"""Kamera-Sonde: Echo-WebSocket, Ablage für Clips, Standbilder und Ergebnisse.

Wegwerf-Prototyp zu Issue #52. Kein Modulcode, keine Tests.

Binäres Frame-Format (Handy → Server):
    4 Byte Big-Endian Länge n | n Byte JSON-Kopf (UTF-8) | JPEG
Der Server antwortet sofort mit einem Text-Frame {"seq", "srv_ein_ms", "srv_aus_ms"}
und schreibt erst danach, falls eine Aufnahme läuft, das Bild auf die Platte.
"""

import asyncio
import json
import os
import re
import struct
import time
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse

DATEN = Path(os.environ.get("DATEN", "./daten"))
HIER = Path(__file__).parent

app = FastAPI()


def jetzt_ms() -> float:
    return time.time_ns() / 1e6


def sicherer_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", name).strip("-")[:60] or "ohne-name"


def stempel() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


@app.get("/")
async def seite() -> FileResponse:
    return FileResponse(HIER / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/worker.js")
async def worker() -> FileResponse:
    return FileResponse(HIER / "worker.js", media_type="text/javascript", headers={"Cache-Control": "no-store"})


@app.post("/ergebnis")
async def ergebnis(request: Request) -> JSONResponse:
    daten = await request.json()
    ziel = DATEN / "ergebnisse" / f"{stempel()}-{sicherer_name(str(daten.get('name', 'lauf')))}.json"
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(json.dumps(daten, ensure_ascii=False, indent=1), encoding="utf-8")
    return JSONResponse({"gespeichert": str(ziel.relative_to(DATEN))})


@app.post("/standbild")
async def standbild(request: Request) -> JSONResponse:
    meta = json.loads(request.headers.get("x-meta", "{}"))
    ziel = DATEN / "standbilder" / f"{stempel()}-{sicherer_name(str(meta.get('name', 'bild')))}"
    ziel.parent.mkdir(parents=True, exist_ok=True)
    endung = ".png" if request.headers.get("content-type") == "image/png" else ".jpg"
    ziel.with_suffix(endung).write_bytes(await request.body())
    ziel.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return JSONResponse({"gespeichert": str(ziel.relative_to(DATEN)) + endung})


class Aufnahme:
    """Eine laufende Aufnahme: JPEG-Folge plus frames.jsonl mit Kopf und Server-Zeiten."""

    def __init__(self, name: str, einstellungen: dict) -> None:
        self.ordner = DATEN / "clips" / f"{stempel()}-{sicherer_name(name)}"
        self.ordner.mkdir(parents=True, exist_ok=True)
        (self.ordner / "aufnahme.json").write_text(
            json.dumps({"name": name, "start": datetime.now().isoformat(), "einstellungen": einstellungen},
                       ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        self.index = 0
        self.zeilen = (self.ordner / "frames.jsonl").open("a", encoding="utf-8")

    def schreibe(self, kopf: dict, jpeg: bytes) -> None:
        datei = f"{self.index:06d}.jpg"
        (self.ordner / datei).write_bytes(jpeg)
        self.zeilen.write(json.dumps({"i": self.index, "datei": datei, **kopf}, ensure_ascii=False) + "\n")
        self.index += 1

    def schliesse(self) -> dict:
        self.zeilen.close()
        return {"ordner": str(self.ordner.relative_to(DATEN)), "bilder": self.index}


@app.websocket("/ws")
async def echo(ws: WebSocket) -> None:
    await ws.accept()
    aufnahme: Aufnahme | None = None
    try:
        while True:
            nachricht = await ws.receive()
            if nachricht["type"] == "websocket.disconnect":
                break
            ein = jetzt_ms()
            roh = nachricht.get("bytes")
            if roh is not None:
                (laenge,) = struct.unpack(">I", roh[:4])
                kopf = json.loads(roh[4 : 4 + laenge])
                await ws.send_text(json.dumps({"seq": kopf.get("seq"), "srv_ein_ms": ein, "srv_aus_ms": jetzt_ms()}))
                if aufnahme is not None:
                    kopf["srv_ein_ms"] = ein
                    await asyncio.to_thread(aufnahme.schreibe, kopf, roh[4 + laenge :])
                continue
            befehl = json.loads(nachricht.get("text") or "{}")
            if befehl.get("typ") == "aufnahme_start":
                if aufnahme is not None:
                    aufnahme.schliesse()
                aufnahme = Aufnahme(str(befehl.get("name", "clip")), befehl.get("einstellungen", {}))
                await ws.send_text(json.dumps({"typ": "aufnahme_laeuft", "ordner": str(aufnahme.ordner.relative_to(DATEN))}))
            elif befehl.get("typ") == "aufnahme_stopp" and aufnahme is not None:
                await ws.send_text(json.dumps({"typ": "aufnahme_beendet", **aufnahme.schliesse()}))
                aufnahme = None
            elif befehl.get("typ") == "ping":
                await ws.send_text(json.dumps({"typ": "pong", "srv_ms": jetzt_ms()}))
    except WebSocketDisconnect:
        pass
    finally:
        if aufnahme is not None:
            aufnahme.schliesse()
