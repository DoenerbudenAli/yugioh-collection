# PRD: MVP der Yu-Gi-Oh-Sammlung

Der Owner digitalisiert seine Sammlung (3–5k Exemplare, Deutsch/Englisch gemischt, einige Proxies), indem er Karten mit dem Pixel 7 Pro in **Firefox** scannt. Danach gleicht er die Sammlung mit Cube- und Decklisten ab. Es gibt einen Nutzer, den Owner, und gescannt wird nur zu Hause im WLAN. Die Begriffe stehen in [`CONTEXT.md`](../../CONTEXT.md).

Dieses Dokument legt fest, **was** das MVP verspricht. Das **Warum** steht in den verlinkten ADRs. Zahlen, die eine Produktentscheidung sind (Schwellen, Zeitlimits), stehen nicht hier, sondern in der Parameterdatei des jeweiligen Moduls ([ADR 0006](../adr/0006-risikostaffelung.md)).

## Bauabschnitte

In dieser Reihenfolge. Jeder Abschnitt ist für den Owner benutzbar, bevor der nächste beginnt.

1. [Katalog](#1-katalog)
2. [Scannen bis zur Buchung](#2-scannen-bis-zur-buchung)
3. [Prüf-Warteschlange und Rückgängig](#3-prüf-warteschlange-und-rückgängig)
4. [Sammlung ansehen und filtern](#4-sammlung-ansehen-und-filtern)
5. [Listen importieren, Fehlkarten, Export](#5-listen-importieren-fehlkarten-export)
6. [Eigene Listen](#6-eigene-listen)

Der Scan kommt vor den Listen, weil er das größte Risiko trägt und weil Fehlkarten erst mit gefüllter Sammlung aussagekräftig sind.

## Für alle Abschnitte

- Die Oberfläche ist deutsch. **Kartennamen sind überall englisch**. Die Suche findet zusätzlich die deutschen Namen, die YGOProDeck führt.
- Akzeptanzkriterien sind Szenarien (Gegeben/Wenn/Dann). Sie werden zu Tests an der Modulschnittstelle. Laut [ADR 0006](../adr/0006-risikostaffelung.md) kommt der Test-PR vor dem Implementierungs-PR.

## 1. Katalog

Der Katalog wird aus YGOProDeck übernommen und täglich aktualisiert ([Betrieb](https://github.com/DoenerbudenAli/yugioh-collection/issues/48)). Der Owner muss dafür nichts tun.

**Versprechen**

- Täglich wird geprüft, ob die Quelle eine neue Datenbankversion hat. Bei einer neuen Version wird komplett abgerufen und lokal verglichen.
- Karten werden nie gelöscht. Führt die Quelle eine Karte nicht mehr, wird sie zur **verwaisten Karte**.
- Eine mehrdeutige Zuordnung blockiert die Übernahme. Der bisherige Katalogstand bleibt gültig.
- Die Oberfläche zeigt den **Katalogstand**, das Datum der letzten Prüfung und einen Hinweis, wenn eine Übernahme blockiert ist. Einen Knopf zum Aktualisieren gibt es nicht.

**Szenarien**

- *Gegeben* der Katalogstand ist aktuell, *wenn* die tägliche Prüfung läuft, *dann* wird nichts abgerufen, und das Datum der letzten Prüfung ändert sich.
- *Gegeben* die Quelle hat eine neue Datenbankversion mit einer neuen Karte, *wenn* die Prüfung läuft, *dann* ist die Karte danach im Katalog, und der Katalogstand trägt die neue Version.
- *Gegeben* Dark Magician hat Exemplare in der Sammlung, *wenn* die Quelle ihn nicht mehr führt, *dann* bleibt er als verwaiste Karte im Katalog, und seine Exemplare bleiben unverändert.
- *Gegeben* zwei neue Einträge der Quelle passen auf dieselbe Karte, *wenn* die Prüfung läuft, *dann* wird nichts übernommen, und die Oberfläche zeigt den Hinweis auf die blockierte Übernahme.
- *Gegeben* Dark Magician hat die Passcodes 46986414 und 36996508, *wenn* einer davon aufgelöst wird, *dann* ergibt beides dieselbe Karte.

## 2. Scannen bis zur Buchung

Der Owner öffnet die Scan-Ansicht und legt Karten nacheinander unter die Kamera, entweder mit Halterung oder freihändig. Jede sicher erkannte Karte wird ohne Bestätigung als Exemplar gebucht. Grundlage: [Scan-UX](https://github.com/DoenerbudenAli/yugioh-collection/issues/7), [ADR 0002](../adr/0002-systemtopologie.md), [ADR 0010](../adr/0010-erkennung-und-buchungsregel.md).

**Versprechen**

- Ein Exemplar geht nie stillschweigend verloren und wird nie stillschweigend falsch gebucht. Im Zweifel geht der Scan in die Prüf-Warteschlange.
- Gebucht wird nach mehreren sicheren Bildern in Folge mit derselben Top-Karte. Einzelne Bilder buchen nie.
- Dieselbe Karte zählt erst erneut, nachdem sie das Kamerabild verlassen hat. Verlassen heißt: keine Karte gefunden **und** der Tisch ist sichtbar. Eine Hand über der Karte zählt nicht als verlassen.
- Findet der Detektor nie eine Karte, entsteht kein Scan und es kommt kein Ton. Der Owner legt die Karte zur Seite (**unerkanntes Exemplar**). Ins MVP kommt sie nicht.
- Mit Halterung bleibt die Karte liegen, bis der Ton kommt.
- **Rückmeldung** über Ton und Farbrahmen (Firefox kann nicht vibrieren):

  | Ereignis | Ton | Rahmen und Anzeige |
  |---|---|---|
  | Gebucht | kurzer hoher Ton | grün, Kartenname und neue Anzahl groß |
  | Prüfung | zwei tiefe Töne | gelb, „zur Seite legen“ |
  | Fehler/gesperrt | Fehlerton | rot |
  | Bereit | – | grau |

- **Proxy-Modus:** bleibt an, bis der Owner ihn abschaltet, und ist als dauerhaftes Banner sichtbar. Er gilt für Buchungen und Prüf-Einträge. Beim **letzten Scan** lässt sich Proxy nachträglich umschalten.
- **Heimrechner aus:** Beim Öffnen der Scan-Ansicht und laufend während des Scannens wird geprüft, ob der Erkennungsdienst erreichbar ist. Ist er nicht erreichbar, ist Scannen gesperrt (rot) und es werden keine Frames gepuffert. Fällt er mitten in einem Scan aus, wird der Scan ohne Buchung abgebrochen. Kommt er zurück, während eine gebuchte Karte noch liegt, wird nicht doppelt gebucht.
- Ein veralteter Index der Erkennung sperrt das Scannen nicht. Es erscheint ein Hinweis, und der Neuaufbau startet.

**Akzeptanz durch das Eval-Set**

Die Ziele aus [ADR 0008](../adr/0008-eval-set.md), präzisiert durch [ADR 0010](../adr/0010-erkennung-und-buchungsregel.md), gelten je Haltung am Prüf-Teil: 0 Falschbuchungen, 0 Doppelbuchungen, 0 verlorene Exemplare (alle drei Blocker), ≥ 95 % automatische Buchungen, Zeit bis zur Buchung ab „liegt ruhig“ p95 ≤ 500 ms bei 8 Bildern/s, Aufschlag durch den Pi p95 ≤ 50 ms. Die Eval-Quittung ist das Gate.

**Szenarien**

- *Gegeben* der Erkennungsdienst ist bereit, *wenn* Dark Magician ruhig unter der Kamera liegt, *dann* wird genau ein Exemplar gebucht, es kommt der hohe Ton, und der grüne Rahmen zeigt „Dark Magician“ mit der neuen Anzahl.
- *Gegeben* Dark Magician wurde gebucht und liegt weiter, *wenn* eine Hand über die Karte fährt und wieder weggeht, *dann* entsteht keine zweite Buchung.
- *Gegeben* Dark Magician wurde gebucht, *wenn* er weggenommen wird, der Tisch sichtbar ist und ein zweites Exemplar Dark Magician hingelegt wird, *dann* entsteht eine zweite Buchung.
- *Gegeben* die Erkennung liefert Kandidaten, ist aber nicht sicher genug, *wenn* das Zeitlimit abläuft, *dann* entsteht ein Prüf-Eintrag, es kommen zwei tiefe Töne, und der Rahmen wird gelb.
- *Gegeben* die Erkennung liefert Kandidaten, *wenn* die Karte vor der Entscheidung weggenommen wird, *dann* entsteht ein Prüf-Eintrag.
- *Gegeben* Dark Magician wurde gerade gebucht und weggenommen, *wenn* er kurz danach wieder sicher erkannt wird (Doppel-Bremse), *dann* entsteht ein Prüf-Eintrag mit dem Hinweis „doppelt?“ statt einer Buchung.
- *Gegeben* der Detektor findet keine Karte, *wenn* eine Karte im Bild liegt, *dann* entsteht kein Scan und es kommt kein Ton.
- *Gegeben* der Heimrechner ist aus, *wenn* der Owner die Scan-Ansicht öffnet, *dann* ist Scannen gesperrt und der Rahmen rot.
- *Gegeben* der Proxy-Modus ist an, *wenn* Dark Magician gebucht wird, *dann* ist das Exemplar ein Proxy.
- *Gegeben* der letzte Scan hat Dark Magician ohne Proxy gebucht, *wenn* der Owner beim letzten Scan auf Proxy umschaltet, *dann* ist dieses Exemplar ein Proxy, und kein anderes Exemplar ändert sich.

## 3. Prüf-Warteschlange und Rückgängig

Unsichere Scans landen in der Prüf-Warteschlange. Der Owner arbeitet sie später am Handy ab, mit dem Prüf-Stapel in der Hand. Fehler einer laufenden Scan-Sitzung nimmt er per Rückgängig zurück.

**Versprechen**

- Prüf-Einträge sind **keine Exemplare**. Sie zählen weder in der Sammlung noch bei Fehlkarten, bis sie bestätigt sind.
- Die Prüf-Warteschlange ist jederzeit nutzbar, auch wenn der Heimrechner aus ist.
- Ein Eintrag zeigt das beste Bild, bis zu drei Kandidaten und den Kontext (den Scan davor und ob das Bild dazwischen leer war). Er bietet eine Suche nach dem Kartennamen, „Verwerfen“ und einen Proxy-Schalter. Die Einträge stehen in Scan-Reihenfolge.
- Bestätigen oder Korrigieren bucht ein Exemplar. Verwerfen bucht nichts. Danach wird das gespeicherte Bild gelöscht.
- **Rückgängig:** ein großer Knopf, mehrfach drückbar, auch über Prüf-Einträge hinweg, wirksam nur innerhalb der **Scan-Sitzung**. Dazu der Verlauf der Sitzung, um gezielt einen Eintrag zu löschen. Liegt die Karte noch, muss sie trotzdem erst raus.
- Am Ende der Sitzung gibt es eine Zusammenfassung: gebucht, in Prüfung, rückgängig.

**Szenarien**

- *Gegeben* ein Prüf-Eintrag mit den Kandidaten Dark Magician und Dark Magician Girl, *wenn* der Owner Dark Magician bestätigt, *dann* hat die Sammlung ein Exemplar Dark Magician mehr, und der Eintrag ist weg.
- *Gegeben* ein Prüf-Eintrag, *wenn* der Owner per Namenssuche „Ash Blossom & Joyous Spring“ wählt, *dann* wird ein Exemplar dieser Karte gebucht.
- *Gegeben* ein Prüf-Eintrag, *wenn* der Owner ihn verwirft, *dann* ändert sich die Sammlung nicht.
- *Gegeben* ein offener Prüf-Eintrag für Dark Magician, *wenn* die Fehlkarten einer Liste berechnet werden, die Dark Magician verlangt, *dann* zählt der Eintrag nicht als Exemplar.
- *Gegeben* der Heimrechner ist aus, *wenn* der Owner die Prüf-Warteschlange öffnet, *dann* kann er sie vollständig abarbeiten.
- *Gegeben* in der laufenden Scan-Sitzung wurden drei Karten gebucht und eine ging in die Prüfung, *wenn* der Owner zweimal auf Rückgängig drückt, *dann* sind der Prüf-Eintrag und die letzte Buchung weg.
- *Gegeben* eine Scan-Sitzung wurde geschlossen, *wenn* eine neue geöffnet wird, *dann* nimmt Rückgängig nichts aus der alten Sitzung zurück.

## 4. Sammlung ansehen und filtern

**Versprechen**

- Die Sammlung ist **als Liste oder als Kacheln** umschaltbar, mit einem Eintrag je Karte: Bild, englischer Name, Anzahl, davon Proxies.
- Die **Detailansicht** einer Karte zeigt ihre Exemplare mit Buchungszeitpunkt und Proxy-Kennzeichen. Dort lässt sich ein **Exemplar löschen**. Das ist der Weg für Fehler, die nach dem Ende der Scan-Sitzung auffallen.
- **Filter** ([Filter und eigene Listen](https://github.com/DoenerbudenAli/yugioh-collection/issues/49)): Name (Teilstring, englisch und die deutschen Namen von YGOProDeck), Kartenart mit Untertyp, Attribut, Stufe/Rang/Link, Archetyp, Proxy ja/nein, Anzahl (≥/=).

**Szenarien**

- *Gegeben* 3 Exemplare Dark Magician, davon 1 Proxy, *wenn* der Owner die Sammlung öffnet, *dann* zeigt der Eintrag Anzahl 3, davon 1 Proxy, in der Listen- wie in der Kachelansicht.
- *Gegeben* 3 Exemplare Dark Magician, *wenn* der Owner in der Detailansicht eines löscht, *dann* hat die Sammlung 2.
- *Gegeben* die Sammlung enthält Dark Magician, *wenn* der Owner nach „Dunkler Magier“ sucht, *dann* wird Dark Magician gefunden und englisch angezeigt.
- *Gegeben* Exemplare verschiedener Karten, *wenn* der Owner nach Attribut „DARK“ und Anzahl ≥ 2 filtert, *dann* erscheinen nur DARK-Karten mit mindestens 2 Exemplaren.
- *Gegeben* nur Proxies von Ash Blossom & Joyous Spring, *wenn* der Owner nach Proxy „nein“ filtert, *dann* erscheint Ash Blossom & Joyous Spring nicht.

## 5. Listen importieren, Fehlkarten, Export

**Versprechen**

- **Cube-Liste** importieren per Cube-ID oder eingefügter YGOProDeck-URL. Wer einen Cube mit derselben Cube-ID erneut importiert, ersetzt die gespeicherte Kopie.
- **Deckliste** importieren als `.ydk`-Datei. Main, Extra und Side bleiben als Abschnitte erhalten, und alle drei zählen bei den Fehlkarten. Alt-Art-Passcodes werden über die Passcode-Tabelle aufgelöst.
- **Ein einziger nicht auflösbarer Eintrag lässt den ganzen Import scheitern**, mit einer Liste der Problemzeilen. Eine halbe Liste gibt es nicht. Nach dem nächsten Katalogstand importiert der Owner erneut.
- **Fehlkarten** werden je Liste gegen die ganze Sammlung berechnet, ohne Reservierung zwischen Listen. Proxies zählen als besessen.
- **Listen verwalten:** Übersicht aller Listen mit der Zahl der Fehlkarten, umbenennen, löschen. Cube- und Decklisten lassen sich nicht bearbeiten, sie ändern sich nur durch erneuten Import.
- **Export** wahlweise der Fehlkarten oder der ganzen Liste:
  - als Text, eine Zeile je Karte im Format `<Anzahl> <englischer Name>`, passend zum Deck-List-Import von Cardmarket;
  - als `.ydk`, ein Passcode je Exemplar, der Standard-Passcode der Karte. Bei einer Deckliste bleiben die Abschnitte erhalten.

**Szenarien**

- *Gegeben* Cube 10400 existiert, *wenn* der Owner die ID 10400 oder die URL des Cubes importiert, *dann* entsteht eine Cube-Liste mit allen Karten des Cubes und ihren Mengen.
- *Gegeben* Cube 10400 ist schon importiert, *wenn* der Owner ihn erneut importiert, *dann* gibt es weiterhin genau eine Cube-Liste 10400 mit dem neuen Stand.
- *Gegeben* eine `.ydk` mit 3 × 14558127 im Main und 1 × 14558127 im Side, *wenn* sie importiert wird, *dann* verlangt die Deckliste 4 Ash Blossom & Joyous Spring, aufgeteilt auf Main und Side.
- *Gegeben* eine `.ydk` mit dem Alt-Art-Passcode 36996508, *wenn* sie importiert wird, *dann* wird er zu Dark Magician aufgelöst.
- *Gegeben* eine `.ydk` mit einem Passcode, den der Katalogstand nicht kennt, *wenn* sie importiert wird, *dann* entsteht keine Liste, und die Meldung nennt die Zeile.
- *Gegeben* eine Liste verlangt 3 Ash Blossom & Joyous Spring und die Sammlung hat 1 Original und 1 Proxy, *wenn* die Fehlkarten berechnet werden, *dann* fehlt 1.
- *Gegeben* Cube-Liste A und Deckliste B verlangen je 1 Ash Blossom & Joyous Spring und die Sammlung hat 1, *wenn* die Fehlkarten berechnet werden, *dann* fehlt sie in keiner der beiden Listen.
- *Gegeben* einer Liste fehlen 2 Ash Blossom & Joyous Spring, *wenn* der Owner die Fehlkarten als Text exportiert, *dann* enthält der Export die Zeile `2 Ash Blossom & Joyous Spring`.
- *Gegeben* einer Liste fehlt 1 Dark Magician, *wenn* der Owner die Fehlkarten als `.ydk` exportiert, *dann* enthält der Export den Passcode 46986414 einmal.
- *Gegeben* eine importierte Deckliste, *wenn* der Owner sie als `.ydk` exportiert und die Datei erneut importiert, *dann* verlangen beide Listen dieselben Karten in denselben Abschnitten.

## 6. Eigene Listen

**Versprechen**

- Eine **Eigene Liste** ist gleich aufgebaut wie Cube- und Deckliste. Fehlkarten und Export funktionieren genauso.
- Sie lässt sich bearbeiten: Karte per Namenssuche hinzufügen, Menge ändern, Karte entfernen, umbenennen, löschen.
- **„Filterergebnis als Eigene Liste übernehmen“** erzeugt eine einmalige Kopie der gefilterten Karten. Spätere Änderungen an der Sammlung ändern die Liste nicht.

**Szenarien**

- *Gegeben* eine leere Eigene Liste, *wenn* der Owner Dark Magician mit Menge 2 hinzufügt, *dann* verlangt die Liste 2 Dark Magician.
- *Gegeben* ein Filter liefert 5 Karten, *wenn* der Owner das Ergebnis als Eigene Liste übernimmt und danach eine weitere passende Karte bucht, *dann* enthält die Liste weiterhin genau die 5 Karten.
- *Gegeben* eine Eigene Liste verlangt 2 Dark Magician und die Sammlung hat 1, *wenn* der Owner die Fehlkarten exportiert, *dann* enthält der Text `1 Dark Magician`.

## Nicht im MVP

- **Von Hand buchen:** Unerkannte Exemplare bleiben außerhalb der Sammlung. Kommt wieder auf, wenn es den Owner stört.
- **Proxy umschalten an älteren Exemplaren:** Wer sich vertan hat, löscht das Exemplar und scannt im Proxy-Modus neu.
- **Gespeicherte Filter** (dynamische Listen): Es gibt nur die einmalige Kopie als Eigene Liste.
- **Cube-Diff und automatisches Nachziehen:** Nachziehen heißt erneut importieren.
- **CSV-Import für Cubes:** kommt erst, wenn der inoffizielle Endpunkt bricht.
- **ATK/DEF-Filter und Textsuche** im Kartentext.
- **Vollständige deutsche Kartennamen (YGOResources):** Die Erkennung arbeitet am Bild, und die Suche kommt mit den deutschen Namen von YGOProDeck aus.
- **Live-Ansicht der Scan-Sitzung** auf Laptop oder Heimrechner.
- **Wake-on-LAN:** Vor dem Scannen reicht der Erreichbarkeits-Check.
- **Mehrbenutzerbetrieb,** Accounts, Hosting im Internet, iOS, Scannen ohne Heimnetz.
- **Druck, Rarität, Sprache, Zustand, Preise** eines Exemplars; Draften und Deckbau.
