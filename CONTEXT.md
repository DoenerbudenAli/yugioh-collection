# Yu-Gi-Oh-Sammlung

Digitalisierung einer physischen Yu-Gi-Oh-Kartensammlung per Handy-Scan, um sie mit Cube- und Decklisten abzugleichen.

## Language

### Katalog

**Karte**:
Eine Yu-Gi-Oh-Karte als Spielidentität, unabhängig von Druck, Sprache, Rarität und Zustand.
_Avoid_: Card, Druck, Print (der Wayfinder-Plan heißt **Map**, nie „Karte“)

**Katalog**:
Die Menge aller existierenden Karten, gegen die erkannt und abgeglichen wird.
_Avoid_: Kartendatenbank

**Passcode**:
Die auf einer Karte gedruckte 8-stellige Nummer; eine Karte kann mehrere Passcodes haben (Alt-Arts), manche haben keinen.
_Avoid_: ID, Kartennummer

**Katalogstand**:
Eine bestimmte Version des Katalogs, benannt nach der Datenbankversion der Quelle, aus der er übernommen wurde.
_Avoid_: Katalogversion, Snapshot

**Verwaiste Karte**:
Eine Karte, die die Quelle nicht mehr führt; sie bleibt im Katalog, damit Exemplare und Listen ihren Bezug behalten.
_Avoid_: gelöschte Karte

### Sammlung

**Exemplar**:
Ein einzelnes physisches Stück einer Karte in der Sammlung.
_Avoid_: Kopie, Copy

**Proxy**:
Ein Exemplar, das kein Original ist (z. B. selbst gedruckt); zählt als besessen, ist aber als Proxy gekennzeichnet.

**Sammlung**:
Alle Exemplare; die Anzahl einer Karte ist die Zahl ihrer Exemplare.
_Avoid_: Bestand, Inventar

### Erfassung

**Scan**:
Die Erfassung genau eines Exemplars; endet mit einer Buchung oder einem Eintrag in der Prüf-Warteschlange. Dieselbe Karte zählt erst erneut, nachdem sie das Kamerabild verlassen hat – verdeckt oder verwackelt gilt nicht als verlassen.
_Avoid_: Foto, Aufnahme

**Buchung**:
Der Abschluss eines Scans, der ein Exemplar in der Sammlung anlegt; nur eine Buchung erzeugt ein Exemplar.
_Avoid_: Speichern, Hinzufügen

**Falschbuchung**:
Eine Buchung auf eine andere Karte als die des gescannten Exemplars; jede Buchung eines Exemplars, dessen Karte nicht im Katalog ist, ist ebenfalls eine Falschbuchung.
_Avoid_: Fehlerkennung (eine Erkennung darf irren, eine Buchung nicht)

**Doppelbuchung**:
Zwei Buchungen für dasselbe Exemplar.

**Verlorenes Exemplar**:
Ein Exemplar, das im Kamerabild lag, ohne dass eine Buchung oder ein Eintrag in der Prüf-Warteschlange entstanden ist.

**Scan-Sitzung**:
Die Zeit vom Öffnen bis zum Schließen der Scan-Ansicht; Rückgängig wirkt nur innerhalb einer Scan-Sitzung.
_Avoid_: Session, Scan-Vorgang

**Erkennung**:
Die Zuordnung von Kamerabildern zu Kandidaten-Karten mit je einer Konfidenz; sie entscheidet nicht, ob gebucht wird.
_Avoid_: Identifikation, Scan (ein Scan nutzt eine Erkennung)

**Prüf-Warteschlange**:
Scans, deren Erkennung nicht sicher genug war und die nachträglich bestätigt, korrigiert oder verworfen werden; ihre Einträge sind keine Exemplare.
_Avoid_: Inbox, Fehlerliste

### Listen

**Cube-Liste**:
Eine von der Community kuratierte Liste von Karten, aus der im 1-gegen-1 gedraftet wird.

**Deckliste**:
Eine Liste von Karten mit Mengen für ein Deck.

**Fehlkarten**:
Die Karten einer Liste, von denen die Sammlung weniger Exemplare hat, als die Liste verlangt.
_Avoid_: Wants, fehlende Karten
