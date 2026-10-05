"""PROTOTYP (Erkennungs-Spike #60): spielt den Scan-Ablauf über die Merkmale des Kalibrier-Teils ab.

Port des Reducers `ScanAblauf` aus prototype/scan-ux (nur Bild-Pfad; kein Rückgängig/Proxy/Ausfall).
Zeiten in ms statt in Bildern, weil die Bildrate gedrosselt simuliert wird.

Eingabe: /arbeit/bilder.jsonl (+ optional /arbeit/ocr.jsonl), Manifest. Läuft auch ohne GPU.
Aufruf: python sim.py <arbeit> <eval-daten>
"""
import itertools, json, sys
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path

ARBEIT, EVAL = Path(sys.argv[1]), Path(sys.argv[2])


# ---------- Reducer ----------
def sicher(b, c):
    k = b["kand"]
    if not k: return False
    ab = k[0][1] - k[1][1] if len(k) > 1 else 1
    return k[0][1] >= c["sicher_ab"] and ab >= c["abstand"]


def simuliere(bilder, c):
    """bilder: Liste {t, leer, kand:[(karte, sim)], pass_karte} in Zeitfolge. -> Ereignisse."""
    ev = []
    phase, lauf, lauf_t0, wartet, wartet_gebucht = "bereit", None, None, None, False
    leer_z, zuletzt_weg, wechsel = 0, None, (None, 0)

    def buchen(karte, t, grund):
        nonlocal phase, lauf, wartet, wartet_gebucht, leer_z, wechsel
        if zuletzt_weg and zuletzt_weg[0] == karte and t - zuletzt_weg[1] <= c["bremse_ms"]:
            return pruef("doppelt?", t, True)
        ev.append(("gebucht", karte, t, grund))
        phase, wartet, wartet_gebucht, lauf, leer_z, wechsel = "wartet", karte, True, None, 0, (None, 0)

    def pruef(grund, t, liegt):
        nonlocal phase, lauf, wartet, wartet_gebucht, leer_z, wechsel
        kand = sorted({k for b in lauf for k, _ in b["kand"][:1]})
        ev.append(("pruef", kand[0] if kand else None, t, grund))
        top = max(((s, k) for b in lauf for k, s in b["kand"][:1]), default=(0, None))[1]
        phase, wartet, wartet_gebucht = ("wartet", top, False) if liegt else ("bereit", None, False)
        lauf, leer_z, wechsel = None, 0, (None, 0)

    def entscheide(b):
        t = b["t"]
        top = b["kand"][0] if b["kand"] else None
        if c["passcode"] and b.get("pass_karte") is not None:
            if c["passcode"] == "allein" or (top and top[0] == b["pass_karte"]):
                return buchen(b["pass_karte"], t, "passcode")
        letzte = lauf[-c["konsens"]:]
        if len(letzte) == c["konsens"] and all(sicher(x, c) and x["kand"][0][0] == letzte[0]["kand"][0][0] for x in letzte):
            return buchen(letzte[0]["kand"][0][0], t, "konsens")
        if t - lauf_t0 >= c["zeitlimit_ms"]:
            return pruef("zeitlimit", t, True)

    for b in bilder:
        if b.get("verdeckt"):  # weder Karte noch leer: zählt nicht als "weg", startet keinen Scan
            leer_z = 0
            if phase == "erkenne" and b["t"] - lauf_t0 >= c["zeitlimit_ms"]: pruef("zeitlimit", b["t"], True)
            continue
        if phase == "bereit":
            if b["leer"]: continue
            lauf, lauf_t0, leer_z = [b], b["t"], 0
            phase = "erkenne"; entscheide(b)
        elif phase == "erkenne":
            if b["leer"]:
                leer_z += 1
                if leer_z < c["leer_bis_weg"]: continue
                if any(x["kand"] for x in lauf): pruef("weggenommen", b["t"], False)
                else: phase, lauf, leer_z = "bereit", None, 0
                continue
            leer_z = 0; lauf.append(b); entscheide(b)
        elif phase == "wartet":
            if b["leer"]:
                leer_z += 1
                if leer_z < c["leer_bis_weg"]: continue
                ev.append(("weg", wartet, b["t"], ""))
                if wartet_gebucht or (zuletzt_weg and zuletzt_weg[0] == wartet):
                    zuletzt_weg = (wartet, b["t"])
                phase, wartet, leer_z, wechsel = "bereit", None, 0, (None, 0)
                continue
            leer_z = 0
            if not (sicher(b, c) and b["kand"][0][0] != wartet):
                wechsel = (None, 0); continue
            k = b["kand"][0][0]
            z = wechsel[1] + 1 if wechsel[0] == k else 1
            if z < c["wechsel"]:
                wechsel = (k, z); continue
            lauf, lauf_t0, leer_z, wechsel = [b], b["t"], 0, (None, 0)
            phase = "erkenne"; entscheide(b)
    return ev


# ---------- Daten ----------
def lade():
    m = {c["clip"]: c for c in map(json.loads, open(EVAL / "manifest/manifest.jsonl", encoding="utf-8")) if c["teil"] == "kalibrier"}
    bilder = defaultdict(list)
    for z in map(json.loads, open(ARBEIT / "bilder.jsonl", encoding="utf-8")):
        bilder[z["clip"]].append(z)
    unruhe = {(z["clip"], z["i"]): z["unruhe"] for z in map(json.loads, open(ARBEIT / "leer.jsonl", encoding="utf-8"))}
    ocr = {}
    if (ARBEIT / "ocr.jsonl").exists():
        for z in map(json.loads, open(ARBEIT / "ocr.jsonl", encoding="utf-8")):
            ocr[(z["clip"], z["i"])] = z.get("karte")
    return m, bilder, ocr, unruhe


