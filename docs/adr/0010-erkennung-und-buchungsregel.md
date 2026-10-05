# Erkennung und Buchungsregel nach dem Spike

Status: akzeptiert
Präzisiert: ADR 0008

Der [Erkennungs-Spike](https://github.com/DoenerbudenAli/yugioh-collection/issues/60) hat die Erkennung am Kalibrier-Teil des Eval-Sets gemessen. Daraus folgt: Die Erkennung nutzt **DRAW2-Embeddings der ganzen Karte** mit kNN gegen den vollen Katalog. Gebucht wird nach **zwei sicheren Bildern in Folge**. **Passcode-OCR entfällt**, und das **Latenz-Ziel gilt je Haltung bei mindestens 8 Bildern/s**. Wir haben uns so entschieden, weil DRAW2 bei null Falsch-Akzeptanzen 77 % der Bilder trägt (DINOv2: 2–4 %). Ein Bild allein läge nur 0,03 über dem höchsten Fehltreffer. Die Passcode-Ziffern sind im Kamerabild nur 8–10 px hoch, die Lesequote liegt bei ≈ 0,3 %. Die Rechenzeit (p95 14 ms je Bild auf der RTX 5080) spielt fürs Budget keine Rolle, also auch keine Cloud-Erkennung. Zahlen und Messaufbau: `prototypes/erkennungs-spike/ERGEBNIS.md` auf dem Branch `prototype/erkennungs-spike`.

## Regeln

- **Erkennung:** Detektor (DRAW2-YOLO, orientierte Box) findet die Karte, Perspektive gerade ziehen, DRAW2 auf der ganzen Karte (224 × 224), Ähnlichkeit gegen alle Katalogbilder, Maximum je Karte über die Alt-Arts. Kein Artwork-Ausschnitt, kein DINOv2.
- **Buchung:** zwei Bilder in Folge mit derselben Top-Karte und Ähnlichkeit ≥ 0,45. Die Zahlen stehen in der Parameterdatei der Erfassung (ADR 0006). Der Weg „Passcode bestätigt“ aus der Scan-UX entfällt.
- **Bild verlassen:** Ein Bild ist nur dann leer, wenn keine Karte gefunden wird **und** der Tisch sichtbar ist. Findet der Detektor keine Karte, aber das Bild ist nicht leer (Hand, Arm), zählt das Bild weder als Karte noch als leer. Ohne diese Unterscheidung bucht eine Hand über der Karte doppelt.
- **Unerkannt:** Findet der Detektor nie eine Karte, entsteht kein Scan. Kommt kein Ton, legt der Owner die Karte zur Seite. Das ist kein verlorenes Exemplar.
- **Halterung:** Die Karte bleibt liegen, bis der Ton kommt.

## Änderungen an ADR 0008

| Metrik | bisher | neu |
|---|---|---|
| verlorene Exemplare | 0, Blocker | 0, Blocker. Zählt nur Exemplare, für die die Erkennung Kandidaten lieferte |
| unerkannte Exemplare | – | nur gemessen, kein Ziel |
| Zeit bis zur Buchung ab „liegt ruhig“ | p95 < 500 ms | p95 ≤ 500 ms **je Haltung, bei 8 Bildern/s** |
| Passcode-Lesequote | nur gemessen | entfällt |

- Eine **Spur** hält je Bild die Top-k Karten mit Konfidenz und die Flags „Karte gefunden“ und „Tisch sichtbar“ fest. Einen gelesenen Passcode gibt es nicht mehr.
- Die Simulation bei 8 Bildern/s entsteht durch Ausdünnen der Clips nach Zeitstempel.

## Konsequenzen

- Am Kalibrier-Teil (8 Bilder/s): frei 98 % automatisch, p95 195 ms; Halterung 80 %, p95 465 ms; keine Falsch-, Doppel- oder verlorenen Buchungen. Die Halterung ist im Eval-Set unterschätzt, weil ohne Ton aufgenommen wurde und die Karte oft vor der Entscheidung wegging. Ob „bis zum Ton liegen lassen“ die 95 % erreicht, zeigen erst Clips mit Ton.
- Neue Karten brauchen nur ein Referenzbild im Index, kein Training.
- Mit Halterung ist die Karte klein im Bild (Ähnlichkeit oft 0,3–0,5). Eine tiefere Halterung ist der erste Hebel, falls die Quote nicht reicht.

## Verworfene Alternativen

- **Ein sicheres Bild bucht:** schneller (frei p95 60 ms) und mehr Auto, aber der Abstand zum höchsten Fehltreffer ist auf 137 Clips zu dünn, und „einzelne Bilder buchen nie“ aus der Scan-UX fiele weg.
- **Schwelle 0,40 bei zwei Bildern:** mehr Auto mit Halterung, aber eine Falschbuchung schon am Kalibrier-Teil.
- **Passcode-OCR als Nebenweg:** liest fast nichts, bei dieser Auflösung auch nicht mit größerem Fenster.
- **Prüf-Eintrag „nicht erkannt“**, wenn etwas im Bild lag, aber keine Karte gefunden wurde: vom Owner verworfen. Der fehlende Ton reicht ihm als Signal.
- **DINOv2 oder Artwork-Ausschnitt:** DINOv2 trennt nicht. Der Artwork-Ausschnitt hat höhere Fehltreffer (bis 0,54) bei kaum besserem Top-1.
