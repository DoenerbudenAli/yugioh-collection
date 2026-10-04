# Eval-Set der Erkennung

Status: akzeptiert
Präzisiert: ADR 0006

Das **Eval-Set** ist der Behaviour-Harness der Erkennung: Clips eigener Exemplare, mit dem Pixel über denselben Pfad aufgenommen wie in der App. Die **Fotos liegen außerhalb von Git** in einem Ordner `eval-daten/` auf dem Heimrechner. Im Repo liegen unter `eval/` nur das **Manifest** (Labels und SHA-256 je Bild), die **Spuren des Kalibrier-Teils** und die **Eval-Quittung**, alle drei Kern. Damit präzisiert dieses ADR die Zeile „`eval/` samt Referenzfotos“ aus ADR 0006: Die Fotos sind nicht im Repo, das Manifest schützt sie stattdessen. Die CI spielt den Konsens der Erfassung über die Kalibrier-Spuren ab. Änderungen an Encoder, Vorverarbeitung oder Schwellen brauchen eine Quittung, die der Owner lokal auf dem Prüf-Teil erzeugt. Wir haben uns so entschieden, weil die Clips mit geschätzt 4–10 GB weit über dem liegen, was ein Git-Repo oder das freie LFS-Kontingent trägt, weil Fotos von Konami-Artwork nicht in ein public AGPL-Repo gehören und weil ein privates Repo wieder ein GitHub-Credential auf dem Host bräuchte (ADR 0005). Die GitHub-Runner haben weder GPU noch Zugriff auf die Fotos. Die Spuren machen den Konsens trotzdem in der CI prüfbar.

## Regeln

### Aufnahme

- Aufgenommen wird über den Pfad der App (zuerst die Kamera-Sonde): dieselbe Analyseauflösung, dieselbe JPEG-Qualität, dieselben Fokus- und Belichtungs-Einstellungen, dieselbe Sende-Rate. Jedes Bild trägt Zeitstempel und Kamera-Metadaten.
- Ein **Clip** ist ein Scan-Zyklus: leer → Karte rein → liegt → raus → leer. Dazu kommen **Stapel-Läufe** mit 20–30 Karten am Stück, darunter zwei Exemplare derselben Karte direkt hintereinander und eine Karte, die direkt über die vorige geschoben wird.
- Jedes Exemplar wird in beiden Haltungen aufgenommen, Halterung und freihändig.
- Clips werden nur angehängt, nie überschrieben oder gelöscht. Neue Clips bekommen ein neues Verzeichnis und neue Manifest-Zeilen.

### Umfang

Etwa 200 Exemplare, mit diesen Mindestquoten:

| Schicht | Minimum |
|---|---|
| Deutsch / Englisch | je 80 |
| Foils (Super, Ultra, Secret) | 30 |
| Ghost, Starlight, Ultimate | alle vorhandenen |
| Altkarten (frühe Sets) | 20 |
| Alt-Arts | 10 |
| ähnliche Artworks (Retrains, Archetyp-Geschwister) | 15 |
| Proxies, nach Herkunft (Druck aus YGOProDeck-Bild, Druck aus Scan, eigenes Artwork) | 30 |
| mit und ohne Hülle (dasselbe Exemplar zweimal) | 20 |
| nicht im Katalog (Token, Rush Duel, Skill, japanische OCG-Karten) | 15 |
| Störclips (Hand davor, halb im Bild, verwackelt, leer) | 20 |

Normale Heimbeleuchtung, dazu etwa 40 Exemplare unter schlechtem Abendlicht.

### Labels

- Gelabelt wird je Clip, nicht je Bild: Passcode (ohne Passcode die YGOProDeck-ID), Art-Variante, Sprache, Seltenheit, Proxy und Herkunft, Haltung, Licht, Hülle, „nicht im Katalog“.
- Dazu je Clip zwei Bildindizes: „liegt ruhig“ und „ist weg“.
- Gelabelt wird über die Reihenfolge. Je Schicht wird ein Stapel gelegt, seine Passcodes werden vorab als Liste festgehalten, und er wird in genau dieser Reihenfolge gescannt. Clip *n* gehört zu Zeile *n*.
- Das Manifest enthält die Labels, die Zuordnung zum Kalibrier- oder Prüf-Teil und den SHA-256 jedes Bildes. Jeder Lauf prüft zuerst, ob `eval-daten/` genau zum Manifest passt, und bricht sonst ab.

### Kalibrier-Teil und Prüf-Teil

- Die Exemplare werden 50/50 aufgeteilt, geschichtet nach allen Schichten des Umfangs.
- Schwellen werden nur am **Kalibrier-Teil** eingestellt.
- Der **Prüf-Teil** liefert die Zahlen, die zählen. Er läuft nur bei Änderungen an Encoder, Index, Vorverarbeitung oder Schwellen, nie während des Tunens. Seine Spuren verlassen `eval-daten/` nicht.
- Ist der Prüf-Teil verbraucht, weil er zu oft angeschaut wurde, kommt ein neuer Prüf-Teil aus frischen Exemplaren dazu.

### Metriken und Ziele

Gemessen am Prüf-Teil, je Haltung getrennt:

