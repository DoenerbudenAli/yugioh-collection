# Kartendatenquelle: YGOProDeck-API, Cube- und .ydk-Format

Research zu Issue #2. Stand der Messungen: 2026-10-04 (YGOProDeck `database_version` 147.22, letzte Aktualisierung 2026-10-02).
Alle Zahlen stammen aus echten Abrufen an diesem Tag; Quellen stehen bei jeder Aussage.

## Kurzfazit / Empfehlung

- **YGOProDeck eignet sich als Hauptquelle für den Katalog.** Ein einziger Aufruf ohne Parameter liefert alle ~14 600 Karten als JSON (~25 MB). Die Doku verlangt ausdrücklich, Daten und Bilder lokal zu speichern. Limit: 20 Anfragen/s, bei Überschreitung 1 h Sperre.
- **Die Karte darf nicht über das Top-Level-`id` identifiziert werden.** Bei Karten mit Alt-Arts wechselt das „Haupt“-`id` je nach Abfrage und Sprache (z. B. Dark Magician: 46986420 im englischen Gesamtabzug, 46986414 im deutschen Abzug und bei der Einzelabfrage). Stabil ist nur die **Menge aller Passcodes** in `card_images[].id`. Empfehlung: eigene interne Karten-ID, dazu eine Tabelle Passcode → Karte, die *alle* Passcodes aus `card_images` enthält. Als sprachübergreifender Zweitschlüssel eignet sich die `konami_id` aus `misc=yes`.
- **Bei deutschen Namen hat YGOProDeck eine große Lücke.** Deutsche Übersetzungen gibt es praktisch nur für Karten bis September 2022. **2 483 von 14 011 TCG-Karten** haben keinen deutschen Eintrag, darunter fast alles ab 2023. **YGOResources** (`db.ygoresources.com`) schließt die Lücke über die Konami-ID: 13 897 von 14 011 TCG-Karten lassen sich dort einem deutschen Namen zuordnen. Empfehlung: Katalog = YGOProDeck (Passcodes, englische Namen, Bilder) + deutsche Namen aus YGOResources über `konami_id`, mit den YGOProDeck-DE-Daten als Rückfall.
- **Cube-Listen lassen sich ohne Login maschinell beziehen** über `POST https://ygoprodeck.com/api/cube/downloadCube.php` mit `cubeid=<n>`. Die Antwort ist JSON mit `name`, `id` (Passcode), `type` und `quantity`. Getestet mit Cube 10400: 303 Karten, alle im Katalog auflösbar. Der Endpunkt ist **nicht dokumentiert**: Er wird intern vom „Download Cube (.csv)“-Button genutzt und kann sich jederzeit ändern.
- **`.ydk` ist eine Textdatei mit einem Passcode pro Zeile und Exemplar.** `#main` und `#extra` sind Kommentar- bzw. Abschnittszeilen, ab `!side` beginnt das Side Deck. Beim Import müssen Passcodes über die Passcode-Tabelle auf die Karte abgebildet werden (wegen Alt-Arts). Beim Export sollte der „kanonische“ Passcode geschrieben werden.
- **Die offizielle Konami-Datenbank kommt als Quelle nicht in Frage.** Ihre Nutzungsbedingungen verbieten Scraping und den Aufbau einer Datenbank durch systematisches Herunterladen ausdrücklich. ProjectIgnis/EDOPro (`BabelCDB`) taugt als Cross-Check für Passcodes und Alt-Art-Aliase, enthält aber nur englische Namen.

## Befunde

### 1. YGOProDeck-API: Endpunkte, Felder, Bedingungen

