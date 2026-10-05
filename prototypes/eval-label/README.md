# Label-Werkzeug fürs Eval-Set (Wegwerf)

Prototyp zu [Eval-Set aufnehmen und labeln](https://github.com/DoenerbudenAli/yugioh-collection/issues/47), Regeln in ADR 0008. Kein Modulcode, keine Tests. Läuft nur auf dem Heimrechner, weil dort `eval-daten/` liegt.

```bash
python prototypes/eval-label/werkzeug.py
```

Danach <http://127.0.0.1:8770> öffnen. Der Ordner `eval-daten/` liegt neben dem Clone. Ein anderer Ort lässt sich über `EVAL_DATEN` setzen.

Ablauf:

1. **Stapel:** Karten in Scan-Reihenfolge erfassen, per Passcode oder Name. Alt-Arts wählt man über das Vorschaubild.
2. **Labeln:** Die Aufnahme der Kamera-Sonde (`https://sonde.kiwi7.de/?eval`) vom Pi holen. Das Werkzeug schlägt die Clip-Grenzen über Schärfe und Bewegung vor, du korrigierst sie über die Tasten.
3. **Übersicht:** Quoten prüfen und „Manifest bauen“ drücken.

## Vorläufiges Manifest-Format

Dieses Format übernimmt [Eval-Gerüst: Manifest, Spuren und Eval-Quittung als Gate](https://github.com/DoenerbudenAli/yugioh-collection/issues/54). Pfade sind relativ zu `eval-daten/`.

- `manifest/bilder.sha256`: eine Zeile je Bild im Format von `sha256sum` (`<hash>  aufnahmen/<ordner>/<datei>`), prüfbar mit `sha256sum -c`.
- `manifest/manifest.jsonl`: eine Zeile je Clip.

| Feld | Bedeutung |
|---|---|
| `clip` | `<aufnahme>/<nr>`, eindeutig |
| `aufnahme`, `von`, `bis` | Ordner der Aufnahme und Bildindizes des Clips (inklusive) |
| `liegt_ruhig`, `ist_weg` | Bildindex „liegt ruhig“ (erstes Bild, in dem die Karte ganz im Bild ist und nicht mehr geschoben oder gedreht wird; Finger auf der Karte und Wackeln des Handys zählen nicht) und erster Index „ist weg“ |
| `liegt_geprueft` | `true`, wenn der Owner „liegt ruhig“ von Hand bestätigt hat (Pflicht außer bei Störclips) |
| `exemplar` | Exemplar-ID `S<stapel>-<nr>`; dasselbe Exemplar in jeder Haltung und Hülle gleich, `null` bei Störclips ohne Karte |
| `teil` | `kalibrier` oder `pruef`, je Exemplar 50/50 geschichtet nach Schichten |
| `passcode`, `ygoprodeck_id` | Passcode der Karte (= YGOProDeck-ID); `null`, wenn nicht im Katalog |
| `art_variante` | YGOProDeck-Bild-ID des Artworks |
| `name` | Anzeigename (nur zur Lesbarkeit) |
| `sprache` | `de`, `en`, `andere` |
| `glanz` | `kein` (auch Rare: nur der Name glänzt), `bild` (Artwork glänzt: Super, Ultra, Secret …), `ganz` (ganze Karte: Ghost, Starlight, Ultimate, Collector's …); nur für die Erkennbarkeit, keine Seltenheit |
| `proxy` | `null`, `ygoprodeck-bild`, `scan`, `eigen` |
| `haltung` | `frei`, `halterung` |
| `licht` | `normal`, `abend` |
| `huelle` | `mit`, `ohne` |
| `nicht_im_katalog` | `true` für Token, Skill, Rush Duel, OCG-only |
| `schichten` | abgeleitete Schichten aus ADR 0008 (Deutsch, Foils, Alt-Arts …) |
| `stoerung` | `null`, `hand`, `halb`, `verwackelt`, `leer` |

Clips werden nur angehängt. Eine neue Aufnahme bringt neue Zeilen, eine alte Aufnahme wird nie überschrieben.
