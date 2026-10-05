"""PROTOTYP: Je Clip Anteil richtiger Top-1 im Liegefenster (draw2-karte) + Ähnlichkeitsverteilung."""
import json, sys
from collections import defaultdict
import numpy as np
V = sys.argv[1] if len(sys.argv) > 1 else "draw2-karte"
m = {c["clip"]: c for c in map(json.loads, open("/eval/manifest/manifest.jsonl", encoding="utf-8")) if c["teil"] == "kalibrier"}
je = defaultdict(list)
richtig_s, falsch_s = [], []
for z in map(json.loads, open("/arbeit/bilder.jsonl", encoding="utf-8")):
    c = m[z["clip"]]
    if "top" not in z or c["exemplar"] is None or c["nicht_im_katalog"]: continue
    if not (c["liegt_ruhig"] <= z["i"] < c["ist_weg"]): continue
    t = z["top"][V]; ok = t[0][0] == c["passcode"]
    je[z["clip"]].append((ok, t[0][0], t[0][1], t[1][1]))
    (richtig_s if ok else falsch_s).append(t[0][1])
print("Ähnlichkeit richtig p5/p50:", np.percentile(richtig_s, [5, 50]).round(3), " falsch p50/p95/max:", np.percentile(falsch_s, [50, 95, 100]).round(3))
schlecht = sorted(((np.mean([x[0] for x in v]), k) for k, v in je.items()))
print(f"Clips: {len(je)}, ganz ohne richtigen Top-1: {sum(q == 0 for q, _ in schlecht)}, unter 50 %: {sum(q < .5 for q, _ in schlecht)}")
for q, k in schlecht[:25]:
    c = m[k]; v = je[k]
    falsch = defaultdict(int)
    for x in v:
        if not x[0]: falsch[x[1]] += 1
    print(f"{q:.2f} {k} n={len(v)} {c['haltung']} {c['glanz']} {c['sprache']} {c['huelle']} {c['stoerung']} | {c['name'][:40]} | falsch: {dict(falsch)} sim={np.median([x[2] for x in v]):.2f}")
