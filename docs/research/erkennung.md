# Erkennung unter 1 s: welche Ansätze sind realistisch?

Research zu Issue #3. Stand: 2026-10-04. Begriffe nach `CONTEXT.md` (**Karte**, **Exemplar**, **Proxy**, **Scan**, **Prüf-Warteschlange**, **Katalog**).

Alle Zahlen stammen aus der jeweils verlinkten Primärquelle. Was keine Quelle hat, ist als **Schätzung** markiert. Mehrere Kernzahlen kommen aus einem einzigen, sehr jungen Open-Source-Projekt ([Adrian-Sandwich/yugioh-ar](https://github.com/Adrian-Sandwich/yugioh-ar), Commit-Stand 2026-10-03). Es dokumentiert seine Messungen ausführlich, ist aber nicht unabhängig reproduziert.

## Kurzfazit und Empfehlung

**Unter 1 s Ende-zu-Ende ist mit dem Heimrechner gut machbar.** Die Rechenzeit liegt im Bereich von zehn bis wenigen hundert Millisekunden. Das Budget fressen vor allem zwei Dinge: das Warten auf ein scharfes, stabiles Bild und die Bestätigung über mehrere Frames. Die eigentliche Unsicherheit ist die **Trefferquote auf echten Handyfotos eigener Karten**, nicht die Latenz.

Priorisierte Shortlist:

1. **Kombination als Zielbild:** Karte erkennen und entzerren, dann **Bild-Embedding mit Nearest Neighbor** gegen den ganzen Katalog als Hauptweg. Dazu **Passcode-OCR** als hochpräziser Bestätiger und **Namens-OCR (DE/EN)** als Stichentscheid bei knappen Fällen. Gebucht wird erst, wenn 2–3 Frames übereinstimmen. Alles unter der Schwelle geht in die Prüf-Warteschlange. So arbeitet das ausgereifteste offene Yu-Gi-Oh-Projekt (yugioh-ar). Es meldet 99,3 % Top-1 auf 4.000 Händler-Scans gegen 14.278 Katalog-Identitäten und **0 falsch akzeptierte** bei 96,2 % automatisch akzeptierten.
2. **Passcode-OCR allein als schneller erster Prototyp:** Der Passcode ist sprachunabhängig, für alle Drucke und Alt-Arts gleich und per Exakt-Lookup eindeutig. Das Verfahren ist billig, präzise und auch auf Pixel oder Pi denkbar. Es hat aber harte Lücken: Proxies aus YGOProDeck-Bildern haben **keinen** Passcode, 67 legale Karten wurden ohne Passcode gedruckt, und die Ziffern sind winzig (~1,5 % der Kartenhöhe). Als **alleinige** Methode reicht es daher nicht.
3. **Artwork-Embedding ohne OCR** als zweiter Prototyp. Es deckt Proxies mit Originalartwork und Karten ohne Passcode ab. Ein generisches DINOv2 ordnet die Kandidaten gut, trennt aber fremde Karten schlecht vom Treffer. Ein auf Yu-Gi-Oh trainierter Encoder (DRAW2-ViT, AGPL-3.0) oder eigenes Fine-Tuning war im Vergleich deutlich besser.
4. **Nicht als Hauptweg:** Perceptual Hash (keine belastbaren Zahlen bei 14k Katalog, empfindlich für Zuschnitt und Reflexe) und Namens-OCR allein (Foil-Titel, 2.493 TCG-Karten ohne deutschen Namen bei YGOProDeck).
5. **Cloud als Plan B:** OCR über Google Vision ist sehr billig (rund 6 USD für 5k Scans, **Schätzung**). Ximilar bietet eine fertige Yu-Gi-Oh-Identifikation mit Spracherkennung. Latenz und Preis pro Aufruf sind dort für unseren Fall aber ungeklärt. Das Budget von 1 s wird dabei eng (**Schätzung**).

**Was das Eval-Set zuerst messen sollte:** (a) die Lesequote des Passcodes in der realen Haltung beim Scannen und bei der realen Analyseauflösung, (b) die **Falsch-Akzeptanzrate** des Embedding-Wegs auf deutschen Karten, Foils und Proxies gegen den vollen Katalog, (c) die Zeit bis zur Entscheidung mit Frame-Konsens. Details stehen unten.

## Vergleichstabelle der Ansätze

| Ansatz | Erwartbare Trefferquote | Rechenzeit RTX 5080 | Pi | Cloud | Proxies | Altkarten | Foil | Alt-Arts | DE/EN | Aufwand |
|---|---|---|---|---|---|---|---|---|---|---|
| **Passcode-OCR + Exakt-Lookup** | Wenn gelesen: praktisch eindeutig. **Abdeckung unbekannt.** Live-Test bei yugioh-ar: Ziffern mit 6 px unlesbar ([1]) | Nur Ziffernzeile: ~0,1–0,6 s auf CPU ([1]); GPU/ML Kit deutlich weniger (**Schätzung**) | Machbar, Erkennung nur auf dem Ausschnitt (**Schätzung**: 0,1–0,5 s) | Google Vision Text 1,50 USD/1000 ([9]) | **Scheitert** bei Prints aus YGOProDeck-Bildern (dort steht „Replica …“ statt Passcode, [10]). Klappt bei Scans echter Karten | 67 legale Karten ohne Passcode ([11]) | Reflex auf der Ziffernzeile möglich; nicht gemessen | Gleicher Passcode für alle Arts, bis auf 2 Ausnahmen ([11]) | Sprachneutral ([11]) | **Klein** |
| **Namens-OCR (DE/EN) + Fuzzy-Match** | Mittel. Bei yugioh-ar 2 von 4 Testkarten korrekt gelesen ([2]); 0 falsche Karten in 1.885 *simulierten* Fehllesungen ([3]) | ~0,1 s pro Name auf CPU ([2]) | Machbar (**Schätzung**) | wie oben | Klappt, solange der Name lesbar ist | Klappt | Ghost/Starlight: Titel schwer lesbar ([3]) | Kein Problem | **2.493 von 14.106 TCG-Karten ohne DE-Namen bei YGOProDeck** (eigene Auswertung, [10]) | Mittel |
| **Bild-Embedding + kNN (ganze Karte oder Artwork)** | Hoch auf Scans: 99,3 % Top-1, 96,2 % auto-akzeptiert, 0 falsch ([4]). Auf echten Fotos nur 16 Karten getestet (16/16 Top-1) ([4]). Pokémon-Vergleich auf echten Fotos: 85,1 % Top-1 offen, 96,4 % bei bekanntem Deck ([12]) | Detektor 12 ms + Encoder 15 ms für 9 Karten auf RTX 4070 ([4]); Suche über 14k Vektoren vernachlässigbar ([5]) | ViT-B: ~0,5 s pro Bild schon auf Laptop-CPU ([4]), Pi langsamer (**Schätzung** ≥1 s); kleines Modell nötig | Ximilar tcg_id ([13]) | Gleiches Artwork: gut (**Schätzung**). Eigene Artworks: scheitert | Artwork gleich: gut (**Schätzung**) | Schwachstelle: Starlight/Ultimate ([4], [6]) | Ein Referenzbild pro Art nötig (YGOProDeck: 14.769 Bilder für 14.597 Karten, [10]) | Volle Karte: Referenzen sind englisch (Textabweichung). Artwork-Ausschnitt: sprachneutral | Mittel; mit Fine-Tuning groß |
| **Perceptual Hash** | Für Yu-Gi-Oh mit 14k Katalog **keine Zahlen** gefunden. MTG-Prototyp nur mit ~300 Karten, ohne Metriken ([14]) | ms (**Schätzung**) | Ja | – | Gleiches Artwork: ok | ok | Empfindlich ([14]: Licht, Verdeckung) | wie Embedding | wie Embedding | Klein |
| **Lokale Merkmale (SIFT/ORB) als Verifikation** | Zweitstimme. Bei yugioh-ar bestätigt sie Foils, die das Embedding knapp ablehnt ([5]) | Zehn bis hundert ms CPU (**Schätzung**) | Ja | – | Gleiches Artwork: ok | ok | **Hilft** ([5]) | Gegen das exakte Art | Sprachneutral (auf Artwork) | Mittel |
| **Cloud-Vision-API (Plan B)** | Ximilar wirbt mit 99,9 %, nicht unabhängig belegt ([15]) | – | – | Upload + Round-Trip ins Internet, ~0,3–1 s (**Schätzung**) | unbekannt | unbekannt | Ximilar meldet Holo-Erkennung ([15]) | unbekannt | Ximilar: Spracherkennung Latein inkl. Deutsch ([13]) | Klein (Integration), laufende Kosten |

Kartendetektion und Perspektivkorrektur sind kein eigener Erkenner. Sie sind Voraussetzung für alle Zeilen, siehe Abschnitt 4.

## Befunde mit Quellen

### 1. Katalog und Referenzbilder (YGOProDeck)

- Abruf des vollen Katalogs am 2026-10-04 über `cardinfo.php`, Datenbankversion 147.22 vom 2026-10-02: **14.597 Karten** und **14.769 Bilder**. Davon haben 125 Karten mehr als ein Artwork, 14.106 haben TCG-Sets ([10], eigene Auswertung).
- YGOProDeck liefert Bilder in drei Größen: volle Karte 813×1185, klein 268×391, Artwork-Ausschnitt 624×624 (Pixelmaße selbst ausgelesen). Bilder sollen einmal heruntergeladen und selbst gehostet werden. Dauerndes Hotlinking führt zur IP-Sperre. Das Rate-Limit liegt bei 20 Anfragen pro Sekunde ([10]).
- **Wichtig:** Die Kartenbilder sind **englische Nachbauten, keine Scans**. Unten links steht „Replica - Not For Use in Sanctioned Tournaments.“ statt Passcode. Set-Code und Edition fehlen (geprüft an Dark Magician 46986414, Alt-Art 36996508 und Ash Blossom 14558127). Folgen:
  - Referenzbilder sind immer englisch, flach und ohne Foil. Echte deutsche Karten weichen bei Name und Text ab.
  - **Proxies, die aus YGOProDeck-Bildern gedruckt wurden, tragen keinen Passcode.**
- Alt-Arts liegen im Array `card_images` mit eigenen Bild-IDs ([10]). Diese IDs sind teils **YGOProDeck-intern und keine Passcodes**: Dark Magician hat die Bild-IDs 46986414–46986421 und 36996508. Bild-IDs müssen also auf die Karte gemappt werden, ein Bild ist kein Passcode. yugioh-ar hält ausdrücklich fest: „Un ID de imagen no es evidencia de passcode“ ([1]).
- Mit `language=de` gibt es deutsche Namen für **11.769** Karten. **2.493 der 14.106 Karten mit TCG-Sets haben keinen deutschen Namen** (eigene Auswertung, [10]), darunter Karten aus *Duelist Nexus* (2023). Für Namens-OCR auf deutschen Karten reicht YGOProDeck daher nicht. Die offizielle Konami-Datenbank führt mehrsprachige Namen ([11]), ob und wie sie sich nutzen lässt, ist offen.
- yugioh-ar fand doppelte Identitäten im Katalog, also dieselbe physische Karte unter altem OCG- und neuem TCG-Namen, etwa „Crackle Blitzclique“ / „Crack Blitzclique“ ([4]). Der Katalog braucht deshalb eine Deduplizierung, sonst entstehen unechte Mehrdeutigkeiten.

### 2. Passcode

- Achtstellig, unten links auf legalen OCG/TCG-Karten, **in allen Sprachen und Drucken gleich, auch bei Alt-Arts**. Ausnahmen: zwei Karten mit alternativem Passcode und eine Einzelkarte. Es gibt **67 legale Karten**, die nur oder teilweise ohne Passcode gedruckt wurden (z. B. Ägyptische Götter, frühe Drucke). Token, Skill-Karten, Giant Cards und **Official Proxies** haben nie einen Passcode ([11]).
- In der YGOProDeck-API stehen Passcodes mit führender Null als 7-stellige Zahl (1.331 Karten). Beim Lookup muss man deshalb auf 8 Stellen auffüllen (eigene Auswertung, [10]). yugioh-ar lässt nur exakt 8 Ziffern zum Lookup zu und behält führende Nullen ([1]).
- **Lesbarkeit ist der Engpass:** Die Ziffernhöhe beträgt ~1,5 % der Kartenhöhe ([1]). ML Kit Text Recognition verlangt mindestens 16×16 px pro Zeichen, über 24 px bringt nichts mehr ([7]). Also muss die Karte im **Analysebild** mindestens etwa 1.070 px hoch sein (**Rechnung**: 16 / 0,015). Bei 1080p im Hochformat (1920 px Höhe) muss die Karte also mehr als gut die Hälfte der Bildhöhe füllen. Die Analyseauflösung muss explizit gesetzt werden, denn CameraX wählt sie sonst nach Hardware ([8]).
- Belege aus yugioh-ar: Im Live-Test mit Karten auf dem Tisch hatten die Ziffern 6,1–6,4 px, kein Passcode war lesbar. Auf einem Referenzfoto mit 710 px Kartenhöhe las RapidOCR (PP-OCRv6 rec small) „89631139“ korrekt, in ~602 ms für sechs Bildvarianten auf CPU ([1]).
- Das verwandte Set-Code-OCR auf Händler-Scans zeigt typische Glyphenverwechslungen (F→E, S→5, O→0, I→1) und bricht bei Foils ein: Ultimate 4 %, Starlight 12 %, Shatterfoil 13 % ([6]). Passcodes bestehen nur aus Ziffern, deshalb ist das Problem dort kleiner (**Schätzung**). Die Foil-Abhängigkeit ist für Passcodes nicht gemessen.
- Ein Android-Projekt nutzt genau diese Kaskade on-device: Passcode per ML Kit, dann pHash, dann Namens-Fuzzy-Match, Katalog mit über 14.000 Karten offline ([16]). Genauigkeit oder Latenz werden nicht veröffentlicht.

### 3. Bild-Embeddings und Nearest Neighbor

- **Bester Yu-Gi-Oh-Beleg** (yugioh-ar, Encoder = ViT aus DRAW2 in fp16 auf RTX 4070) ([4]):
  - Voller Katalog mit 14.278 Identitäten und 14.782 Referenzen: **99,3 % Top-1** auf 4.000 nach Seltenheit geschichteten TCGplayer-Scans.
  - Akzeptanzregel Ähnlichkeit ≥ 0,50 und Abstand zum Zweiten ≥ 0,25: **96,2 % korrekt akzeptiert, 0 falsch akzeptiert**.
  - Die 27 Top-1-Fehler betreffen fast nur Starlight und Ultimate Rare, alle fielen unter die Schwelle.
  - Echte Tischfotos: 16/16 Top-1, davon 15 akzeptiert. Das ist eine sehr kleine Stichprobe.
  - Die Autoren betonen, dass Scans **optimistischer** sind als Kamerafotos ([6]).
- **Latenz** (gleiche Quelle, RTX 4070): Für eine Szene mit 9 Karten braucht der Detektor 12 ms und der Encoder 15 ms. Die ganze Analyse liegt bei 137 ms p50 mit vollem Katalog. Live mit Handy-Stream, 10–12 Karten und Geometrie-Verfeinerung: 196 ms p50 und 261 ms p95. Die GPU war dabei nur zu 7 % ausgelastet, der Rest ist CPU-Geometrie ([4]). Bei **einer** Karte und einer RTX 5080 sind deutlich geringere Zeiten zu erwarten (**Schätzung**).
- **Generisches DINOv2 vs. spezialisierter Encoder** (gleicher Testaufbau) ([4]):
  - Recall bei 0 Falsch-Akzeptanzen: DINOv2 ViT-S/14 75,6 %, ViT-B/14 71,1 %, DRAW2-ViT 97,1 %.
  - 91–96 % der Negativbeispiele lagen bei DINOv2 über Ähnlichkeit 0,5. DINOv2 *ordnet* also gut, *trennt* aber schlecht. Ohne Fine-Tuning ist die Schwelle schwer zu setzen.
- Allgemein schlägt DINOv2 OpenCLIP beim Wiederfinden einzelner Objekte deutlich, z. B. Oxford-M mAP 72,9 (ViT-B/14) gegenüber 50,7 (OpenCLIP ViT-G/14) ([17]). Für CLIP gibt es keinen Yu-Gi-Oh-Beleg. DINOv2-Code und Gewichte stehen unter Apache-2.0, ViT-S/14 hat 21 M Parameter ([18]).
- **DRAW2** besteht aus einem YOLOv11-OBB-Detektor und einem ViT-Klassifikator (`google/vit-base-patch16-224-in21k`) für über 13.000 Klassen, trainiert auf YGOProDeck-Daten. Lizenz **AGPL-3.0**. Es gibt keine veröffentlichten Genauigkeitszahlen ([19], [20]).
  - Weil das Modell ein Klassifikator ist, deckt es neue Karten erst nach Neutraining ab: 13.659 bzw. 13.820 Labels gegenüber 14.597 Karten heute ([5]).
  - yugioh-ar nutzt deshalb die Repräsentation des Modells für kNN. So lassen sich neue Karten über Referenzbilder ergänzen ([5]).
- **Artwork-Ausschnitt statt ganzer Karte** (yugioh-ar, DRAW2-Encoder, 16 echte Ausschnitte) ([5]):
  - Gegen 14.249 Artworks: 16/16 Top-1, 11 akzeptiert, 0 falsch.
  - Die Ähnlichkeit ist aber niedriger als bei der ganzen Karte, ein Foil fiel von 0,63 auf 0,40, weil der Encoder auf ganzen Karten trainiert ist.
  - Für deutsche Karten ist der Artwork-Ausschnitt trotzdem interessant, weil er den englischen Text der Referenzen ausblendet (**Schätzung**). Gemessen ist das nicht.
- **Foils:** Der Embedding-Score fällt bei Foils unter die Schwelle. Eine SIFT-Verifikation gegen das exakte Artwork (≥ 30 Inlier, Abstand 2×) bestätigte die abgelehnten Fälle ([5]). Reflexentfernung per Netz (DocSHRNet, SHDocs) brachte in deren Test **keinen** Gewinn ([21]).
- **Weitere Vergleichspunkte:**
  - Lowhur (ResNet-101, Triplet-Loss, ORB-Re-Ranking) meldet ~99 % auf künstlich veränderten YGOProDeck-Bildern, aber nur „a handful“ echte Fotos ([22]).
  - TCG-AR (Pokémon, ArcFace) auf echten Fotos: 85,1 % Top-1 gegen den offenen Katalog, 96,4 % bei bekanntem Deck, 55 FPS ([12]). Das zeigt den typischen Abstand zwischen Scan- und Foto-Domäne.

### 4. Kartendetektion und Perspektivkorrektur

- Alle Verfahren profitieren von einem entzerrten Kartenausschnitt. yugioh-ar entzerrt aus dem Original-JPEG auf 630×920 und nicht aus der 224-px-Eingabe des Encoders ([1]).
- Die gedrehten Rechtecke des DRAW2-Detektors sind **nicht** die echten Ecken bei Perspektive. Eine Kantenverfeinerung ist nötig ([5]), sie war bei yugioh-ar der größte CPU-Kostenblock (~136 ms p50 live) ([4]).
- **Für unseren Fall** gilt: eine Karte, frontal in der Hand vor ruhigem Hintergrund. Dafür reicht wahrscheinlich eine klassische Viereck-Erkennung (Konturen, konvexe Hülle, 4-Punkt-Transformation) wie in [14] und [22] (**Schätzung**). Finger über den Ecken sind das Hauptrisiko.
- **On-device auf dem Pixel:**
  - CameraX `ImageAnalysis` liefert Frames mit `STRATEGY_KEEP_ONLY_LATEST`, ältere Frames werden verworfen ([8]). Damit lässt sich auf dem Gerät erkennen, zuschneiden und nur der Kartenausschnitt hochladen.
  - ML Kit Text Recognition v2 läuft on-device und unterstützt Latein inklusive Deutsch ([7]). Damit wäre auch Passcode-OCR direkt auf dem Pixel möglich. Das ist eine Option für die Topologie und hier keine Empfehlung.
- **Serverseitig:** Der volle Frame wird hochgeladen. Bei 1080p und 60 fps liefert ein Handy-MJPEG-Stream 11,5 MB/s, empfohlen werden 30 fps ([4]). Live gemessen: ~20 fps, das letzte Bild war 44 ms alt ([4]).

### 5. Latenzbudget (pro Scan, eine Karte)

| Schritt | Heimrechner (RTX 5080) | Raspberry Pi (Modell unbekannt) | Cloud |
|---|---|---|---|
| Frame-Aufnahme, Auswahl eines scharfen Frames | 33–100 ms (**Schätzung**, 1–3 Frames bei 30 fps) | gleich | gleich |
| Optional Zuschnitt und JPEG-Kodierung auf dem Pixel | 10–30 ms (**Schätzung**) | gleich | gleich |
| Upload über WLAN | 5–40 ms (**Schätzung**; Bildalter im Stream gemessen 44 ms [4]) | gleich | 50–300 ms ins Internet (**Schätzung**) |
| Detektion und Entzerrung | ~12 ms Detektor auf RTX 4070 [4], dazu Geometrie bis ~100 ms CPU [4] | 0,1–0,5 s (**Schätzung**) | im Dienst enthalten |
| Embedding + kNN | ~15 ms für 9 Karten auf RTX 4070 [4] | ≥ 0,5–1 s mit ViT-B (**Schätzung**, schon Laptop-CPU 0,47 s/Bild [4]) | im Dienst |
| Passcode/Namens-OCR (nur Ausschnitt) | ~0,1 s CPU [2]; auf GPU weniger (**Schätzung**) | 0,1–0,5 s (**Schätzung**) | Google Vision / Ximilar: unbekannt |
| Konsens über 2–3 Frames | +70–200 ms (**Schätzung**) | +Rechenzeit × 2–3 | +Round-Trip × 2–3 |
| **Summe** | **~0,2–0,5 s (Schätzung)** | **~1–3 s mit Embedding; mit reinem OCR knapp unter 1 s möglich (Schätzung)** | **~0,5–1,5 s (Schätzung)** |

Zum Vergleich auf CPU: Laptop-CPU 1–4 s pro Analyse mit mehreren Karten ([4]).

### 6. Bestehende Apps und Projekte

| Projekt | Verfahren | Zahlen | Lizenz |
|---|---|---|---|
| [Adrian-Sandwich/yugioh-ar](https://github.com/Adrian-Sandwich/yugioh-ar) | OBB-Detektor → Entzerrung → Embedding-kNN (DRAW2-ViT) + SIFT + OCR von Passcode, Name, Set-Code (RapidOCR); mehrsprachiges Register EN/ES/DE/FR/PT | siehe oben | MIT (Code); Kartenbilder nicht weitergegeben |
| [HichTala/draw2](https://github.com/HichTala/draw2) | YOLOv11-OBB + ViT-Klassifikator, Webcam/OBS-Plugin, Anzeige auf DE möglich | keine Metriken veröffentlicht | AGPL-3.0 |
| [ernestogba3/yugioh-card-scanner](https://github.com/ernestogba3/yugioh-card-scanner) | Android, CameraX + OpenCV; Passcode (ML Kit) → pHash → Namens-Fuzzy-Match; offline | keine | MIT |
| [kiyeo/Yu-Gi-Oh-Card-Tracker](https://github.com/kiyeo/Yu-Gi-Oh-Card-Tracker) | Browser; OpenCV/YOLO, EasyOCR/DocTR, Artwork-Index, heuristische Bewertung | keine; „assistive beta“ | MIT |
| [vanstorm9/yugioh-one-shot-learning](https://github.com/vanstorm9/yugioh-one-shot-learning) | ResNet-101 Triplet + ORB-Re-Ranking | ~99 % auf künstlich veränderten Katalogbildern | keine Lizenzangabe gefunden |
| [ULiege-VIULab/tcg-ar](https://github.com/ULiege-VIULab/tcg-ar) (Pokémon) | Oriented R-CNN + ArcFace-kNN | 85,1 % Top-1 auf echten Fotos | AGPL-3.0 |
| [fortierq/mtgscan](https://github.com/fortierq/mtgscan) (MTG) | Namens-OCR in der Cloud (Azure Read) + Fuzzy-Match (SymSpell) | keine | MIT |
| [Magic Card Detector](https://tmikonen.github.io/quantitatively/2020-01-01-magic-card-detector/) (MTG) | Konturen, 4-Punkt-Entzerrung, pHash | ~300 Referenzkarten, keine Metriken | – |
| Yu-Gi-Oh! NEURON (Konami, offiziell) | Kartenerkennung per Kamera ([23]); nach DRAW2-README bis zu 20 Karten gleichzeitig ([19]) | Verfahren nicht dokumentiert | proprietär |
| Delver Lens / Delver X (MTG) | Verfahren nicht dokumentiert; empfiehlt ≥1080p und ≥10 fps, Modell „lambda“ ([24]) | – | proprietär |

Kommerzielle Apps wie Delver Lens oder NEURON legen ihr Verfahren nicht offen. Belastbare Verfahrensbelege kommen daher nur aus den offenen Projekten.

### 7. Cloud als Plan B

- **Google Cloud Vision:** Text Detection kostet 1,50 USD je 1.000 Bilder, die ersten 1.000 pro Monat sind frei ([9]). Bei 5.000 Exemplaren und ~3 Frames pro Karte wären das ~15.000 Aufrufe, also ~21 USD (**Rechnung/Schätzung**). Das ist nur generische OCR, Matching und Katalog bleiben beim Projekt.
- **Ximilar `collectibles/v2/tcg_id`:**
  - Erkennt und schneidet Karten zu, unterstützt Yu-Gi-Oh und liefert Name, Set, Set-Code und Seltenheit ([13]).
  - Die Spracherkennung deckt lateinische Sprachen inklusive Deutsch ab ([13]).
  - Ximilar wirbt mit „99.9 % accuracy“, das ist Eigenangabe ([15]).
  - Preis pro Aufruf und Latenz stehen nicht in der Doku ([13]).
- Bei der Cloud bestimmt die Internet-Round-Trip-Zeit die Latenz. Mit Frame-Konsens wird 1 s knapp (**Schätzung**).

## Was ein Eval-Set zuerst messen sollte

Zusammensetzung (**Vorschlag**): ~200–300 eigene Exemplare, mit dem Pixel in der echten Scan-Haltung (Hand, Heimbeleuchtung) als kurze Clips oder Bildserien aufgenommen, nicht als Einzelfotos. Geschichtet nach:

- Sprache (DE / EN)
- Seltenheit: Common, Rare, Super, Ultra, Secret, **Ghost/Starlight/Ultimate**, soweit vorhanden
- Alter: frühe Sets vs. aktuelle
- **Proxies** getrennt nach Herkunft: Druck aus YGOProDeck-Bild, Druck aus Scan einer echten Karte, eigenes Artwork
- Alt-Arts
- mit/ohne Hülle
- Negativbeispiele, die nicht im Katalog sind (Token, Rush Duel, Skill, japanische OCG-Karten), um die Ablehnung zu prüfen

Messgrößen in dieser Reihenfolge:

1. **Passcode-Lesequote** pro Frame und pro Exemplar, abhängig von Ziffernhöhe in px und Analyseauflösung (1080p vs. 4K). Diese Zahl entscheidet, ob Passcode-OCR Haupt- oder Nebenweg sein kann.
2. **Falsch-Akzeptanzrate** des Embedding-Wegs gegen den vollen Katalog, getrennt nach DE, Foil und Proxy-Art. Weil ohne Bestätigung gebucht wird, ist das die wichtigste Fehlerart. Dazu der Anteil, der automatisch akzeptiert wird bzw. in die Prüf-Warteschlange geht, bei kalibrierter Schwelle (Ähnlichkeit + Abstand wie in [6]).
3. **Top-1/Top-5-Genauigkeit**: generisches DINOv2 vs. spezialisierter Encoder, ganze Karte vs. Artwork-Ausschnitt.
4. **Zeit bis zur Entscheidung** Ende-zu-Ende (p50/p95), mit Konsens über N Frames, sowie die Zuverlässigkeit von „Karte hat das Bild verlassen“ als Trenner zwischen zwei Scans.
5. Die Namens-OCR-Trefferquote DE/EN erst danach, als Stichentscheid.

## Offene Punkte

- **Echte Trefferquoten auf Handyfotos fehlen.** Alle großen Zahlen stammen von Händler-Scans oder synthetischen Daten. Nur das Eval-Set kann das klären.
- **Deutsche Karten:** Kein Projekt hat Zahlen für DE-Karten gegen englische Replica-Referenzen veröffentlicht. Für Namens-OCR fehlen bei YGOProDeck 2.493 deutsche Namen. Eine weitere Quelle wäre die Konami-Datenbank, deren Nutzungsbedingungen hier nicht geprüft wurden.
- **Lizenz:** DRAW2 (AGPL-3.0) ist der stärkste verfügbare Yu-Gi-Oh-Encoder. Das Projekt ist öffentlich, eine Übernahme von DRAW2-Code oder -Gewichten muss mit der Lizenzwahl des Projekts zusammenpassen. Die Alternative ist eigenes Fine-Tuning von DINOv2 (Apache-2.0) auf YGOProDeck-Bilder mit Augmentierung.
- **Raspberry Pi:** Das Modell ist unbekannt. Alle Pi-Zeiten sind Schätzungen ohne Messung.
- **Pixel on-device:** ML-Kit-Latenz auf dem konkreten Pixel-Modell ist nicht gemessen. On-device-Embedding (LiteRT) wurde nicht untersucht.
- **Ximilar:** Preis pro Aufruf und Latenz sind unbekannt, dafür wäre eine Anfrage beim Anbieter nötig.
- **pHash:** Für einen Katalog mit 14k Karten gibt es keine Messung. Ein Test auf dem Eval-Set wäre billig, falls man es als Vorfilter erwägt.
- **Katalog-Deduplizierung:** OCG/TCG-Doppelnamen ([4]) und Bild-ID-zu-Karte-Mapping ([10]) müssen beim Katalogaufbau gelöst werden.

## Quellen

1. yugioh-ar, `research/OCR_PASSCODE.md`: https://github.com/Adrian-Sandwich/yugioh-ar/blob/main/research/OCR_PASSCODE.md
2. yugioh-ar, `research/OCR_NOMBRE.md`: https://github.com/Adrian-Sandwich/yugioh-ar/blob/main/research/OCR_NOMBRE.md
3. yugioh-ar, README: https://github.com/Adrian-Sandwich/yugioh-ar
4. yugioh-ar, `research/TIEMPO_REAL.md` (GPU-Messungen, voller Katalog, DINOv2-Vergleich): https://github.com/Adrian-Sandwich/yugioh-ar/blob/main/research/TIEMPO_REAL.md
5. yugioh-ar, `research/ARTE_YGOPRODECK.md` und `research/PLAN_VECTORES_E_INVARIANCIA.md`: https://github.com/Adrian-Sandwich/yugioh-ar/tree/main/research
6. yugioh-ar, `research/CALIBRACION_ESCANEOS.md`: https://github.com/Adrian-Sandwich/yugioh-ar/blob/main/research/CALIBRACION_ESCANEOS.md
7. Google ML Kit, Text Recognition v2 (Android): https://developers.google.com/ml-kit/vision/text-recognition/v2/android
8. Android CameraX, Image analysis: https://developer.android.com/media/camera/camerax/analyze
9. Google Cloud Vision Pricing: https://cloud.google.com/vision/pricing
10. YGOProDeck API Guide: https://ygoprodeck.com/api-guide/ und eigene Auswertung von `https://db.ygoprodeck.com/api/v7/cardinfo.php` (mit und ohne `language=de`) sowie der Bilder unter `images.ygoprodeck.com`, abgerufen 2026-10-04
11. Yugipedia, „Password“: https://yugipedia.com/wiki/Password
12. ULiege-VIULab/tcg-ar, README (Results): https://github.com/ULiege-VIULab/tcg-ar
13. Ximilar Docs, Collectibles Recognition: https://docs.ximilar.com/collectibles/recognition
14. T. Ikonen, „Magic Card Detector“: https://tmikonen.github.io/quantitatively/2020-01-01-magic-card-detector/
15. Ximilar, „Build Your Own Trading Card Game Identifier With Our API“: https://ximilar.com/?p=14016
16. ernestogba3/yugioh-card-scanner, README: https://github.com/ernestogba3/yugioh-card-scanner
17. Oquab et al., „DINOv2: Learning Robust Visual Features without Supervision“, Tab. 9: https://arxiv.org/abs/2304.07193
18. facebookresearch/dinov2, README und Lizenz: https://github.com/facebookresearch/dinov2
19. HichTala/draw2, README: https://github.com/HichTala/draw2
20. Hugging Face, HichTala/draw2 (Modellkarte): https://huggingface.co/HichTala/draw2
21. yugioh-ar, `research/ESTADO_DEL_ARTE_REFLEJOS.md`: https://github.com/Adrian-Sandwich/yugioh-ar/blob/main/research/ESTADO_DEL_ARTE_REFLEJOS.md
22. vanstorm9/yugioh-one-shot-learning, README: https://github.com/vanstorm9/yugioh-one-shot-learning
23. Konami, Yu-Gi-Oh! NEURON: https://www.yugioh-card.com/en/products/neuron/
24. Delver: https://delver.app/
