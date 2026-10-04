# Systemtopologie

Das System läuft als zwei Deployables im Heimnetz. Der **Hauptdienst** läuft auf dem Raspberry Pi und enthält Katalog (samt Bildern), Sammlung, Listen, Erfassung und UI. Er ist die einzige maßgebliche Datenhaltung. Der **Erkennungsdienst** läuft auf dem Heimrechner und enthält nur das Modul Erkennung mit GPU-Adapter und Index. Das Handy ist ein reiner Client ohne eigene Daten, eine Cloud gibt es nicht. Wir haben uns so entschieden, weil nur der Pi immer an ist, die Erkennung unter 1 s aber die GPU des Heimrechners braucht, und weil eine einzige Datenhaltung jede Sync-Logik erspart.

## Regeln

- **Eine Komposition je Deployable.** Das präzisiert ADR 0001. Die Komposition des Hauptdienstes verdrahtet für die Erkennung einen Remote-Client-Adapter, der Erkennungsdienst den GPU-Adapter. Beide Adapter gehören dem Modul Erkennung und importieren nur dessen Kern, die Abhängigkeitsregel bleibt also unverändert.
- **Zugang:** Das Handy erreicht ausschließlich den Hauptdienst, über HTTPS hinter dem vorhandenen Reverse Proxy (Caddy) des Pi, unter einer eigenen Subdomain mit Let's-Encrypt-Zertifikat. Damit hat die Browser-Kamera einen Secure Context. Im Heimnetz geht der Weg direkt übers WLAN, von unterwegs über das vorhandene Tailnet.
- **Frame-Pfad:** Handy → Hauptdienst (Erfassung) → Erkennungsdienst. Der Hauptdienst bekommt in Docker eine feste CPU- und RAM-Reservierung und darf nicht auslagern, weil auf dem Pi weitere Dienste laufen (Immich, Paperless u. a.) und nur ~1 GB RAM frei ist.
- **Latenzgrenze:** Der Aufschlag durch den Pi wird gemessen und muss für 95 % der Frames unter 50 ms bleiben. Wird die Grenze gerissen, ziehen Erkennung und Erfassung gemeinsam auf den Heimrechner (siehe verworfene Alternativen).
- **Heimrechner aus:** Scannen ist gesperrt, Frames werden nicht gepuffert. Alles andere, auch die Prüf-Warteschlange, bleibt nutzbar.
- **Erreichbarkeit:** Der Erkennungsdienst meldet über einen Health-Endpunkt, ob er bereit ist und aus welchem Katalogstand sein Index gebaut wurde. Der Hauptdienst fragt ihn beim Öffnen der Scan-Ansicht und laufend während des Scannens ab. Ein veralteter Index sperrt das Scannen nicht. Der Hauptdienst zeigt einen Hinweis und stößt den Neuaufbau an. Ein Katalogstand, der aktualisiert wurde, während der Heimrechner aus war, wird so ohne Zusatzlogik nachgezogen.
- **Bilder für den Index:** Pull. Der Hauptdienst liefert eine Liste aus Karte, Bild-Adresse und Prüfsumme. Der Erkennungsdienst lädt nur fehlende Bilder und hält sie in einem Zwischenspeicher, den man jederzeit wegwerfen kann. Eigentümer der Bilder bleibt der Katalog.
- **Pi → Heimrechner:** fester Hostname per DHCP-Reservierung, unverschlüsseltes HTTP/WebSocket im LAN. Die Firewall des Heimrechners öffnet den Port nur für den Pi. Über die Leitung gehen nur Kartenfotos und Kandidaten.

## Verworfene Alternativen

- **Sammlung auf dem Heimrechner:** Er ist nur an, wenn er gebraucht wird. Ohne ihn gäbe es keine Fehlkarten.
- **Sammlung auf dem Handy mit Sync:** Das wäre ab dem ersten Tag ein Sync-Problem.
- **Frames puffern, wenn der Heimrechner aus ist:** Ein Scan endet, wenn die Karte das Bild verlässt, und braucht dafür Live-Feedback. Gepufferte Frames wären eine zweite Prüf-Warteschlange.
- **Erkennung und Erfassung auf dem Heimrechner, Pi nur Durchreiche:** Gemessen kostet der Pi ~1–2 % des Budgets von 1 s, eine Anfrage durch Caddy an einen Dienst auf dem Pi dauert über eine offene Verbindung ~10 ms. Dafür hätte es eine zweite Datenhaltung gebraucht (Prüf-Warteschlange nur bei laufendem Heimrechner), oder Remote-Adapter in beide Richtungen. Bleibt Rückfallweg, falls die Latenzgrenze gerissen wird.
- **Handy direkt zum Heimrechner:** Das hätte einen zweiten HTTPS-Einstiegspunkt mit eigenem Zertifikat unter Windows und CORS zwischen zwei Origins gebraucht.
- **Tailscale-Namen (`*.ts.net`) oder eigene CA:** Die vorhandene Domain mit Caddy und Let's Encrypt löst HTTPS bereits, so wie bei den übrigen Diensten auf dem Pi.
- **Cloud-Erkennung im MVP:** Sie ist nach der Research nicht nötig und bliebe als weiterer Adapter der Erkennung später ohne Topologie-Umbau möglich.
- **Push der Bilder bei jedem Indexaufbau:** Das wären bei jedem neuen Set 1–2 GB übers LAN statt ein paar hundert Bilder.
- **TLS/mTLS zwischen Pi und Heimrechner:** Über die Leitung gehen keine Geheimnisse, im Heimnetz genügt die Firewall-Regel.
