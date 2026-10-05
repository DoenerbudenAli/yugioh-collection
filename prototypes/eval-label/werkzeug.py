"""Label-Werkzeug fürs Eval-Set (Issue #47, ADR 0008). Wegwerf-Prototyp, nur Standardbibliothek.

Start:  python werkzeug.py        → http://127.0.0.1:8770

Ablage (EVAL_DATEN, Standard: <Workspace>/eval-daten, außerhalb jedes Clones):
    katalog/cardinfo-en.json, cardinfo-de.json   YGOProDeck-Komplettabruf
    katalog/bilder-klein/<bild_id>.jpg           Vorschaubilder (Cache, nicht im Manifest)
    stapel/<S01>.json                            Stapel-Listen in Scan-Reihenfolge
    aufnahmen/<ordner>/                          Aufnahmen der Kamera-Sonde (JPEGs, frames.jsonl, aufnahme.json)
    labels/<ordner>.json                         Clip-Schnitte und Zuordnung je Aufnahme
    manifest/manifest.jsonl, bilder.sha256       Ergebnis von „Manifest bauen“ (geht per PR nach eval/)
"""

import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import threading
import urllib.request
from collections import Counter, defaultdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

HIER = Path(__file__).resolve().parent
DATEN = Path(os.environ.get("EVAL_DATEN", HIER.parents[2] / "eval-daten"))
PI_CLIPS = os.environ.get("PI_CLIPS", "pi:/srv/data/yugioh/kamera-sonde/clips")
PORT = int(os.environ.get("PORT", "8770"))
NAME = re.compile(r"^[A-Za-z0-9_.-]+$")

NICHT_IM_KATALOG_TYPEN = {"token", "skill"}

QUOTEN = [  # Schicht, Minimum (ADR 0008); None = alle vorhandenen
    ("Deutsch", 80), ("Englisch", 80), ("Foils", 30), ("Ghost/Starlight/Ultimate", None), ("Altkarten", 20),
    ("Alt-Arts", 10), ("ähnliche Artworks", 15), ("Proxies", 30), ("mit und ohne Hülle", 20),
    ("nicht im Katalog", 15), ("Störclips", 20), ("Abendlicht", 40),
]


# ---------- Katalog ----------

class Katalog:
    def __init__(self) -> None:
        self.karten: dict[int, dict] = {}
        self.nach_bild: dict[int, int] = {}

    def laden(self) -> None:
        ordner = DATEN / "katalog"
        en = json.loads((ordner / "cardinfo-en.json").read_text(encoding="utf-8"))["data"]
        de_pfad = ordner / "cardinfo-de.json"
        de = {k["id"]: k["name"] for k in json.loads(de_pfad.read_text(encoding="utf-8"))["data"]} if de_pfad.exists() else {}
        for k in en:
            bilder = [b["id"] for b in k.get("card_images", [])] or [k["id"]]
            self.karten[k["id"]] = {
                "id": k["id"], "name": k["name"], "name_de": de.get(k["id"]), "typ": k.get("humanReadableCardType", k["type"]),
                "frame": k.get("frameType"), "bilder": bilder,
            }
            for b in bilder:
                self.nach_bild[b] = k["id"]

    def suche(self, q: str) -> list[dict]:
        q = q.strip()
        if not q:
            return []
        if q.isdigit():
            treffer = []
            zahl = int(q)
            if zahl in self.nach_bild:  # exakter Passcode (auch Alt-Art-Bild-ID)
                karte = self.karten[self.nach_bild[zahl]]
                treffer.append({**karte, "bild_vorschlag": zahl})
            if len(q) < 8:
                for k in self.karten.values():
                    if len(treffer) >= 20:
                        break
                    if str(k["id"]).zfill(8).startswith(q) and k["id"] != self.nach_bild.get(zahl):
                        treffer.append(k)
            return treffer
        teile = q.casefold().split()
        bewertet = []
        for k in self.karten.values():
            for feld in (k["name"], k["name_de"]):
                if not feld:
                    continue
                f = feld.casefold()
                if all(t in f for t in teile):
                    bewertet.append((0 if f.startswith(teile[0]) else 1, len(f), k))
                    break
        bewertet.sort(key=lambda x: (x[0], x[1]))
        return [k for _, _, k in bewertet[:20]]


KATALOG = Katalog()


def vorschaubild(bild_id: int) -> bytes:
    ziel = DATEN / "katalog" / "bilder-klein" / f"{bild_id}.jpg"
    if not ziel.exists():
        ziel.parent.mkdir(parents=True, exist_ok=True)
        anfrage = urllib.request.Request(
            f"https://images.ygoprodeck.com/images/cards_small/{bild_id}.jpg", headers={"User-Agent": "yugioh-collection-eval-label"})
        with urllib.request.urlopen(anfrage, timeout=20) as antwort:
            ziel.write_bytes(antwort.read())
    return ziel.read_bytes()


