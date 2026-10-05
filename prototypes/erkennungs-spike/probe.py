"""PROTOTYP: Smoke-Test sm_120 + Detektor auf ein paar Bildern, schreibt gerade gezogene Karten nach /arbeit/probe/."""
import json
from pathlib import Path
import cv2, torch
import merkmale as M

print(torch.__version__, torch.cuda.get_device_name(), torch.cuda.get_arch_list())
out = Path("/arbeit/probe"); out.mkdir(exist_ok=True)
yolo = M.detektor()
clips = M.kalibrier_clips()
for c in clips[::12]:
    for i in (c["von"], c["liegt_ruhig"], c["ist_weg"]):
        b = cv2.imread(str(M.EVAL / f"aufnahmen/{c['aufnahme']}/{i:06d}.jpg"))
        f = M.finde(yolo, [b])[0]
        tag = f"{c['clip'].replace('/', '-')}-{i}"
        if f is None:
            print(tag, "keine Karte"); continue
        print(tag, round(f[0], 2))
        if i == c["liegt_ruhig"]:
            cv2.imwrite(str(out / f"{tag}.jpg"), M.gerade(b, f[1], M.HOCH))
