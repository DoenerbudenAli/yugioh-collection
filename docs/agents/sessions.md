# Agenten-Sessions

Wo eine Session läuft, hängt von der Arbeit ab ([ADR 0005](../adr/0005-agenten-isolation.md), [ADR 0011](../adr/0011-harness-arbeit-auf-dem-host.md)):

| Arbeit | Wo | Unter wem |
|---|---|---|
| Harness (Regeln, CI, Broker, Devcontainer, ihre Doku) | Claude-Code-App auf dem Host | Owner |
| Features, Code außerhalb des Harness | Container, `just agent bau <name>` | `<app-slug>[bot]`, Rolle *Bau* |
| Wayfinder, Grilling, Triage, Research | Container, `just agent planung <name>` | `<app-slug>[bot]`, Rolle *Planung* |

Login, `gh`-Konfiguration und Credential-Helper des Owners gelangen nie in einen Container.

## Ablauf im Container

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

- Harness-Arbeit macht der Owner in der App auf dem Host. Der lokale Clone pusht Branches, auf `main` nur per PR.
- Owner-PRs brauchen kein Approval, das Kern-Gate greift dort nicht. Negativproben, die eine Merge-Sperre beweisen, laufen deshalb als Bot-PR aus `just agent bau probe`.
- Einstellungen am Repo ändert der Owner im Browser.
- Notbremse: [Kill-Switch im Broker-README](../../broker/README.md#kill-switch).
