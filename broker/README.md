# Broker für Rollen-Tokens

Ein kleiner Dienst auf dem Windows-Host. Er hält den Private Key der GitHub App und stellt Agenten im Container auf Anfrage ein Installation-Token aus: 1 h gültig, nur für dieses Repo, nur mit den Rechten ihrer Rolle ([ADR 0005](../docs/adr/0005-agenten-isolation.md), „Broker“, „Rollenbindung“). Den Key sieht kein Agent, und auch der Owner-User kann ihn nicht entschlüsseln.

## Schnittstelle

Der Broker hört nur auf `127.0.0.1:<port>`. Docker Desktop leitet `host.docker.internal` aus Containern dorthin, das Heimnetz erreicht ihn nicht.

| Anfrage | Authorization | Körper | Antwort |
|---|---|---|---|
| `POST /schluessel` | `Bearer <admin-geheimnis>` | `{"schluessel", "rolle", "ablauf"}` (Unix-Sekunden) | `204`, sonst `400`/`403` |
| `POST /schluessel/abmelden` | `Bearer <admin-geheimnis>` | `{"schluessel"}` | `204` |
| `POST /token` | `Bearer <schluessel>` | `{"rolle"}` | `200 {"token", "expires_at"}`, sonst `403`, bei GitHub-Fehler `502` |

- **Admin-Geheimnis:** erzeugt der Broker bei jedem Start neu und schreibt es nach `<daten>\admin-geheimnis`. Lesen darf es nur der Owner-User, ein Container sieht die Datei nie. `just agent` meldet damit Schlüssel an und ab. Ein Neustart wirft alle Anmeldungen weg.
- **Schlüssel:** zufällig, mindestens 16 Zeichen, einer pro Container. Tokens gibt es nur bis zum Ablauf und nur in der angemeldeten Rolle.
- **Rollen und Rechte** stehen in `harness.toml` unter `[broker.rollen.*]`, App-ID und Installation unter `[github_app]`.
- **Log:** `<daten>\broker.log`, ohne Schlüssel und Tokens.

## Ablage auf dem Host

| Was | Wo | Rechte |
|---|---|---|
| Code aus `origin/main`, Abhängigkeiten in `broker\lib` | `C:\Program Files\harness-broker\quelle\` | nur Admins schreiben |
| Python | `C:\Program Files\Python313\` (python.org, für alle Benutzer) | nur Admins schreiben |
| Key (DPAPI des Dienstkontos), Admin-Geheimnis, Log | `C:\ProgramData\harness-broker\` | Dienstkonto ändern, Owner lesen |
| Dienstkonto | lokaler User `harness-broker`, Passwort in Bitwarden | – |
| Autostart | Aufgabe `harness-broker` in der Aufgabenplanung, beim Systemstart | – |

Code und Python liegen außerhalb des Benutzerordners des Owners, denn dort könnte jeder Agent unter dessen Login Code ändern, den dann das Dienstkonto ausführt. Gestartet wird über `dienst.py` mit dem System-Python, nicht über einen venv-Launcher: Dessen Unterprozess beendet „Aufgabe stoppen“ nicht mit.

## Einrichten und aktualisieren

Einrichten: `einrichten.sh` in Git Bash (`"C:\Program Files\Git\bin\bash.exe" broker/einrichten.sh`), nachdem der Broker auf `main` gemergt ist. Der Wizard führt durch Dienstkonto, Installation, Key-Import, Autostart und Abnahme.

Aktualisieren nach einem Merge auf `main`: im Wizard nur Stufe 3 (Code holen) ausführen, dann die Aufgabe neu starten (`Stop-ScheduledTask harness-broker; Start-ScheduledTask harness-broker` im Admin-Fenster).

`requirements.txt` ist aus `uv.lock` erzeugt (`uv export --frozen --no-dev --no-emit-project --format requirements.txt -o requirements.txt`) und wird mit `--require-hashes` installiert. Nach jeder Änderung an den Abhängigkeiten neu erzeugen.

Wird das Passwort des Dienstkontos zurückgesetzt statt geändert, ist der DPAPI-Schlüssel verloren: Key neu importieren (Stufe 5).

## Kill-Switch

1. **Broker stoppen:** im Admin-Fenster `Stop-ScheduledTask harness-broker` (für dauerhaft zusätzlich `Disable-ScheduledTask harness-broker`). Ab sofort gibt es keine neuen Tokens mehr. Ausgestellte Tokens laufen spätestens nach 1 h ab.
2. **Installation sperren:** <https://github.com/settings/installations> → `kaiba-agent` → **Configure** → ganz unten **Suspend**. Danach lehnt GitHub auch bereits ausgestellte Tokens ab.
3. **`setup-token` widerrufen** (ADR 0005, Claude-Zugang).

## Restrisiken

- Ein Admin (also der Owner nach einer UAC-Bestätigung) kann den Key aus dem Speicher des laufenden Brokers lesen. Agenten laufen ohne Admin-Rechte. Eine UAC-Abfrage, die man nicht selbst ausgelöst hat, also immer ablehnen.
- Jeder Prozess unter dem Owner-Login kann das Admin-Geheimnis lesen und sich ein Rollen-Token holen. ADR 0005 nimmt das hin: Mehr als ein Rollen-Token bekommt er nicht.

## Entwicklung

```bash
uv run python -m pytest
uv run python -m ruff check . && uv run python -m ruff format --check .
uv run python -m pyright
```

Unter Windows mit Smart App Control braucht `uv` ein signiertes Python: `uv venv --python "C:\Program Files\Python313\python.exe"`. Die Launcher `pytest.exe` usw. werden blockiert, deshalb `python -m`.
