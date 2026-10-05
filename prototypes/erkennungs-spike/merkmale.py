"""PROTOTYP (Erkennungs-Spike #60): Merkmale je Bild des Kalibrier-Teils.

Läuft im Container `erkennungs-spike`:
  /eval   = eval-daten (nur lesend)
  /arbeit = Arbeitsordner außerhalb von Git (Modelle, Index, Ergebnisse)

Schritte:
  katalog  – Referenz-Embeddings aller Katalogbilder je Variante
  bilder   – je Bild des Kalibrier-Teils: Karte finden (DRAW2-YOLO-OBB), gerade ziehen,
             einbetten, kNN gegen den Katalog (Top-10 je Karte), Passcode-Ausschnitt sichern
  tempo    – Latenz je Bild (Batch 1, wie im Dienst) für die Hauptvariante
Der Prüf-Teil wird nie gelesen.
"""
import json, sys, time
from pathlib import Path

import cv2
import numpy as np
import torch
from huggingface_hub import hf_hub_download
from transformers import AutoModel, ViTForImageClassification
from ultralytics import YOLO

EVAL, ARBEIT = Path("/eval"), Path("/arbeit")
DEV = "cuda"
VARIANTEN = ["draw2-karte", "draw2-artwork", "dinov2s-karte", "dinov2b-karte"]
# Artwork-Fenster in einer gerade gezogenen Karte (Anteile von Breite/Höhe, Normalkarte)
ART = (0.12, 0.18, 0.88, 0.70)
# Passcode unten links
PASS = (0.0, 0.925, 0.45, 0.995)
HOCH = (590, 860)  # gerade gezogene Karte in hoher Auflösung (B, H), ~Kartenformat 59x86


# ---------- Modelle ----------
class Encoder:
    def __init__(self, name):
        self.name = name
        if name.startswith("draw2"):
            self.m = ViTForImageClassification.from_pretrained("HichTala/draw2").vit
            self.mean, self.std = [0.5] * 3, [0.5] * 3
        else:
            repo = "facebook/dinov2-small" if name.startswith("dinov2s") else "facebook/dinov2-base"
            self.m = AutoModel.from_pretrained(repo)
            self.mean, self.std = [0.485, 0.456, 0.406], [0.229, 0.224, 0.225]
        self.m = self.m.to(DEV).half().eval()
        self.mean_t = torch.tensor(self.mean, device=DEV).view(1, 3, 1, 1).half()
        self.std_t = torch.tensor(self.std, device=DEV).view(1, 3, 1, 1).half()

    @torch.inference_mode()
    def __call__(self, bilder_rgb):  # Liste von 224x224x3 uint8
        x = torch.from_numpy(np.stack(bilder_rgb)).to(DEV).permute(0, 3, 1, 2).half() / 255
        x = (x - self.mean_t) / self.std_t
        out = self.m(pixel_values=x)
        e = out.last_hidden_state[:, 0] if self.name.startswith("draw2") else out.pooler_output
        return torch.nn.functional.normalize(e.float(), dim=-1)


def ausschnitt(karte_rgb, box):
    h, w = karte_rgb.shape[:2]
    x0, y0, x1, y1 = box
    return karte_rgb[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)]


def eingabe(variante, karte_rgb):
    if variante.endswith("artwork"):
        karte_rgb = ausschnitt(karte_rgb, ART)
    return cv2.resize(karte_rgb, (224, 224), interpolation=cv2.INTER_AREA)


# ---------- Katalog ----------
def katalog_liste():
    d = json.load(open(EVAL / "katalog/cardinfo-en.json", encoding="utf-8"))
    d = d.get("data", d)
    return [(i["id"], k["id"]) for k in d for i in k["card_images"]]


