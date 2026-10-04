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
Die Erfassung genau eines Exemplars; dieselbe Karte zählt erst erneut, nachdem sie das Kamerabild verlassen hat.
_Avoid_: Foto, Aufnahme

**Erkennung**:
Die Zuordnung von Kamerabildern zu Kandidaten-Karten mit je einer Konfidenz; sie entscheidet nicht, ob gebucht wird.
_Avoid_: Identifikation, Scan (ein Scan nutzt eine Erkennung)

**Prüf-Warteschlange**:
Scans, deren Erkennung nicht sicher genug war und die nachträglich bestätigt oder korrigiert werden.
_Avoid_: Inbox, Fehlerliste

### Listen

**Cube-Liste**:
Eine von der Community kuratierte Liste von Karten, aus der im 1-gegen-1 gedraftet wird.

**Deckliste**:
Eine Liste von Karten mit Mengen für ein Deck.

**Fehlkarten**:
Die Karten einer Liste, von denen die Sammlung weniger Exemplare hat, als die Liste verlangt.
_Avoid_: Wants, fehlende Karten
