# Erkennungs-Spike – Ergebnis (PROTOTYP, Wegwerf-Branch)

Ticket: [Erkennungs-Spike: Treffer, Tempo und Schwellen am Eval-Set](https://github.com/DoenerbudenAli/yugioh-collection/issues/60). Stand 2026-10-05. Gemessen nur am **Kalibrier-Teil** (137 Clips, 66 Exemplare, 6.940 Bilder). Der Prüf-Teil wurde nicht gelesen.

## Aufbau

- Docker-Image `erkennungs-spike` (PyTorch 2.14.1+cu130, sm_120 vorhanden), `eval-daten/` nur lesend als `/eval`, Arbeitsordner `spike-arbeit/` außerhalb von Git als `/arbeit`.
- Katalog: alle 14.769 YGOProDeck-Vollbilder (`katalog_laden.py`) nach `eval-daten/katalog/bilder-voll/`.
- Je Bild (`merkmale.py`): DRAW2-YOLO-OBB findet die Karte (640 px, Fund ab 0,05, in der Simulation ab 0,25), Perspektive gerade ziehen, einbetten, Brute-Force-kNN auf der GPU, Maximum über Alt-Arts je Karte.
- Varianten: DRAW2 ganze Karte, DRAW2 Artwork-Ausschnitt, DINOv2-S, DINOv2-B (jeweils 224×224).
- `ocr.py`: EasyOCR nur Ziffern auf dem Passcode-Fenster unten links (eng und weit).
- `leer.py`: Anteil der Pixel, die nicht wie der helle Tisch aussehen („Unruhe“).
- `sim.py`: Port des Reducers `ScanAblauf` aus `prototype/scan-ux`, Zeiten in ms, gedrosselte Bildrate; Gittersuche über die Schwellen. `auswertung.py`, `fehler.py`, `beste.py`: Auswertungen.

Aufruf (aus diesem Ordner):

```
docker build -t erkennungs-spike .
docker run --rm --gpus all -v <eval-daten>:/eval:ro -v <spike-arbeit>:/arbeit -v .:/spike erkennungs-spike python merkmale.py katalog|bilder|tempo
python sim.py <spike-arbeit> <eval-daten> draw2-karte
```

## Zahlen

**Encoder, je Bild im Liegefenster** (Karten im Katalog, ohne Störclips sinngemäß):

| Variante | Top-1 alle Bilder* | Trefferquote bei 0 Falsch-Akzeptanz | höchste Ähnlichkeit eines falschen Top-1 |
|---|---|---|---|
| DRAW2 ganze Karte | 0,81 (≈ 0,90 ohne „nicht im Katalog“) | 0,77 | 0,42 |
| DRAW2 Artwork | 0,83 | 0,77 | 0,54 |
| DINOv2-S | 0,49 | 0,04 | 0,79 |
| DINOv2-B | 0,57 | 0,02 | 0,83 |

\* inklusive der 160 Bilder von Karten, die nicht im Katalog sind (dort ist Top-1 per Definition falsch).

DRAW2 ganze Karte je Schicht (Top-1): Deutsch 0,84, Englisch 0,80, Foils 0,80, Ghost/Starlight/Ultimate 0,93, ähnliche Artworks 0,88, Proxies 0,87, Alt-Arts 1,00. Mit Halterung 0,74, freihändig 0,84. Fehler sitzen fast nur in Störclips (halb im Bild, verwackelt) und in einzelnen Bewegungsbildern. Richtige Treffer: Ähnlichkeit p5 0,40, Median 0,82.

**Tempo** (Batch 1 wie im Dienst: JPEG dekodieren, finden, gerade ziehen, einbetten, kNN): p50 11 ms, p95 14 ms, p99 15 ms, 330 MB VRAM. Index-Aufbau für den vollen Katalog: 217 s je Variante (Engpass JPEG-Dekodieren über den Windows-Mount).

**Passcode-OCR:** ≈ 0,3 % je Bild, wenige Clips, keine Falschlesung. Ziffern sind im Bild 8–10 px hoch und oft vom Finger verdeckt. Weites Fenster aus dem Originalbild ändert nichts.

**Detektor:** Liegt-ruhig-Bilder gefunden: frei 100 %, Halterung 95 % (bei Fund-Schwelle 0,05). Leere Bilder mit Fehlfund: 1 %. Mit 1024 px findet er in 90 % der leeren Bilder etwas → 640 px.

**Liegezeit** (liegt ruhig → ist weg, ohne Ton bei der Aufnahme): frei p5 760 ms / Median 1.260 ms; Halterung p5 320 ms / Median 617 ms. Aufnahme-Bildrate meist ~20/s, teils 7–13/s.

**Scan-Ablauf** (DRAW2 ganze Karte, „weg“ erst bei leerem Tisch, Unruhe < 0,15, 1 leeres Bild, Zeitlimit 1.200 ms, Bremse 1.000 ms):

| Regel | Bilder/s | frei: Auto / p95 ab liegt ruhig | Halterung: Auto / p95 |
|---|---|---|---|
| 1 Bild ≥ 0,45 | 8 | 100 % / 60 ms | 91 % / 328 ms |
| **2 Bilder ≥ 0,45** | **8** | **98 % / 195 ms** | **80 % / 465 ms** |
| 2 Bilder ≥ 0,45 | 20 | 98 % / 137 ms | 89 % / 456 ms |
| 2 Bilder ≥ 0,40 | 8 | 100 % / 195 ms | 87 % / 380 ms, **1 Falschbuchung** |
| 3 Bilder ≥ 0,45 | 8 | 95 % / 365 ms | 61 % / 716 ms |

In allen Zeilen außer der markierten: 0 Falsch-, 0 Doppelbuchungen. Halterung verliert Prozente, weil die Karte ohne Ton oft vor der Entscheidung weggenommen wurde und weil sie kleiner im Bild ist (Ähnlichkeit 0,3–0,5). Ice Barrier (Halterung) fand der Detektor nie → kein Scan.

Ohne die Tisch-Prüfung bei „weg“ entstehen Doppelbuchungen, wenn eine Hand die Karte verdeckt (Störclips „hand“).

## Entscheidung (Owner, 2026-10-05)

- DRAW2 ganze Karte, Buchung nach **2 sicheren Bildern ≥ 0,45**.
- Passcode-OCR entfällt im MVP.
- Latenz-Ziel: p95 ≤ 500 ms ab „liegt ruhig“ je Haltung bei 8 Bildern/s.
- Halterung: Karte bis zum Ton liegen lassen.
- Findet der Detektor keine Karte, entsteht kein Scan. Der Owner legt die Karte ohne Ton zur Seite („unerkannt“, kein Blocker).
- Plan B Cloud: nicht nötig.
