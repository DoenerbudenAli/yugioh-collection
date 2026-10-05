"""PROTOTYP: Fundquote des Detektors je Schwelle – liegt-ruhig-Bilder vs. Bilder nach ist_weg (leer)."""
import cv2, numpy as np
import merkmale as M

yolo = M.detektor()
clips = M.kalibrier_clips()
def bester(i, c, imgsz):
    b = cv2.imread(str(M.EVAL / f"aufnahmen/{c['aufnahme']}/{i:06d}.jpg"))
    r = yolo.predict(b, verbose=False, device=0, half=True, conf=0.01, imgsz=imgsz)[0]
    return float(r.obb.conf.max()) if r.obb is not None and len(r.obb.conf) else 0.0
for imgsz in (640, 1024):
    liegt, leer = [], []
    for c in clips:
        if c["exemplar"] is None or c["stoerung"]: continue
        liegt.append((c["haltung"], bester(c["liegt_ruhig"], c, imgsz), bester(min(c["liegt_ruhig"] + 3, c["ist_weg"] - 1), c, imgsz)))
        if c["ist_weg"] + 2 <= c["bis"]: leer.append(bester(c["ist_weg"] + 2, c, imgsz))
    for s in (0.05, 0.1, 0.25):
        for h in ("frei", "halterung"):
            L = [x for x in liegt if x[0] == h]
            print(imgsz, s, h, f"liegt: {np.mean([x[1] >= s for x in L]):.2f}  liegt+3: {np.mean([x[2] >= s for x in L]):.2f}")
        print(imgsz, s, f"leer (falsch gefunden): {np.mean([x >= s for x in leer]):.2f} n={len(leer)}")
