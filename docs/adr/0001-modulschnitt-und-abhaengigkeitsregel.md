# Modulschnitt und Abhängigkeitsregel

Das System zerfällt in fünf Module: **Katalog**, **Sammlung**, **Listen**, **Erkennung** und **Erfassung**. Ein Modul darf nur den Kern eines anderen Moduls importieren, und nur entlang dieser Kanten:

```
Erfassung ──► Erkennung ──► Katalog
Erfassung ──► Sammlung  ──► Katalog
Erfassung ──► Katalog
Listen    ──► Katalog
```

Der Katalog hängt von nichts ab. Jede andere Kante ist verboten, insbesondere Listen ↔ Sammlung. Innerhalb eines Moduls gibt es zwei Schichten. Der **Kern** ist rein, ohne I/O, und darf nur den Kern erlaubter Module importieren. Die **Adapter** (Speicher, HTTP, Dateien, Kamera) importieren nur den eigenen Kern. Darüber liegt eine einzige **Komposition** (je Deployable, siehe ADR 0002), die Adapter verdrahtet und technischen Querschnitt (Logging, Konfiguration, Uhr) als Providers hineingibt. Ganz oben liegt die UI, die nur die Komposition kennt. Wir haben uns so entschieden, weil die Regel mechanisch erzwingbar sein soll und Agenten ohne erzwungene Grenzen messbar Komplexität aufbauen.

## Regeln

- Jedes Modul hat genau einen öffentlichen Einstiegspunkt; Importe an ihm vorbei sind verboten.
- Die erlaubten Kanten stehen in **einer** maschinenlesbaren Regeldatei. Linter-Konfiguration und Doku werden daraus erzeugt oder dagegen geprüft.
- **Datenhoheit:** Jedes Modul besitzt seine Daten. Andere Module erreichen sie nur über sein Interface und verweisen per ID darauf. Physisch darf es eine gemeinsame Datenbankdatei sein.
- Fachtypen gehören dem Modul, das sie definiert (die Karten-ID gehört dem Katalog). Ein `shared`/`common`-Modul gibt es nicht.
- Die Erkennung besitzt ihren Index und baut ihn aus den Daten des Katalogs. Nach einer Katalog-Aktualisierung stößt die Komposition den Neuaufbau an.
- Die Fehlkarten berechnet Listen aus einer übergebenen Anzahl je Karte. Die Komposition holt diese Anzahl aus der Sammlung.
- Die Korrektur gebuchter Scans gehört der Erfassung. Die Sammlung bietet dafür nur Buchen und Entfernen von Exemplaren an.
- Jedes Exemplar ist ein eigener Datensatz mit Herkunft (Scan oder Import).

## Verworfene Alternativen

- **Erkennung als Teil der Erfassung:** Die Erkennung hat einen eigenen Test-Harness (das Eval-Set), läuft wahrscheinlich anders verteilt und ist über einen Fake ersetzbar. Damit ist sie eine echte Seam.
- **Eigenes Modul „Abgleich“:** Es wäre ein reiner Durchreicher gewesen, und Listen und Sammlung wären über ihn gekoppelt worden.
- **OpenAIs sechs Schichten** (Types → Config → Repo → Service → Runtime → UI): Bei dieser Größe entstehen damit fast nur leere Ordner. Kern/Adapter ist genauso gut erzwingbar und kann später verfeinert werden.
- **`shared`-Modul:** Es wird erfahrungsgemäß zur Müllhalde, an der jede Grenze vorbeiläuft.
- **Gemeinsamer Datenzugriff per SQL:** Er umgeht jeden Import-Linter.
- **Sammlung als Zähler je Karte:** Damit lässt sich ein einzelnes falsch gebuchtes Exemplar nicht korrigieren.
- **Event Sourcing für die Sammlung:** Ohne zweiten Lesepfad wäre es reine Zeremonie, und es ist später schwer zurückzubauen.
