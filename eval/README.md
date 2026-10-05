# Eval-Set: Manifest

Das Manifest des Eval-Sets der Erkennung ([ADR 0008](../docs/adr/0008-eval-set.md)). Die Fotos liegen nicht im Repo, sondern in `eval-daten/` auf dem Heimrechner. Die Dateien hier beschreiben und schützen sie. Alle drei Dateien sind Kern.

- `manifest.jsonl`: eine Zeile je Clip mit Labels und Zuordnung zum Kalibrier- oder Prüf-Teil.
- `bilder.sha256`: SHA-256 jedes Bildes, relativ zu `eval-daten/`. Geprüft wird in `eval-daten/` mit `sha256sum -c bilder.sha256`.

Das Format ist vorläufig. Es stammt aus [Eval-Set aufnehmen und labeln](https://github.com/DoenerbudenAli/yugioh-collection/issues/47) und wird vom [Eval-Gerüst](https://github.com/DoenerbudenAli/yugioh-collection/issues/54) übernommen. Erzeugt wurde es mit dem Label-Werkzeug auf dem Branch `prototype/eval-label`.

## Felder in `manifest.jsonl`

| Feld | Bedeutung |
|---|---|
| `clip` | `<aufnahme>/<nr>`, eindeutig |
| `aufnahme`, `von`, `bis` | Ordner unter `eval-daten/aufnahmen/` und Bildindizes des Clips (inklusive) |
| `liegt_ruhig` | erstes Bild, in dem die Karte ganz im Bild ist und nicht mehr geschoben oder gedreht wird; Finger auf der Karte und Wackeln des Handys zählen nicht |
| `liegt_geprueft` | `true`, wenn der Owner `liegt_ruhig` von Hand bestätigt hat (Pflicht außer bei Störclips) |
| `ist_weg` | erstes Bild ohne die Karte (Vorschlag des Werkzeugs, auf 1–2 Bilder genau) |
| `exemplar` | Exemplar-ID `S<stapel>-<nr>`, in jeder Haltung gleich; `null` bei Störclips ohne Karte |
| `teil` | `kalibrier` oder `pruef`, je Exemplar 50/50 geschichtet |
| `passcode`, `ygoprodeck_id` | Passcode der Karte (= YGOProDeck-ID), `null`, wenn nicht im Katalog |
| `art_variante` | YGOProDeck-Bild-ID des Artworks |
| `name` | Anzeigename, nur zur Lesbarkeit |
| `sprache` | `de`, `en`, `andere` |
| `glanz` | `kein` (auch Rare), `bild` (Artwork glänzt), `ganz` (Ghost, Starlight, Ultimate …); beschreibt die Erkennbarkeit, nicht die Seltenheit |
| `proxy` | `null` oder `ygoprodeck-bild` (`scan` und `eigen` kommen im Set nicht vor) |
| `haltung` | `frei`, `halterung` |
| `licht` | `normal` |
| `huelle` | `mit`, `ohne` |
| `nicht_im_katalog` | `true` für Token und Skill |
| `schichten` | abgeleitete Schichten aus ADR 0008 |
| `stoerung` | `null`, `hand` (Hand über der Karte bzw. nur Hand), `halb` (halb im Bild), `verwackelt`, `leer` (nur Unterarm) |
| `notiz` | Sonderfälle, z. B. „überdeckt von der nächsten Karte“ oder „nur Hand, keine Karte“ |

## Stand

277 Clips mit 14.039 Bildern (797 MB) von 132 Exemplaren, aufgenommen am 2026-10-05 mit dem Pixel 7 Pro in Firefox über die Kamera-Sonde. Kalibrier- und Prüf-Teil haben je 66 Exemplare. Wo das Set von den Quoten in ADR 0008 abweicht, steht im Ticket.
