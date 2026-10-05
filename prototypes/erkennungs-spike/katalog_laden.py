"""PROTOTYP (Erkennungs-Spike #60): lädt alle YGOProDeck-Vollbilder nach eval-daten/katalog/bilder-voll/.

Gedrosselt auf ~10 Bilder/s, überspringt vorhandene Dateien (wiederaufnehmbar).
Aufruf: python katalog_laden.py <pfad zu eval-daten>
"""
import json, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

eval_daten = Path(sys.argv[1])
ziel = eval_daten / "katalog" / "bilder-voll"
ziel.mkdir(parents=True, exist_ok=True)
karten = json.load(open(eval_daten / "katalog" / "cardinfo-en.json", encoding="utf-8"))
karten = karten.get("data", karten)
urls = [(i["id"], i["image_url"]) for k in karten for i in k["card_images"]]
offen = [(i, u) for i, u in urls if not (ziel / f"{i}.jpg").exists()]
print(f"{len(urls)} Bilder, {len(offen)} offen", flush=True)

fehler = []
def lade(arg):
    i, u = arg
    for versuch in range(3):
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "yugioh-collection-spike/0.1"})
            daten = urllib.request.urlopen(req, timeout=30).read()
            (ziel / f"{i}.jpg").write_bytes(daten)
            return
        except Exception as e:  # noqa: BLE001
            time.sleep(2 * (versuch + 1))
    fehler.append(i)

t0 = time.time()
with ThreadPoolExecutor(4) as ex:
    for n, _ in enumerate(ex.map(lade, offen), 1):
        soll = n / 10.0  # 10/s
        if (dt := time.time() - t0) < soll:
            time.sleep(soll - dt)
        if n % 500 == 0:
            print(f"{n}/{len(offen)} nach {time.time() - t0:.0f} s", flush=True)
print(f"fertig, {len(fehler)} Fehler: {fehler[:20]}", flush=True)
