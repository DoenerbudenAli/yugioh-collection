"""PROTOTYP (Erkennungs-Spike #60): Passcode-OCR auf den Ausschnitten aus merkmale.py.

Liest /arbeit/passcode/*.png (unten links der gerade gezogenen Karte), EasyOCR nur Ziffern.
Ergebnis /arbeit/ocr.jsonl: je Bild gelesener Text und – falls 8 Ziffern auf eine Katalog-Karte passen – deren ID.
"""
import json, re, time
from pathlib import Path

import cv2
import easyocr

EVAL, ARBEIT = Path("/eval"), Path("/arbeit")
d = json.load(open(EVAL / "katalog/cardinfo-en.json", encoding="utf-8"))
d = d.get("data", d)
passcode_zu_karte = {}
for k in d:
    passcode_zu_karte[k["id"]] = k["id"]
    for i in k["card_images"]:
        passcode_zu_karte.setdefault(i["id"], k["id"])

reader = easyocr.Reader(["en"], gpu=True, verbose=False)
clips = {c["aufnahme"]: c for c in map(json.loads, open(EVAL / "manifest/manifest.jsonl", encoding="utf-8")) if c["teil"] == "kalibrier"}
bild_zu_clip = {}
for c in map(json.loads, open(EVAL / "manifest/manifest.jsonl", encoding="utf-8")):
    if c["teil"] != "kalibrier": continue
    for i in range(c["von"], c["bis"] + 1):
        bild_zu_clip[(c["aufnahme"], i)] = c["clip"]

import sys, numpy as np
WEIT = len(sys.argv) > 1 and sys.argv[1] == "weit"
if WEIT:  # zweiter Versuch: aus dem Originalbild, Karte 2x hochskaliert, Fenster unten links großzügig
    dateien = [z for z in map(json.loads, open(ARBEIT / "bilder.jsonl", encoding="utf-8")) if "ecken" in z]
else:
    dateien = sorted((ARBEIT / "passcode").glob("*.png"))
t0 = time.time()
with open(ARBEIT / ("ocr-weit.jsonl" if WEIT else "ocr.jsonl"), "w", encoding="utf-8") as f:
    for n, p in enumerate(dateien):
        if WEIT:
            aufnahme, nr = p["clip"].split("/")[0], p["i"]
            b = cv2.imread(str(EVAL / f"aufnahmen/{aufnahme}/{nr:06d}.jpg"))
            M = cv2.getPerspectiveTransform(np.float32(p["ecken"]), np.float32([[0, 0], [1179, 0], [1179, 1719], [0, 1719]]))
            img = cv2.warpPerspective(b, M, (1180, 1720), flags=cv2.INTER_CUBIC)[int(.86 * 1720):, :int(.6 * 1180)]
        else:
            aufnahme, nr = p.stem.rsplit("-", 1)
            img = cv2.imread(str(p))
            img = cv2.resize(img, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        texte = reader.readtext(img, allowlist="0123456789", detail=1, paragraph=False)
        text = " ".join(t for _, t, _ in texte)
        karte = None
        for kandidat in re.findall(r"\d{8}", text.replace(" ", "")):
            if int(kandidat) in passcode_zu_karte:
                karte = passcode_zu_karte[int(kandidat)]; break
        f.write(json.dumps({"clip": bild_zu_clip.get((aufnahme, int(nr))), "i": int(nr), "text": text, "karte": karte}) + "\n")
        if n % 1000 == 0: print(f"{n}/{len(dateien)} {time.time() - t0:.0f} s", flush=True)
print("fertig", flush=True)
