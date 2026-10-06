# Agenten-Sessions

Jede Agenten-Session zu diesem Repo läuft in einem eigenen Container, auch Planung und Wayfinder ([ADR 0005](../adr/0005-agenten-isolation.md)). Auf dem Host gibt es keine GitHub-Credentials. Eine Local-Session auf dem Host kann das Repo also lesen, aber nichts auf GitHub schreiben.

## Ablauf

Aus PowerShell im Repo-Ordner:

```powershell
just agent planung <name>   # Session starten oder fortsetzen
just agent bau <name>
just weg <name>             # nach dem Merge: Container samt Volume wegwerfen
```

- **Ein Container pro Strang**, also pro Ticket oder Session. Der Name sagt, worum es geht, z. B. `planung-62` oder `bau-70`.
- **Fortsetzen** mit demselben Befehl, auch nach einem Neustart des PCs. Ein vorhandener Container behält seine Rolle.
- Technik, Netz und Skills im Container: [.devcontainer/README.md](../../.devcontainer/README.md).

## Welche Rolle wofür

| Rolle | Darf | Für |
|---|---|---|
| *Planung* | Issues schreiben, Code lesen | Wayfinder, Grilling, Triage, Research-Kommentare |
| *Bau* | Code und PRs schreiben, Issues lesen | Bau-Tickets, Features, PRs mit ADRs, Glossar oder Research-Dateien |

Die Rechte stehen in `harness.toml` unter `[broker.rollen.*]`. Braucht eine Planungs-Entscheidung eine Datei im Repo (ADR, `CONTEXT.md`), öffnet eine Session mit der Rolle *Bau* den PR. Die Planungs-Session kann keinen Branch pushen.

## Owner

- Reviewen, approven, mergen und Einstellungen ändern geht nur im Browser.
- Eigene Änderungen macht der Owner auf github.dev (im Repo die Taste `.` drücken). Commit und PR laufen dort unter dem Owner.
- Der lokale Clone holt anonym (`git pull`) und ist nur zum Lesen da.
- Notbremse: [Kill-Switch im Broker-README](../../broker/README.md#kill-switch).
