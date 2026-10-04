# Qualitätsnote und Ratchet

Status: akzeptiert
Präzisiert: ADR 0007

Die Code-Gesundheit wird auf zwei Ebenen gesteuert. Die **Qualitätsnote** je Modul in `docs/qualitaet.md` ist der Wochenblick: Sie zeigt dem Aufräum-Agenten, wo er ansetzt, und dem Owner im Verlauf, ob Komplexität, Duplikation und Co. über Quartale flach bleiben. Ein Skript **ohne LLM** berechnet sie aus Messwerten. Der GC-Agent „Qualitätsnoten“ schreibt nur die Begründung dazu. Damit präzisiert dieses ADR seine Zeile „pflegt `docs/qualitaet.md`“ aus ADR 0007. Der **Ratchet** ist das Gate: Kein PR darf die billigen Zähler eines Moduls erhöhen, ohne dass der Owner es per Kern-Datei erlaubt. Wir haben uns so entschieden, weil eine LLM-Note von Lauf zu Lauf schwankt und über Quartale nicht vergleichbar wäre, weil Bereinigung nur bei maschinenprüfbaren Zielen wirkt (AIDev: mediane Smell-Veränderung 0,00) und weil eine wöchentliche Meldung schleichende Drift zu spät und ohne Verursacher findet (CMU: +30 % Warnungen, +41 % Komplexität).

## Regeln

### Qualitätsnote

- **Benotet** werden die fünf Module (Katalog, Sammlung, Listen, Erkennung, Erfassung) und die PWA (`web/`). Harness, Broker und Kompositionen nicht, sie sind Kern oder dünner Klebecode.
- **Teilmetriken** je Modul: Mutation Score, Komplexitäts-Hotspots (Funktionen über einer Komplexitätsschwelle), Duplikat-Blöcke (jscpd, für Python und TS gleich) und Unterdrückungen (`noqa`, `type: ignore`, `pyright: ignore`, `eslint-disable`, `@ts-expect-error`, `pragma: no cover`, `pragma: no mutate`, `Stryker disable`). Warnungen selbst zählen nicht, sie sind ohnehin ein Gate und auf `main` immer 0.
- Coverage und Größe des Moduls stehen als **Information** daneben, ohne Einfluss auf die Note (ADR 0003).
- **Skala:** Jede Teilmetrik wird über Schwellen auf A–E abgebildet. Die Modulnote ist die **schlechteste Teilnote**, mit Angabe der Metrik („C wegen Duplikation“).
- Die Schwellen und die Komplexitätsschwelle stehen in einer Kern-Konfiguration im Paket `harness`.
- Der GC-Agent ergänzt je Modul eine Zeile zur größten Lücke. Die Note selbst ändert er nicht.

### Prozess-Metriken

- Für das ganze Repo, ohne Note: Reversion Rate (Anteil gemergter PRs, die später per Revert zurückgenommen werden), CI-Runden und geänderte Zeilen je PR, offene `drift`-Issues und KI-Kosten je Woche, soweit messbar.
- Sie erscheinen nur im Verlauf.

### Ablage und Anzeige

- `docs/qualitaet.md` enthält die aktuelle Tabelle. Daneben liegt eine Verlaufsdatei mit einem Eintrag je Lauf. Beide sind Peripherie und kommen per wöchentlichem GC-PR, der automatisch mergt (ADR 0006, ADR 0007).
- Die Verlaufsdatei ist **nur anhängbar**. Die CI prüft, dass bestehende Einträge unverändert bleiben.
- Ein **Dashboard auf GitHub Pages** zeigt den Verlauf. Ein Skript im Paket `harness` erzeugt daraus statisches HTML mit SVG, ohne JS-Bibliothek. Ein Workflow deployt es bei jedem Push auf `main`, der die Verlaufsdatei ändert.
- **Steigt ein Modul ab**, legt der GC ein `drift`-Issue mit Fingerabdruck an (ADR 0007). Auf die Note selbst gibt es kein Gate.