def schritt_katalog():
    liste = [(b, k) for b, k in katalog_liste() if (EVAL / f"katalog/bilder-voll/{b}.jpg").exists()]
    print(f"Katalog: {len(liste)} Bilder", flush=True)
    for v in VARIANTEN:
        enc = Encoder(v)
        embs, t0 = [], time.time()
        for s in range(0, len(liste), 128):
            stapel = []
            for b, _ in liste[s:s + 128]:
                img = cv2.cvtColor(cv2.imread(str(EVAL / f"katalog/bilder-voll/{b}.jpg")), cv2.COLOR_BGR2RGB)
                stapel.append(eingabe(v, img))
            embs.append(enc(stapel).half().cpu())
        e = torch.cat(embs).numpy()
        np.savez(ARBEIT / f"index-{v}.npz", emb=e, bild=np.array([b for b, _ in liste]), karte=np.array([k for _, k in liste]))
        print(f"{v}: {e.shape} in {time.time() - t0:.0f} s", flush=True)
        del enc; torch.cuda.empty_cache()


class Index:
    def __init__(self, v):
        z = np.load(ARBEIT / f"index-{v}.npz")
        self.emb = torch.from_numpy(z["emb"]).to(DEV)  # fp16, normalisiert
        karte = z["karte"]
        self.karten, inv = np.unique(karte, return_inverse=True)
        self.inv = torch.from_numpy(inv).to(DEV)
        self.n = len(self.karten)

    def suche(self, q, k=10):  # q: (B, D) float, normalisiert -> je Bild Top-k Karten (max über Alt-Arts)
        sim = q.half() @ self.emb.T  # (B, N)
        je_karte = torch.full((q.shape[0], self.n), -1.0, device=DEV, dtype=sim.dtype)
        je_karte.scatter_reduce_(1, self.inv.expand_as(sim), sim, reduce="amax")
        w, i = je_karte.float().topk(k, dim=1)
        return [[(int(self.karten[j]), round(float(s), 4)) for s, j in zip(ws, js)] for ws, js in zip(w.cpu(), i.cpu())]


# ---------- Bilder ----------
def detektor():
    return YOLO(hf_hub_download("HichTala/draw2", "ygo_yolo.pt"))


def ecken_ordnen(p):
    """4 Ecken -> oben-links, oben-rechts, unten-rechts, unten-links; Karte steht hochkant."""
    p = np.asarray(p, dtype=np.float32)
    c = p.mean(0)
    winkel = np.arctan2(p[:, 1] - c[1], p[:, 0] - c[0])
    p = p[np.argsort(winkel)]  # beginnend links-oben im Uhrzeigersinn (Bildkoordinaten)
    # Start = Ecke mit kleinster x+y
    s = int(np.argmin(p.sum(1)))
    p = np.roll(p, -s, axis=0)
    # Querformat -> um 90° drehen, damit die lange Seite senkrecht ist
    breite = np.linalg.norm(p[1] - p[0]); hoehe = np.linalg.norm(p[3] - p[0])
    if breite > hoehe:
        p = np.roll(p, -1, axis=0)
    return p


def gerade(bild_bgr, ecken, groesse):
    w, h = groesse
    ziel = np.float32([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]])
    M = cv2.getPerspectiveTransform(ecken, ziel)
    return cv2.warpPerspective(bild_bgr, M, (w, h), flags=cv2.INTER_LINEAR)


def finde(yolo, bilder_bgr):
    res = yolo.predict(bilder_bgr, verbose=False, device=0, half=True, conf=0.05)
    out = []
    for r in res:
        if r.obb is None or len(r.obb.conf) == 0:
            out.append(None); continue
        j = int(r.obb.conf.argmax())
        out.append((float(r.obb.conf[j]), ecken_ordnen(r.obb.xyxyxyxy[j].cpu().numpy())))
    return out


def kalibrier_clips():
    m = [json.loads(l) for l in open(EVAL / "manifest/manifest.jsonl", encoding="utf-8")]
    return [c for c in m if c["teil"] == "kalibrier"]