**Endpunkt und Abruf des Gesamtkatalogs**
- Die Doku nennt `https://db.ygoprodeck.com/api/v7/cardinfo.php` als „the only endpoint that is now needed“. Ohne Parameter liefert er alle Karten („The only way to return all cards now is by having 0 parameters“). Quelle: [API Guide](https://ygoprodeck.com/api-guide/).
- Gemessen: `cardinfo.php?misc=yes` liefert 14 597 Einträge mit 24,9 MB, `…&language=de&misc=yes` liefert 11 769 Einträge mit 21,9 MB.
- Für Änderungen gibt es `https://db.ygoprodeck.com/api/v7/checkDBVer.php` → `[{"database_version":"147.22","last_update":"2026-10-02 00:03:40"}]`. Der Endpunkt ist laut Doku ungecacht, und die Version steigt, sobald Karten hinzukommen oder sich ändern. Quelle: API Guide, Abschnitt „Check Database Version“; selbst abgerufen.
- Antworten von `cardinfo.php` werden serverseitig 2 Tage gecacht. Quelle: API Guide („cached for 2 days (172800 seconds)“). Der beobachtete Header war `Cache-Control: max-age=1800`.

**Nutzungsbedingungen (alle aus dem [API Guide](https://ygoprodeck.com/api-guide/))**
- Lokale Kopie ist ausdrücklich verlangt: „Please download and store all data pulled from this API locally … Failure to do so may result in either your IP address being blacklisted“.
- Rate Limit: 20 Anfragen pro Sekunde, bei Überschreitung 1 Stunde Sperre.
- Bilder: Sie sollen *nicht* fortlaufend gehotlinkt werden: „You must download and store these images yourself! Please only pull an image once and then store it locally“. Wer sehr viele Bilder pro Sekunde zieht, riskiert eine IP-Sperre.
- Die API ist kostenlos („completely free to use“). Einen eigenen ToS-Text gibt es nicht: `/terms-of-service/`, `/terms/` und `/tos/` liefern 404, und die Datenschutzerklärung regelt die API nicht. Laut Footer liegen Kartentexte und Kartenbilder urheberrechtlich bei 4K Media/Konami. Für eine private, nicht gehostete Einzelnutzer-App sind die Bedingungen erfüllt, solange einmalig geladen und lokal gespeichert wird. (Das ist keine Rechtsberatung.)

**Felder pro Karte** (selbst abgerufen, Doku-Abschnitt „Response Information“)
- `id`: laut Doku „ID or Passcode of the card“; Fallstrick dazu siehe Abschnitt 4. Weitere Felder: `name`, `type`, `frameType`, `desc`, `atk`/`def`/`level`/`race`/`attribute`, `archetype`, `card_sets` (nur englische Set-Codes, siehe offenes [Issue #522](https://github.com/AlanOC91/YGOPRODeck/issues/522)), `card_prices`, `banlist_info`.
- `card_images[]`: enthält je Artwork `id` (den Passcode dieser Artwork), `image_url`, `image_url_small` und `image_url_cropped`. Laut Doku: „Alternative artwork (if available) will also be listed within the card_images array.“
- Mit `misc=yes` kommt `misc_info[]` hinzu. Darin sind gemessen enthalten: `konami_id` (bei 14 391 von 14 597 Karten), `beta_id`/`beta_name` (Vorab-ID bzw. Vorab-Name), `treated_as`, `formats` (u. a. TCG, OCG, Speed Duel, Master Duel), `tcg_date` und `ocg_date`, `has_effect`.
- Die Doku zu `konami_id`: „The Konami ID of the card. This is not the passcode.“

**Sprachen**
- Unterstützte Sprachen: `language=de|fr|it|pt`. „Card images are only stored in English.“ Neu geleakte Karten gibt es zunächst nur auf Englisch. Laut Doku ist jede Sprache „over 9000 cards translated“. Quelle: API Guide, Abschnitt „Endpoint Languages“.
- Deutsche Einträge haben `name` auf Deutsch und zusätzlich `name_en`. Beispiel `id=46986414&language=de` → `"name":"Dunkler Magier"`, `"name_en":"Dark Magician"`. Selbst abgerufen.
- Der Parameter `name=` erwartet den exakten Namen *in der abgefragten Sprache*. `name=Dark Magician&language=de` liefert einen Fehler.
- **Gemessene Lücke:** 2 483 von 14 011 TCG-Karten fehlen im deutschen Datensatz. Fast alle davon haben ein `tcg_date` ab 2022: 2022: 172, 2023: 630, 2024: 556, 2025: 531, 2026: 568. Die jüngsten deutschen Einträge stammen im Wesentlichen vom 2022-09-29; danach kommen nur noch 3 Karten. Beispiel: `id=9674034` (Snake-Eye Ash, 2023) mit `language=de` → „No card matching your query“.
- Außerdem haben 630 deutsche Einträge `name == name_en`. Ein Teil davon ist korrekt, weil manche Namen in allen Sprachen gleich sind („Abaki“), ein Teil sind vermutlich unübersetzte Platzhalter („Altergeist Hexstia“). Das ist **nicht im Einzelnen geprüft**.

**Bilder**
- Die URLs folgen dem Muster `https://images.ygoprodeck.com/images/{cards|cards_small|cards_cropped}/<passcode>.jpg`. Quelle: API Guide.
- Gemessen am Beispiel 46986414: Die große Version hat 813×1185 px und 153 KB, die kleine 28 KB. Header: `Cache-Control: public, max-age=2678400`.
- Bei ~14 770 Artwork-IDs ergibt das *geschätzt* rund 2 GB für die großen und rund 0,4 GB für die kleinen Bilder. Die Hochrechnung basiert auf nur einer Stichprobe.
- Alle Bilder zeigen **englische** Karten. Für die Erkennung deutscher Exemplare eignet sich deshalb eher das sprachneutrale Artwork (`cards_cropped`) als die ganze Karte. Das gehört zur Erkennungs-Recherche.

### 2. Cube-Liste maschinell beziehen (konkret getestet)

- Die Seite `https://ygoprodeck.com/cube/view-cube/10400` („Goat Arena Cube (303 cube)“) hat einen Button „Download Cube (.csv)“. Er ruft per jQuery `$.ajax({url:'/api/cube/downloadCube.php', type:'POST', data:{cubeid:10400}})` auf und baut die CSV erst im Browser aus `data.cube_list` zusammen, Spalten `id,name,type,quantity`. Quelle: Seitenquelltext von view-cube/10400, Funktion `downloadCube()`.
- Getestet mit `curl -X POST -d "cubeid=10400" https://ygoprodeck.com/api/cube/downloadCube.php`. Ergebnis: HTTP 200 ohne Cookie und ohne Login, Antwort `{"success":"Cube list retrieved successfully.","cube_list":[{"name":"4-Starred Ladybug of Doom","id":83994646,"type":"Flip Effect Monster","quantity":1}, …]}`. Das sind 303 Einträge, alle mit `quantity` 1.
- Alle 303 IDs ließen sich über die Passcode-Tabelle (alle `card_images[].id`) auflösen. Eine davon, Blue-Eyes Ultimate Dragon `23995346`, ist **nicht** das Top-Level-`id` des englischen Gesamtabzugs (dort `23995348`). Eine Auflösung nur über das Top-Level-`id` wäre also schon in diesem Cube einmal gescheitert.
- Weder der Endpunkt noch die Cube-Funktion stehen im API Guide. Die Schnittstelle ist inoffiziell und kann ohne Ankündigung brechen. Als Rückfallebene eignen sich die CSV-Datei, die der Owner manuell herunterlädt (gleiche Spalten), oder Copy & Paste einer Namensliste.

### 3. `.ydk`-Format

Es gibt keine formale Spezifikation. Maßgeblich ist das Verhalten der Clients, die das Format eingeführt haben bzw. heute verbreiten:

- **Schreiben (EDOPro):** `#created by <Name>`, dann `#main`, je Exemplar eine Zeile mit dem Passcode in Dezimalschreibweise, dann `#extra`, dann `!side`. Optional steht vor jeder Zeile ein Namenskommentar `# <Kartenname>`. Quelle: [`edopro/gframe/deck_manager.cpp`](https://github.com/edo9300/edopro/blob/master/gframe/deck_manager.cpp), `SaveDeck` und `MakeYdkEntryString`.
- **Lesen (EDOPro, `LoadCardList`):**
  - Leere Zeilen werden ignoriert. Zeilen mit `#` werden ignoriert, außer genau `#extra`, das den Extra-Abschnitt beginnt.
  - Eine Zeile mit `!` beginnt den Side-Abschnitt.
  - Jede andere Zeile, die eine Ziffer enthält, wird mit `std::stoul` gelesen. Es zählt also nur die führende Zahl.
  - Tokens werden verworfen. Unbekannte Passcodes werden übersprungen bzw. als Fehler gemeldet.
- **Lesen (Original-YGOPro, `LoadDeckFromStream`):** `!` beginnt den Side-Abschnitt. Zeilen, die nicht mit einer Ziffer beginnen, werden ignoriert, auch `#main` und `#extra`. Main- und Extra-Karten landen also in *einer* Liste, und `LoadDeck` sortiert sie nach Kartentyp (Fusion/Synchro/Xyz/Link → Extra). Quelle: [`ygopro/gframe/deck_manager.cpp`](https://github.com/Fluorohydride/ygopro/blob/master/gframe/deck_manager.cpp).
  - Folgerung für den Import: Beim Ermitteln der Fehlkarten zählen alle Abschnitte gleich, also werden main, extra und side einfach summiert. Ob das Side Deck mitzählt, sollte als Option wählbar sein.
- **Passcodes mit führender Null** stehen ohne Nullen in der Datei (z. B. `295517` für den gedruckten Code `00295517`). Grund: Die Werte werden als Zahl geparst und geschrieben (`std::to_string`).
- **Variante `ydke://`:** `ydke://<main>!<extra>!<side>!`, jeder Teil ist Base64 eines Arrays von Little-Endian-uint32-Passcodes. Quelle: EDOPro `ExportDeckYdke`; Bibliothek [ProjectIgnis/ydke.js](https://github.com/ProjectIgnis/ydke.js). Optional als zweites Importformat.
- **Alt-Arts in `.ydk`:** Decklisten können jede Artwork-Variante enthalten (z. B. `46986415` statt `46986414`). Original-YGOPro gilt ein Passcode als Alternativ-Artwork, wenn `alias` gesetzt ist und weniger als 20 vom eigenen Code entfernt liegt (`CARD_ARTWORK_VERSIONS_OFFSET = 20`). Quelle: [`ygopro/gframe/data_manager.cpp`](https://github.com/Fluorohydride/ygopro/blob/master/gframe/data_manager.cpp). EDOPro fasst beim Namensexport mit Abstand < 10 zusammen. Die Regel ist jedoch **nicht vollständig**, siehe Abschnitt 4.
- **Export-Empfehlung:** Pro Karte genau einen Passcode schreiben, und zwar den Basis-Passcode (in der CDB `alias == 0`, bzw. das kleinste/„Original“-Artwork). Pro Exemplar eine Zeile. Die Abschnitte main/extra/side der Quellliste sollten erhalten bleiben, wenn sie bekannt sind. Bei einer Fehlkartenliste aus einem Cube kann einfach alles unter `#main` stehen; die Clients sortieren Extra-Deck-Karten selbst.

### 4. Fallstricke

**Mehrere Passcodes pro Karte (Alt-Arts)**
- In YGOProDeck haben 125 Karten mehr als ein Artwork, zusammen 172 zusätzliche Passcodes (gemessen). Spitzenreiter sind Dark Magician mit 9 und Blue-Eyes White Dragon mit 8.
- Das Top-Level-`id` ist **nicht stabil**. Bei 32 Karten ist es nicht der kleinste Passcode der Gruppe. Bei 14 Karten unterscheidet es sich zwischen englischem und deutschem Gesamtabzug, z. B. Dark Magician 46986420 vs. 46986414 und Cyber Dragon Infinity 10443958 vs. 10443957.
- Eine Einzelabfrage per Alt-Art-ID (`id=46986420`) liefert einen Eintrag mit genau *einem* Bild statt aller neun. Erst der Gesamtabzug gruppiert die Artworks.
- Daraus folgt: Die Passcode-Tabelle wird aus *allen* `card_images[].id` des Gesamtabzugs gebaut, und die Karte bekommt eine eigene stabile ID. Ein Fremdschlüssel auf das YGOProDeck-`id` ist zu vermeiden.
- Alt-Art-Passcodes liegen nicht immer nah beieinander: Dark Magician `36996508` → `46986414` und Polymerization `27847700` → `24094653`. Sowohl die 20er-Regel von YGOPro als auch die 10er-Regel von EDOPro übersehen solche Fälle. YGOProDeck gruppiert beide korrekt unter dieselbe Karte (gemessen).
- Umgekehrt zeigt das `alias`-Feld der EDOPro-CDB auch auf *andere* Karten, die nur regeltechnisch „als“ eine Karte behandelt werden. Beispiele: Harpie Lady 1/2/3 → Harpie Lady, Mecha Phantom Beast Token-Varianten, „A Legendary Ocean“ → „Umi“ (45 Zeilen in `cards.cdb` mit Abstand ≥ 20). Nach `CONTEXT.md` sind das **eigene Karten**, weil sie andere Namen und andere Texte haben. YGOProDeck führt sie als eigene Einträge mit `misc_info.treated_as`.
- Bei 129 Einträgen ist `treated_as` gleich dem eigenen Namen. Das betrifft gerade Karten mit Alt-Arts und hat für die Identität keine Bedeutung.

**Karten ohne (echten) Passcode**
- 202 Einträge haben IDs ≥ 100 000 000 (gemessen). Davon sind 124 Skill Cards (Speed Duel, Bereich `300ZYYXXX`).
- Der Rest sind vorab angekündigte Karten mit neunstelliger Vorab-ID (`10ZZYYXXX` u. a.), z. B. „Angelechy Castellan“ `101402090` (TCG, noch ohne offiziellen Passcode).
- Hinzu kommt der Platzhalter „???“ `149694341`.
- Das Schema der Vorab-IDs ist dokumentiert in [ProjectIgnis/BabelCDB README](https://github.com/ProjectIgnis/BabelCDB), „Guidelines for passcodes“.
- Bei Erscheinen bekommt eine solche Karte ihren echten Passcode, und YGOProDeck vermerkt die alte ID in `misc_info.beta_id` (bei 3 949 Karten vorhanden). Eine Cube- oder `.ydk`-Liste aus der Vorabphase kann also veraltete IDs enthalten. Beim Import sollte deshalb zusätzlich `beta_id` → Karte gemappt werden.
- Spielsteine (106 Tokens) haben teils Passcodes, teils nicht. EDOPro verwirft Tokens beim Deck-Laden. Für die Sammlung sind sie Randfälle.
- 27 TCG-Karten haben keine `konami_id`, überwiegend sehr neue Karten und Tokens.

**Fehlende deutsche Namen**
- Siehe Abschnitt 1: rund 2 500 TCG-Karten ab 2022 fehlen bei YGOProDeck auf Deutsch.
- Hinzu kommen 378 OCG-only-Karten (nur Japan), die naturgemäß keinen deutschen Namen haben. Für eine deutsch/englisch gemischte Sammlung spielen sie keine Rolle.

**Weitere**
- 14 deutsche Einträge haben ein Top-Level-`id`, das im englischen Abzug nicht als Top-Level-`id` vorkommt. Das sind genau die Alt-Art-Fälle oben, also derselbe Fallstrick.
- `card_sets` enthält nur englische Set-Codes wie `LOB-EN005`. Deutsche Codes wie `LOB-G003` oder `SYE-DE001` liefert YGOProDeck nicht ([Issue #522](https://github.com/AlanOC91/YGOPRODeck/issues/522)), YGOResources dagegen schon (siehe Abschnitt 5).

### 5. Alternativen als Katalogquelle

| Quelle | Passcodes | DE-Namen | Bilder | Bedingungen | Eignung |
|---|---|---|---|---|---|
| **YGOProDeck API** | ja, inkl. Alt-Arts in `card_images` | bis ~09/2022 | ja, nur EN-Karten | lokal speichern, 20 req/s, Bilder einmal laden | **Hauptquelle** |
| **YGOResources** (`db.ygoresources.com`) | **nein**, nur Konami-ID | ja, aktuell | nein | nicht die ganze DB abfragen, cachen; für Offline-Komplettbedarf „get in touch“ | **Ergänzung für DE-Namen** über `konami_id` |
| **Konami Neuron / offizielle DB** | nein (nur cid) | ja | ja | Scraping und systematischer DB-Aufbau verboten | ungeeignet |
| **ProjectIgnis BabelCDB** (EDOPro) | ja, inkl. `alias` | nein (nur EN) | nein (separat) | keine Lizenzangabe | Cross-Check und Rückfall für Passcodes |

- **YGOResources:**
  - Die [API-Doku](https://db.ygoresources.com/about/api) nennt `/data/card/<konamiId>` (Kartendaten je Sprache: `ae, cn, de, en, es, fr, it, ja, ko, pt`, jeweils `name`, `effectText`, `prints`) und `/data/idx/card/name/<en|ja|de|fr|it|es|pt|ko>` (Name → Konami-ID).
  - Änderungen lassen sich über den Header `X-Cache-Revision` und `/manifest/<revision>` verfolgen.
  - Wörtliche Bitte der Betreiber: „Please don't query the entire database. Only query data as you need it, and cache that data locally. (If you have a use case that requires offline access to all the data, get in touch. We can just send you a file.)“
  - Gemessen: Der DE-Namensindex hat 13 964 Namen. Von den 2 460 bei YGOProDeck fehlenden TCG-Karten mit `konami_id` hat YGOResources **2 418** auf Deutsch. Insgesamt sind 13 897 von 14 011 TCG-Karten über `konami_id` mit einem deutschen Namen verknüpfbar.
  - Ein Abruf des Namensindex (eine Anfrage) ist mit den Bedingungen vereinbar. Für die vollen Kartendaten aller Karten (~14 000 Einzelabrufe) sollte man dagegen **vorher die Betreiber kontaktieren**.
  - `/data/card/<id>` enthält pro Sprache `prints` mit deutschen Set-Codes, z. B. Dark Magician: `LOB-G003`, `SYE-DE001`. Das ist potenziell nützlich, wenn die Erkennung den Set-Code per OCR liest.
  - Der in der Doku genannte Index `/data/meta/index/printcode` liefert derzeit 404, die Doku ist an dieser Stelle veraltet.
- **Konami:** Die DE-Kartenseite `db.yugioh-card.com/yugiohdb/card_search.action?ope=2&cid=4041&request_locale=de` zeigt „Dunkler Magier“. Die verlinkten [Nutzungsbedingungen](https://legal.konami.com/games/neuron/terms/tou/en/) verbieten jedoch u. a.: „Create a database by systematically downloading and storing Materials.“ und „Use any robot, spider, … to retrieve, index, ‚scrape‘, ‚data mine‘ … without Konami's express prior written consent.“
- **ProjectIgnis:**
  - [`BabelCDB/cards.cdb`](https://github.com/ProjectIgnis/BabelCDB) ist eine SQLite-Datei mit den Tabellen `datas(id, alias, …)` und `texts(id, name, desc, …)`. Sie hat 14 759 Zeilen und wird täglich gepflegt (letzter Commit 2026-10-03).
  - Ein deutsches Gegenstück [`BabelCDB-Deutsch`](https://github.com/ProjectIgnis/BabelCDB-Deutsch) enthält nur `strings.conf` (UI-Texte) und ist seit 2020 archiviert, liefert also **keine** deutschen Kartennamen.
  - Abgleich mit YGOProDeck: 363 YGOProDeck-Passcodes fehlen in `cards.cdb` und 353 CDB-IDs fehlen in YGOProDeck. Die Ursache sind vermutlich Vorab-, Rush- und Skill-Karten, die in anderen `.cdb`-Dateien liegen bzw. anders geführt werden. Das ist **nicht im Einzelnen geprüft**.

## Offene Punkte

- **Lizenz und Bedingungen schriftlich klären (optional):** YGOProDeck hat keinen eigenen ToS-Text. YGOResources bietet für Offline-Komplettbedarf eine Datei an, eine Anfrage beim Betreiber (Discord) wäre der saubere Weg, falls mehr als der Namensindex gebraucht wird.
- **Stabilität von `downloadCube.php`:** Die Schnittstelle ist inoffiziell. Es ist offen, ob private oder unlisted Cubes ohne Login ebenfalls funktionieren; getestet wurde nur der öffentliche Cube 10400.
- **Qualität deutscher Namen:** Die 630 YGOProDeck-DE-Einträge mit `name == name_en` und die Abweichungen zwischen YGOProDeck-DE und YGOResources-DE wurden nicht stichprobenartig geprüft. Ebenfalls offen ist, welche Quelle bei Widerspruch gewinnt; empfohlen ist YGOResources, weil es näher an Konami liegt.
- **Bildbedarf:** Ob für die Erkennung große Bilder, kleine Bilder oder nur `cards_cropped` nötig sind (Speicher ~0,4–2 GB), entscheidet die Erkennungs-Recherche. Deutsche Kartenbilder gibt es bei keiner der freien Quellen.
- **Kanonischer Passcode beim Export:** Vorschlag ist der kleinste Passcode der Gruppe bzw. der mit `alias == 0` in der CDB. Noch zu entscheiden; Dark Magician wäre damit `36996508` (kleinster) statt `46986414` (Original, `alias == 0`). Zu bevorzugen ist daher die CDB-Regel `alias == 0` bzw. das älteste Artwork.
- **Rush-Duel- und Speed-Duel-Karten:** Diese Karten im Katalog auszuschließen (Filter `formats` enthält TCG oder OCG) erscheint sinnvoll, ist aber eine Produktentscheidung.