### Ratchet

- Je Modul (wie oben) zählt der Check `ratchet` (Teil von `ci`) Unterdrückungen, Komplexitäts-Hotspots und Duplikat-Blöcke. Ist ein Zähler im PR höher als auf der Basis des PRs, ist der Check rot.
- Mutation bleibt sein eigenes Gate mit eigener Schwelle (ADR 0003). Ein Mutationslauf je PR über das ganze Modul wäre für den Ratchet zu teuer.
- **Vergleichsbasis** ist der Stand auf `main` (Merge-Base), keine gepflegte Baseline-Datei. Sinkt ein Zähler, ist nichts nachzutragen.
- **Erhöhen** darf ein PR einen Zähler nur, wenn er im selben PR einen Eintrag im **Ausnahmen-Protokoll** anlegt: Modul, Zähler, Anzahl und Begründung. Das Protokoll ist Kern im Paket `harness`, eine Erhöhung braucht also den Owner (Stolperdraht, ADR 0006). Es ist nur anhängbar und zugleich das Archiv aller bewusst hingenommenen Verschlechterungen.
- Der Ratchet gilt für **alle PRs**, auch für die des Owners.

### Bau

- Der Ratchet ist ein Gate und kommt ins Epic Harness-Bau, vor dem Automerge. Ohne Modulcode stehen alle Zähler auf 0.
- Das Epic legt außerdem das Gerüst von `docs/qualitaet.md` (alle Module unbewertet) und die Kern-Konfiguration mit den Schwellen an.
- Messskript, Verlaufsdatei, Dashboard und den Qualitätsnoten-Agenten gibt es erst mit Modulcode, als normale Tickets (ADR 0007).

## Restrisiken

- Die Schwellen der Note sind anfangs geschätzt. Ihre erste Kalibrierung an echtem Modulcode ist ein Kern-PR, und eine geänderte Schwelle macht den Verlauf an dieser Stelle unstetig.
- Der Ratchet zählt nur. Ein PR kann einen Hotspot auflösen und dafür einen neuen bauen, ohne dass ein Zähler steigt. Das fängt die Note im Verlauf nicht, nur `ai-review` und der Aufräum-Agent.
- Die Verlaufsdatei ist Peripherie. Ein Bot-PR könnte erfundene neue Einträge anhängen, nur alte ändern kann er nicht. Das ist hingenommen, weil die Note keine Entscheidung automatisch auslöst.
- KI-Kosten lassen sich bei einem Abo-Token womöglich nur über Turns und Laufzeit annähern.

## Verworfene Alternativen

- **LLM vergibt die Note:** nicht reproduzierbar, über Quartale nicht vergleichbar, und Agenten bauen Schulden nur bei maschinenprüfbaren Zielen ab.
- **Gewichteter Durchschnitt der Teilnoten:** Über Gewichte ließe sich ewig streiten, und ein gutes Modul könnte eine Schwäche verdecken.
- **Gate auf die Note:** Jeder PR bräuchte einen Mutationslauf über das ganze Modul, und weil die Stufen grob sind, träfe es den PR, der die Schwelle zufällig überschreitet, statt den Verursacher. Begründete Ausnahmen gäbe es nicht.
- **Nur `drift`-Issue ohne Ratchet:** Die Drift fiele erst nach mehreren gemergten PRs auf, ohne Verursacher, und das Sortieren kostete Owner-Zeit.
- **Gepflegte Baseline-Datei als Kern:** Jede Verbesserung bräuchte dann ein Owner-Review und bräche den Automerge der Peripherie.
- **Ratchet nur für Bot-PRs:** Ein PR des Owners würde die Basis verschieben, ohne dass es sichtbar wird.
- **Verlauf nur als Actions-Artefakte:** Sie verfallen nach 90 Tagen, zu kurz für einen Verlauf über Quartale.
- **Dashboard mit JS-Chart-Bibliothek:** eine Abhängigkeit mehr für ein paar Linien, die statisches SVG genauso zeigt.
