"""PROTOTYP: „Unruhe“ je Bild – Anteil Pixel, die nicht wie der helle, ungesättigte Tisch aussehen. Leerer Tisch ≈ 0, Hand/Karte ≫ 0.
Ergebnis /arbeit/leer.jsonl. Läuft auf der CPU."""
import json
from pathlib import Path
import cv2
EVAL, ARBEIT = Path("/eval"), Path("/arbeit")
clips = [c for c in map(json.loads, open(EVAL / "manifest/manifest.jsonl", encoding="utf-8")) if c["teil"] == "kalibrier"]
with open(ARBEIT / "leer.jsonl", "w") as f:
    for c in clips:
        for i in range(c["von"], c["bis"] + 1):
            hsv = cv2.cvtColor(cv2.imread(str(EVAL / f"aufnahmen/{c['aufnahme']}/{i:06d}.jpg"), cv2.IMREAD_REDUCED_COLOR_8), cv2.COLOR_BGR2HSV)
            tisch = (hsv[..., 2] > 140) & (hsv[..., 1] < 45)
            f.write(json.dumps({"clip": c["clip"], "i": i, "unruhe": round(float(1 - tisch.mean()), 4)}) + "\n")
print("fertig")
