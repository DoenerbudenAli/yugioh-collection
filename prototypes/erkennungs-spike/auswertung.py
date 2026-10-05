"""PROTOTYP (Erkennungs-Spike #60): Bild-Ebene je Encoder-Variante und Schicht, Passcode-Lesequote.

Fenster je Clip: Bilder von liegt_ruhig bis vor ist_weg mit gefundener Karte.
Aufruf: python auswertung.py <arbeit> <eval-daten>  -> <arbeit>/auswertung.json + Textausgabe
"""
import json, sys
from collections import defaultdict
from pathlib import Path
import numpy as np

ARBEIT, EVAL = Path(sys.argv[1]), Path(sys.argv[2])
m = {c["clip"]: c for c in map(json.loads, open(EVAL / "manifest/manifest.jsonl", encoding="utf-8")) if c["teil"] == "kalibrier"}
bilder = [z for z in map(json.loads, open(ARBEIT / "bilder.jsonl", encoding="utf-8"))]
ocr = {(z["clip"], z["i"]): z for z in map(json.loads, open(ARBEIT / "ocr.jsonl", encoding="utf-8"))} if (ARBEIT / "ocr.jsonl").exists() else {}
VAR = list(next(z for z in bilder if "top" in z)["top"])


def soll(c):
    return None if c["exemplar"] is None or c["nicht_im_katalog"] else c["passcode"]


def schichten(c):
    s = set(c["schichten"]) | {f"Haltung {c['haltung']}", f"Glanz {c['glanz']}"}
    if c["stoerung"]: s.add(f"Störung {c['stoerung']}")
    return s


fenster = [z for z in bilder if "top" in z and m[z["clip"]]["exemplar"] is not None
           and m[z["clip"]]["liegt_ruhig"] <= z["i"] < m[z["clip"]]["ist_weg"]]
alle_mit_karte = [z for z in bilder if "top" in z]
erg = {"bilder_gesamt": len(bilder), "bilder_fenster": len(fenster), "varianten": {}}
print(f"{len(bilder)} Bilder, {len(fenster)} im Liegefenster mit Karte")

for v in VAR:
    # Falsch-Akzeptanz-Grenze: höchste Top-1-Ähnlichkeit eines falschen Top-1 über ALLE Bilder mit Fund
    falsch = [z["top"][v][0][1] for z in alle_mit_karte if z["top"][v][0][0] != soll(m[z["clip"]])]
    grenze = max(falsch) if falsch else 0
    je = defaultdict(lambda: [0, 0, 0, 0])  # n, top1, top5, über Grenze & richtig
    ex_top1 = defaultdict(lambda: defaultdict(list))
    for z in fenster:
        c = m[z["clip"]]; s = soll(c); t = z["top"][v]
        r1, r5 = t[0][0] == s, s in [k for k, _ in t[:5]]
        for sch in schichten(c) | {"alle"}:
            a = je[sch]; a[0] += 1; a[1] += r1; a[2] += r5; a[3] += r1 and t[0][1] > grenze
        ex_top1[c["exemplar"]][c["haltung"]].append(r1)
    erg["varianten"][v] = {"grenze_falsch": round(grenze, 4),
                           "falsch_sims_p99": round(float(np.percentile(falsch, 99)), 4) if falsch else None,
                           "schichten": {k: {"n": a[0], "top1": round(a[1] / a[0], 3), "top5": round(a[2] / a[0], 3),
                                             "recall_0fa": round(a[3] / a[0], 3)} for k, a in sorted(je.items())}}
    print(f"\n== {v}: höchste falsche Top-1-Ähnlichkeit {grenze:.3f}")
    for k, a in sorted(je.items(), key=lambda x: -x[1][0]):
        print(f"  {k:28s} n={a[0]:5d} top1={a[1]/a[0]:.3f} top5={a[2]/a[0]:.3f} recall@0FA={a[3]/a[0]:.3f}")

if ocr:
    je = defaultdict(lambda: [0, 0, 0])  # Bilder, richtig gelesen, falsch gelesen (gültiger Passcode einer anderen Karte)
    ex = defaultdict(lambda: [False, False])
    for z in fenster:
        c = m[z["clip"]]; o = ocr.get((z["clip"], z["i"]), {}); k = o.get("karte")
        for sch in schichten(c) | {"alle"}:
            a = je[sch]; a[0] += 1; a[1] += k is not None and k == soll(c); a[2] += k is not None and k != soll(c)
        e = ex[(c["clip"])]; e[0] |= k is not None and k == soll(c); e[1] |= k is not None and k != soll(c)
    falsch_aussen = sum(1 for z in bilder if (o := ocr.get((z["clip"], z["i"]))) and o.get("karte") and o["karte"] != soll(m[z["clip"]]))
    erg["passcode"] = {"schichten": {k: {"n": a[0], "je_bild": round(a[1] / a[0], 3), "falsch_je_bild": round(a[2] / a[0], 4)} for k, a in je.items()},
                       "je_clip": round(np.mean([e[0] for e in ex.values()]), 3), "clips_mit_falschlesung": sum(e[1] for e in ex.values()),
                       "falschlesungen_alle_bilder": falsch_aussen}
    print("\n== Passcode-OCR")
    for k, a in sorted(je.items(), key=lambda x: -x[1][0]):
        print(f"  {k:28s} n={a[0]:5d} je Bild={a[1]/a[0]:.3f} falsch={a[2]/a[0]:.4f}")
    print(f"  je Clip (mind. ein Bild richtig): {erg['passcode']['je_clip']}, Clips mit Falschlesung: {erg['passcode']['clips_mit_falschlesung']}, Falschlesungen gesamt: {falsch_aussen}")

json.dump(erg, open(ARBEIT / "auswertung.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