def folge(zeilen, variante, fps, ocr, det_min, unruhe, u_leer):
    out, letzte_t = [], None
    for z in sorted(zeilen, key=lambda z: z["t_ms"]):
        if fps and letzte_t is not None and z["t_ms"] - letzte_t < 1000 / fps - 5: continue
        letzte_t = z["t_ms"]
        da = z["det"] is not None and z["det"] >= det_min and "top" in z
        verdeckt = not da and unruhe[(z["clip"], z["i"])] >= u_leer
        out.append({"i": z["i"], "t": z["t_ms"], "leer": not da and not verdeckt, "verdeckt": verdeckt,
                    "kand": [tuple(x) for x in z["top"][variante][:3]] if da else [],
                    "pass_karte": ocr.get((z["clip"], z["i"])) if da else None})
    return out


def bewerte_clip(clip, bilder, ev, t_liegt):
    soll = clip["passcode"] if not clip["nicht_im_katalog"] else None
    buch = [e for e in ev if e[0] == "gebucht"]
    pr = [e for e in ev if e[0] == "pruef"]
    r = {"gebucht": len(buch), "richtig": sum(e[1] == soll for e in buch), "falsch": sum(e[1] != soll for e in buch),
         "pruef": len(pr), "bremse": sum(e[3] == "doppelt?" for e in pr)}
    if clip["exemplar"] is None:  # Störclip: jede Buchung ist falsch
        r["falsch"], r["richtig"] = len(buch), 0
    r["art"] = "stoer" if clip["stoerung"] else ("ausserhalb" if clip["nicht_im_katalog"] else "normal")
    r["doppel"] = max(0, r["richtig"] - 1)
    r["verloren"] = int(r["art"] != "stoer" and not buch and not pr)
    r["verloren_stoer"] = int(r["art"] == "stoer" and clip["exemplar"] is not None and not buch and not pr)
    r["auto"] = int(r["art"] == "normal" and r["richtig"] >= 1 and r["falsch"] == 0)
    r["dauer_ms"] = (buch[0][2] - t_liegt) if buch and t_liegt is not None else None
    r["grund"] = buch[0][3] if buch else (pr[0][3] if pr else None)
    return r


def lauf(args):
    variante, fps, c, det_min, haltung, daten = args
    m, bilder, ocr, unruhe = daten
    gesamt = defaultdict(int); dauern = []; je_clip = {}
    for name, clip in m.items():
        if haltung and clip["haltung"] != haltung: continue
        zs = bilder.get(name)
        if not zs: continue
        f = folge(zs, variante, fps, ocr, det_min, unruhe, c["u_leer"])
        t_liegt = next((z["t_ms"] for z in zs if z["i"] == clip["liegt_ruhig"]), None)
        r = bewerte_clip(clip, f, simuliere(f, c), t_liegt)
        je_clip[name] = r
        for k in ("gebucht", "richtig", "falsch", "pruef", "bremse", "doppel", "verloren", "verloren_stoer", "auto"): gesamt[k] += r[k]
        gesamt["clips"] += 1; gesamt["normal"] += r["art"] == "normal"
        gesamt["pruef_normal"] += r["art"] == "normal" and r["pruef"] > 0
        if r["dauer_ms"] is not None and r["art"] == "normal": dauern.append(r["dauer_ms"])
    dauern.sort()
    q = lambda p: round(dauern[min(len(dauern) - 1, int(p * len(dauern)))]) if dauern else None
    return {"variante": variante, "fps": fps, "haltung": haltung, **c, "det_min": det_min, **gesamt,
            "auto_quote": round(gesamt["auto"] / max(1, gesamt["normal"]), 3),
            "dauer_p50": q(.5), "dauer_p95": q(.95), "dauer_max": dauern[-1] if dauern else None}, je_clip


DATEN = None
def _init():
    global DATEN
    DATEN = lade()
def _lauf(a):
    return lauf((*a, DATEN))[0]


if __name__ == "__main__":
    varianten = sys.argv[3].split(",") if len(sys.argv) > 3 else ["draw2-karte", "draw2-artwork", "dinov2s-karte", "dinov2b-karte"]
    gitter = []
    for v, fps, haltung in itertools.product(varianten, [6, 8, 10, 20], ["frei", "halterung"]):
        for sa, ab, ko, zl, lw, ul in itertools.product(
                [0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.8], [0.0, 0.05, 0.1, 0.15],
                [1, 2, 3], [800, 1200, 2000, 3000], [1, 2, 3], [0.15, 0.3, 0.5, 1.01]):
            c = {"sicher_ab": sa, "abstand": ab, "konsens": ko, "zeitlimit_ms": zl, "leer_bis_weg": lw,
                 "wechsel": 2, "bremse_ms": 1000, "passcode": None, "u_leer": ul}
            gitter.append((v, fps, c, 0.25, haltung))
    print(f"{len(gitter)} Läufe", flush=True)
    with Pool(14, initializer=_init) as p:
        erg = p.map(_lauf, gitter, chunksize=64)
    with open(ARBEIT / "gitter.jsonl", "w", encoding="utf-8") as f:
        for e in erg: f.write(json.dumps(e) + "\n")
    print("fertig", flush=True)