| Metrik | Ziel |
|---|---|
| Falschbuchungen (auch bei Karten, die nicht im Katalog sind) | 0, Blocker |
| verlorene Exemplare | 0, Blocker |
| Doppelbuchungen | 0, Blocker |
| Anteil automatischer Buchungen (Rest geht in die Prüf-Warteschlange) | ≥ 95 % |
| Zeit bis zur Buchung ab „liegt ruhig“ | p95 < 500 ms |
| Aufschlag durch den Pi im Frame-Pfad | p95 ≤ 50 ms (ADR 0002) |
| Passcode-Lesequote je Bild und je Exemplar, Top-1 und Top-5 je Encoder | nur gemessen, kein Ziel |

Die Passcode-Lesequote entscheidet, ob Passcode-OCR Haupt- oder Nebenweg wird. Alle Zahlen, die ein Ziel einhalten, stehen in den Parameterdateien der Module (ADR 0006), nicht im Eval-Code.

### Läufe

- `just eval` (offline): ruft Erkennung und Konsens der Erfassung im Prozess auf, im Image des Erkennungsdienstes auf dem Heimrechner, `eval-daten/` read-only gemountet. Liefert Qualität, Inferenzzeit und die Spuren.
- `just eval --pruef`: spielt nur die vorhandenen Prüf-Spuren durch den Konsens. Das braucht keine GPU und dauert Sekunden.
- `just eval-strecke`: spielt die Clips im Originaltakt über den WebSocket durch den echten Pfad Pi → Heimrechner. Liefert die Zeit bis zur Buchung und den Aufschlag durch den Pi. Läuft bei Änderungen an Topologie oder Netzpfad.

### Spuren

- Eine **Spur** hält je Bild fest, was die Erkennung geliefert hat: die Top-k Karten mit Konfidenz, die Flags scharf und leer und den gelesenen Passcode. Sie enthält kein Bild und kein Artwork.
- Die Spuren des Kalibrier-Teils liegen unter `eval/`. Die CI spielt den Konsens-Reducer der Erfassung über sie ab und prüft die Blocker-Ziele und den Anteil automatischer Buchungen. So ist jede Änderung an der Konsens-Logik ohne GPU geprüft.
- Neu erzeugt werden die Spuren, wenn sich Encoder, Index oder Vorverarbeitung ändern.

### Eval-Quittung

- `eval/quittung.json` enthält die Metriken des Prüf-Teils, den Hash des Manifests und einen **Eingabe-Hash**. Er umfasst das Paket `erkennung`, die Modell-ID mit dem Hash der Gewichte und die Parameterdateien von Erkennung und Erfassung.
- Die CI rechnet den Eingabe-Hash nach. Weicht er ab oder verfehlt eine Metrik der Quittung ein Blocker-Ziel, ist der PR rot.
- Die Quittung erzeugt der Owner lokal und committet sie im selben PR. Sie ist Kern und braucht sein Approval.
- `eval-daten/` wird nie in einen Devcontainer gemountet. Agenten können die Quittung nicht selbst erzeugen und bitten den Owner um einen Lauf.

### Ablage

- `eval-daten/` liegt auf dem Heimrechner, außerhalb jedes Clones. Eine Kopie liegt als Backup auf dem Pi.
- Das Manifest ersetzt die Versionierung: Jede Abweichung der Bilder fällt über die Hashes auf, und weil Clips nur angehängt werden, bleibt jeder frühere Stand im Manifest-Verlauf nachvollziehbar.

## Restrisiken

- Mit 200 Exemplaren lässt sich keine sehr kleine Fehlerrate belegen. Bei 0 Falschbuchungen unter rund 100 Exemplaren je Haltung im Prüf-Teil liegt die Rate mit 95 % Sicherheit nur unter etwa 3 %. Ein größerer Prüf-Teil kommt per Nachschub.
- Die Kalibrier-Spuren im public Repo zeigen, welche eigenen Karten im Set sind. Das ist hingenommen.
- Fällt der Heimrechner samt Platte aus, bevor das Backup auf dem Pi läuft, ist das Set verloren. Manifest und Spuren überleben im Repo, die Fotos nicht.
- Eine Quittung bezeugt nur, was der Owner lokal laufen ließ. Gegen Versehen schützt der Eingabe-Hash, gegen einen bewusst gefälschten Lauf nichts. Das ist im Solo-Betrieb hingenommen.

## Verworfene Alternativen

- **Fotos im public Repo mit Git LFS:** Artwork in einem public AGPL-Repo, und 4–10 GB sprengen das freie Kontingent (1 GB Speicher, 1 GB Traffic im Monat).
- **Privates Repo für die Fotos:** Es brauchte ein LFS-Datenpaket mit laufenden Kosten und einen Deploy-Key auf dem Heimrechner, also wieder ein GitHub-Credential auf dem Host (ADR 0005). Die Hashes im Manifest leisten dasselbe für die Unverfälschtheit.
- **Einzelfotos statt Clips:** Damit lassen sich Mehr-Bild-Konsens, „Bild verlassen“ und Doppel-Bremse nicht messen.
- **Labels je Bild:** zu teuer. Die zwei Bildindizes je Clip reichen für Zeit bis zur Buchung und Trennung der Scans.
- **Eval in der CI mit GPU-Runner:** kostenpflichtig, und der Runner bräuchte die Fotos.
- **Alle Spuren im Repo:** Agenten könnten Schwellen gegen den Prüf-Teil tunen, bis die CI grün ist. Der Owner sähe beim Approval nur den Wert, nicht die Überanpassung.
- **Ein Set ohne Aufteilung:** Schwellen, die am selben Set eingestellt und gemessen werden, liefern geschönte Zahlen.