# ---------- Ablage ----------

def lies_json(pfad: Path, standard):
    return json.loads(pfad.read_text(encoding="utf-8")) if pfad.exists() else standard


def schreib_json(pfad: Path, daten) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    tmp = pfad.with_suffix(".tmp")
    tmp.write_text(json.dumps(daten, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    tmp.replace(pfad)


def alle_stapel() -> list[dict]:
    return [lies_json(p, {}) for p in sorted((DATEN / "stapel").glob("*.json"))]


def aufnahme_frames(ordner: str) -> list[dict]:
    zeilen = (DATEN / "aufnahmen" / ordner / "frames.jsonl").read_text(encoding="utf-8").splitlines()
    frames = []
    for z in zeilen:
        f = json.loads(z)
        frames.append({"i": f["i"], "datei": f["datei"], "schaerfe": f.get("schaerfe"), "t": f.get("t_aufnahme_ms") or f.get("t_abholung_ms")})
    return frames


def aufnahmen_liste() -> dict:
    lokal = sorted(p.name for p in (DATEN / "aufnahmen").glob("*") if (p / "frames.jsonl").exists())
    labels = {p.stem: lies_json(p, {}) for p in (DATEN / "labels").glob("*.json")}
    try:
        host, pfad = PI_CLIPS.split(":", 1)
        aus = subprocess.run(["ssh", "-o", "ConnectTimeout=5", host, f"ls -1 {pfad}"], capture_output=True, text=True, timeout=15)
        am_pi = sorted(n for n in aus.stdout.split() if NAME.match(n))
        pi_fehler = aus.stderr.strip() if aus.returncode else None
    except Exception as e:  # noqa: BLE001 – Prototyp: Fehler nur anzeigen
        am_pi, pi_fehler = [], str(e)
    return {
        "lokal": [{"ordner": o, "stapel": labels.get(o, {}).get("stapel"), "haltung": labels.get(o, {}).get("haltung"),
                   "clips": len(labels.get(o, {}).get("clips", [])), "fertig": labels.get(o, {}).get("fertig", False)} for o in lokal],
        "nur_am_pi": [o for o in am_pi if o not in lokal], "pi_fehler": pi_fehler,
    }


def hole_vom_pi(ordner: str) -> dict:
    if not NAME.match(ordner):
        raise ValueError("ungültiger Ordner")
    ziel = DATEN / "aufnahmen"
    ziel.mkdir(parents=True, exist_ok=True)
    if (ziel / ordner).exists():
        raise ValueError("schon da – Aufnahmen werden nie überschrieben")
    aus = subprocess.run(["scp", "-r", "-q", f"{PI_CLIPS}/{ordner}", str(ziel / ordner)], capture_output=True, text=True, timeout=1800)
    if aus.returncode:
        raise RuntimeError(aus.stderr.strip() or "scp fehlgeschlagen")
    return {"ordner": ordner, "bilder": len(list((ziel / ordner).glob("*.jpg")))}


# ---------- Quoten und Manifest ----------

def exemplare() -> dict[str, dict]:
    """Alle Exemplare aus allen Stapeln, Schlüssel = Exemplar-ID (z. B. S03-07)."""
    alle = {}
    for s in alle_stapel():
        for k in s.get("karten", []):
            alle[k["ex"]] = {**k, "stapel": s["id"]}
    return alle


def schichten(k: dict) -> list[str]:
    s = []
    if k.get("sprache") == "de":
        s.append("Deutsch")
    if k.get("sprache") == "en":
        s.append("Englisch")
    if k.get("glanz") == "bild":
        s.append("Foils")
    if k.get("glanz") == "ganz":
        s.append("Ghost/Starlight/Ultimate")
    if k.get("altkarte"):
        s.append("Altkarten")
    if k.get("ygopro_id") and k.get("bild_id") and k["bild_id"] != k["ygopro_id"]:
        s.append("Alt-Arts")
    if k.get("aehnlich"):
        s.append("ähnliche Artworks")
    if k.get("proxy"):
        s.append("Proxies")
    if k.get("nicht_im_katalog"):
        s.append("nicht im Katalog")
    return s


def gelabelte_clips() -> list[tuple[str, dict, dict]]:
    """(ordner, label-kopf, clip) für alle Clips aller Aufnahmen."""
    aus = []
    for p in sorted((DATEN / "labels").glob("*.json")):
        lab = lies_json(p, {})
        for c in lab.get("clips", []):
            aus.append((p.stem, lab, c))
    return aus


def huelle_von(lab: dict, k: dict | None) -> str | None:
    h = lab.get("huelle", "wie-stapel")
    return (k or {}).get("huelle") if h == "wie-stapel" else h


def quoten() -> dict:
    ex = exemplare()
    zaehler: Counter[str] = Counter()
    for k in ex.values():
        zaehler.update(schichten(k))
    aufgenommen: dict[str, set] = defaultdict(set)  # Exemplar → {(haltung, licht, huelle)}
    stoer = 0
    for _, lab, c in gelabelte_clips():
        if c.get("stoerung"):
            stoer += 1
        if c.get("ex"):
            aufgenommen[c["ex"]].add((lab.get("haltung"), lab.get("licht"), huelle_von(lab, ex.get(c["ex"]))))
    zaehler["Störclips"] = stoer
    zaehler["Abendlicht"] = sum(1 for a in aufgenommen.values() if any(x[1] == "abend" for x in a))
    zaehler["mit und ohne Hülle"] = sum(1 for a in aufgenommen.values() if {"mit", "ohne"} <= {x[2] for x in a})
    beide = sum(1 for a in aufgenommen.values() if {"halterung", "frei"} <= {x[0] for x in a})
    return {"exemplare": len(ex), "beide_haltungen": beide, "aufgenommen": len(aufgenommen),
            "quoten": [{"schicht": s, "minimum": m, "ist": zaehler[s]} for s, m in QUOTEN]}


def sha256(pfad: Path) -> str:
    return hashlib.sha256(pfad.read_bytes()).hexdigest()


def teile_zu(ex: dict[str, dict]) -> dict[str, str]:
    """50/50 geschichtet: innerhalb jeder Schicht-Kombination abwechselnd, Reihenfolge per Hash (deterministisch)."""
    gruppen: dict[tuple, list[str]] = defaultdict(list)
    for e, k in ex.items():
        gruppen[tuple(sorted(schichten(k)))].append(e)
    teil, kippe = {}, 0
    for schluessel in sorted(gruppen):
        for e in sorted(gruppen[schluessel], key=lambda x: hashlib.sha256(x.encode()).hexdigest()):
            teil[e] = "kalibrier" if kippe % 2 == 0 else "pruef"
            kippe += 1
    return teil


def baue_manifest() -> dict:
    ex = exemplare()
    teil = teile_zu(ex)
    zeilen, hashes, probleme, stoer = [], [], [], 0
    for ordner, lab, c in gelabelte_clips():
        if not lab.get("fertig"):
            probleme.append(f"{ordner}: nicht als fertig markiert")
            continue
        k = ex.get(c.get("ex") or "")
        if c.get("ex") and not k:
            probleme.append(f"{ordner} Clip {c['n']}: Exemplar {c['ex']} in keinem Stapel")
        if c.get("ex") not in teil:
            stoer += 1
        frames = aufnahme_frames(ordner)
        for i in range(c["von"], c["bis"] + 1):
            hashes.append(f"{sha256(DATEN / 'aufnahmen' / ordner / frames[i]['datei'])}  aufnahmen/{ordner}/{frames[i]['datei']}")
        zeilen.append({
            "clip": f"{ordner}/{c['n']:03d}", "aufnahme": ordner, "von": c["von"], "bis": c["bis"],
            "liegt_ruhig": c.get("liegt"), "ist_weg": c.get("weg"), "exemplar": c.get("ex"),
            "teil": teil[c["ex"]] if c.get("ex") in teil else ("kalibrier" if stoer % 2 == 0 else "pruef"),
            "passcode": (k or {}).get("passcode"), "ygoprodeck_id": (k or {}).get("ygopro_id"), "art_variante": (k or {}).get("bild_id"),
            "name": (k or {}).get("name"), "sprache": (k or {}).get("sprache"), "glanz": (k or {}).get("glanz"),
            "proxy": (k or {}).get("proxy"), "haltung": lab.get("haltung"), "licht": lab.get("licht"), "huelle": huelle_von(lab, k),
            "nicht_im_katalog": bool((k or {}).get("nicht_im_katalog")), "schichten": schichten(k) if k else [],
            "stoerung": c.get("stoerung"),
        })
    ziel = DATEN / "manifest"
    ziel.mkdir(parents=True, exist_ok=True)
    (ziel / "manifest.jsonl").write_text("".join(json.dumps(z, ensure_ascii=False) + "\n" for z in zeilen), encoding="utf-8", newline="\n")
    (ziel / "bilder.sha256").write_text("\n".join(sorted(set(hashes), key=lambda h: h[66:])) + "\n", encoding="utf-8", newline="\n")
    return {"clips": len(zeilen), "bilder": len(set(hashes)), "teile": Counter(z["teil"] for z in zeilen), "probleme": probleme,
            "manifest_sha256": sha256(ziel / "manifest.jsonl")}


# ---------- HTTP ----------

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args) -> None:  # leiser
        if not self.path.startswith(("/aufnahmen/", "/bild/")):
            sys.stderr.write("%s\n" % (fmt % args))

    def antworte(self, daten, status=HTTPStatus.OK, typ="application/json") -> None:
        roh = daten if isinstance(daten, bytes) else json.dumps(daten, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", typ)
        self.send_header("Content-Length", str(len(roh)))
        self.send_header("Cache-Control", "no-store" if typ == "application/json" or typ.startswith("text/html") else "max-age=86400")
        self.end_headers()
        self.wfile.write(roh)

    def koerper(self):
        return json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")

    def do_GET(self) -> None:
        url = urlparse(self.path)
        teile = [unquote(t) for t in url.path.strip("/").split("/") if t]
        try:
            if not teile:
                return self.antworte((HIER / "index.html").read_bytes(), typ="text/html; charset=utf-8")
            if teile == ["api", "suche"]:
                return self.antworte(KATALOG.suche(parse_qs(url.query).get("q", [""])[0]))
            if teile[:2] == ["bild", "klein"] and len(teile) == 3:
                return self.antworte(vorschaubild(int(teile[2].removesuffix(".jpg"))), typ="image/jpeg")
            if teile == ["api", "stapel"]:
                return self.antworte(alle_stapel())
            if teile == ["api", "aufnahmen"]:
                return self.antworte(aufnahmen_liste())
            if teile[:2] == ["api", "aufnahme"] and len(teile) == 3 and NAME.match(teile[2]):
                o = teile[2]
                return self.antworte({"ordner": o, "kopf": lies_json(DATEN / "aufnahmen" / o / "aufnahme.json", {}),
                                      "frames": aufnahme_frames(o), "labels": lies_json(DATEN / "labels" / f"{o}.json", None)})
            if teile[0] == "aufnahmen" and len(teile) == 3 and all(NAME.match(t) for t in teile[1:]):
                return self.antworte((DATEN / "aufnahmen" / teile[1] / teile[2]).read_bytes(), typ="image/jpeg")
            if teile == ["api", "quoten"]:
                return self.antworte(quoten())
            self.antworte({"fehler": "unbekannt"}, HTTPStatus.NOT_FOUND)
        except Exception as e:  # noqa: BLE001
            self.antworte({"fehler": str(e)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_PUT(self) -> None:
        teile = [unquote(t) for t in urlparse(self.path).path.strip("/").split("/") if t]
        try:
            if teile[:2] == ["api", "stapel"] and len(teile) == 3 and NAME.match(teile[2]):
                schreib_json(DATEN / "stapel" / f"{teile[2]}.json", self.koerper())
                return self.antworte({"ok": True})
            if teile[:2] == ["api", "labels"] and len(teile) == 3 and NAME.match(teile[2]):
                schreib_json(DATEN / "labels" / f"{teile[2]}.json", self.koerper())
                return self.antworte({"ok": True})
            self.antworte({"fehler": "unbekannt"}, HTTPStatus.NOT_FOUND)
        except Exception as e:  # noqa: BLE001
            self.antworte({"fehler": str(e)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self) -> None:
        teile = [unquote(t) for t in urlparse(self.path).path.strip("/").split("/") if t]
        try:
            if teile == ["api", "holen"]:
                return self.antworte(hole_vom_pi(self.koerper()["ordner"]))
            if teile == ["api", "manifest"]:
                return self.antworte(baue_manifest())
            self.antworte({"fehler": "unbekannt"}, HTTPStatus.NOT_FOUND)
        except Exception as e:  # noqa: BLE001
            self.antworte({"fehler": str(e)}, HTTPStatus.INTERNAL_SERVER_ERROR)


if __name__ == "__main__":
    KATALOG.laden()
    print(f"Eval-Daten: {DATEN}\nKatalog: {len(KATALOG.karten)} Karten\nhttp://localhost:{PORT}", flush=True)

    class ServerV6(ThreadingHTTPServer):
        address_family = socket.AF_INET6

    # „localhost“ löst zuerst nach ::1 auf; ohne IPv6-Listener kostet jede Anfrage 200 ms Rückfall.
    threading.Thread(target=ServerV6(("::1", PORT), Handler).serve_forever, daemon=True).start()
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