def schritt_bilder():
    clips = kalibrier_clips()
    yolo = detektor()
    encs = {v: Encoder(v) for v in VARIANTEN}
    idx = {v: Index(v) for v in VARIANTEN}
    (ARBEIT / "passcode").mkdir(exist_ok=True)
    (ARBEIT / "karten").mkdir(exist_ok=True)
    ziel = open(ARBEIT / "bilder.jsonl", "w", encoding="utf-8")
    t0, n = time.time(), 0
    for c in clips:
        meta = {json.loads(l)["i"]: json.loads(l) for l in open(EVAL / f"aufnahmen/{c['aufnahme']}/frames.jsonl", encoding="utf-8")}
        nrn = list(range(c["von"], c["bis"] + 1))
        for s in range(0, len(nrn), 32):
            teil = nrn[s:s + 32]
            bgr = [cv2.imread(str(EVAL / f"aufnahmen/{c['aufnahme']}/{i:06d}.jpg")) for i in teil]
            funde = finde(yolo, bgr)
            karten_hoch, gefunden = [], []
            for i, b, f in zip(teil, bgr, funde):
                if f is None: continue
                k = cv2.cvtColor(gerade(b, f[1], HOCH), cv2.COLOR_BGR2RGB)
                karten_hoch.append(k); gefunden.append((i, f))
                pc = ausschnitt(k, PASS)
                cv2.imwrite(str(ARBEIT / f"passcode/{c['aufnahme']}-{i:06d}.png"), cv2.cvtColor(pc, cv2.COLOR_RGB2BGR))
                if i == c["liegt_ruhig"]:
                    cv2.imwrite(str(ARBEIT / f"karten/{c['clip'].replace('/', '-')}.jpg"), cv2.cvtColor(k, cv2.COLOR_RGB2BGR))
            treffer = {}
            if karten_hoch:
                for v in VARIANTEN:
                    q = encs[v]([eingabe(v, k) for k in karten_hoch])
                    treffer[v] = idx[v].suche(q)
            fund_nr = {i: j for j, (i, _) in enumerate(gefunden)}
            for i, f in zip(teil, funde):
                zeile = {"clip": c["clip"], "i": i, "t_ms": meta[i]["t_aufnahme_ms"], "schaerfe": meta[i].get("schaerfe"),
                         "det": None if f is None else round(f[0], 3)}
                if i in fund_nr:
                    zeile["ecken"] = np.round(f[1], 1).tolist()
                    zeile["top"] = {v: treffer[v][fund_nr[i]] for v in VARIANTEN}
                ziel.write(json.dumps(zeile) + "\n")
                n += 1
        print(f"{c['clip']}: {n} Bilder, {time.time() - t0:.0f} s", flush=True)
    ziel.close()


def schritt_tempo():
    """Latenz je Bild wie im Dienst: JPEG dekodieren, finden, gerade ziehen, einbetten, kNN. Batch 1."""
    clips = kalibrier_clips()
    yolo, enc, idx = detektor(), Encoder("draw2-karte"), Index("draw2-karte")
    dateien = [(EVAL / f"aufnahmen/{c['aufnahme']}/{i:06d}.jpg") for c in clips[:20] for i in range(c["von"], c["bis"] + 1)]
    zeiten = []
    for n, d in enumerate(dateien[:1100]):
        roh = d.read_bytes()
        torch.cuda.synchronize(); t = time.perf_counter()
        b = cv2.imdecode(np.frombuffer(roh, np.uint8), cv2.IMREAD_COLOR)
        f = finde(yolo, [b])[0]
        if f is not None:
            k = cv2.cvtColor(gerade(b, f[1], (224, 224)), cv2.COLOR_BGR2RGB)
            idx.suche(enc([k]))
        torch.cuda.synchronize()
        if n >= 100: zeiten.append((time.perf_counter() - t) * 1000)  # erste 100 = Aufwärmen
    z = np.array(zeiten)
    erg = {"n": len(z), "p50_ms": float(np.percentile(z, 50)), "p95_ms": float(np.percentile(z, 95)),
           "p99_ms": float(np.percentile(z, 99)), "vram_mb": torch.cuda.max_memory_allocated() / 2**20,
           "gpu": torch.cuda.get_device_name(), "arch": torch.cuda.get_arch_list(), "torch": torch.__version__}
    json.dump(erg, open(ARBEIT / "tempo.json", "w"), indent=1)
    print(erg)


if __name__ == "__main__":
    {"katalog": schritt_katalog, "bilder": schritt_bilder, "tempo": schritt_tempo}[sys.argv[1]]()
