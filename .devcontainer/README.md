# Agenten-Container

Jede Agenten-Session läuft in einem eigenen Container aus diesem Ordner ([ADR 0005](../docs/adr/0005-agenten-isolation.md)). Der Container kennt nur zwei Geheimnisse: einen Schlüssel, mit dem er beim [Broker](../broker/README.md) ein 1-h-Rollen-Token holt, und das `setup-token` für Claude. Ins Netz darf er nur über die Allowlist.

## Bedienung

Aus PowerShell im Repo-Ordner:

```powershell
just agent bau <name>      # Container agent-<name> anlegen oder fortsetzen, Claude öffnen
just weg <name>            # Schlüssel abmelden, Container und Volume löschen
```

- **Rollen** stehen in `harness.toml` unter `[broker.rollen.*]`. Ein vorhandener Container behält seine Rolle.
- **Neu:** Das Skript erzeugt einen Zufallsschlüssel und meldet ihn für 24 h beim Broker an. Danach holt es das Image aus GHCR, legt das Volume `agent-<name>` an, startet den Container und öffnet Claude (`docker exec … claude`).
- **Fortsetzen:** Das Skript meldet denselben Schlüssel für weitere 24 h an. Das ist nach jedem Neustart des PCs nötig, weil der Broker beim Start alle Anmeldungen vergisst. Ein gestoppter Container wird neu gestartet und setzt dabei auch die Firewall neu.
- **`setup-token`** liegt in `%USERPROFILE%\.config\harness\claude-setup-token` und geht nur über die Umgebung von `docker exec` in den Container, nicht auf die Kommandozeile und nicht in die Container-Konfiguration. Ein neues Token wirkt beim nächsten `just agent`.
- **Nur abmelden**, ohne Container zu löschen: `python .devcontainer/agent.py abmelden <name>`.

Einrichtung und Abnahme auf einem neuen Rechner: `& "C:\Program Files\Git\bin\bash.exe" .devcontainer/einrichten.sh`.

## Im Container

| Was | Wo |
|---|---|
| Clone | `/arbeit/<repo>` im Volume `agent-<name>`, ein eigener pro Container |
| User | `agent` ohne sudo, ohne Capabilities, ohne Docker |
| git, gh | Credential-Helper `git-credential-broker` und Wrapper `/usr/local/bin/gh` holen das Token beim Broker. Es liegt bis 5 min vor Ablauf in `~/.cache/harness/token.json`. |
| Commits | als `<app-slug>[bot]` mit dessen noreply-Adresse (aus `harness.toml`) |
| Claude Code | `bypassPermissions` ist Standard, Telemetrie und Auto-Update sind aus. Dem Clone vertraut es ohne Rückfrage. |
| Skills | die Sammlungen aus `[[devcontainer.skills]]` in `harness.toml` als Plugins, siehe [Skills](#skills) |

`einstieg.sh` läuft beim Start als root. Er setzt die Firewall (`firewall.sh`), prüft sie und wechselt dann endgültig zu `agent`. Scheitert die Firewall oder ihr Selbsttest, endet der Container mit Fehler. `docker logs agent-<name>` zeigt warum.

Erst wenn Firewall und Clone stehen, entsteht `/run/harness/bereit`, und erst danach öffnet `just agent` Claude. Das Verzeichnis ist ein tmpfs (`docker run --tmpfs`). So überlebt das Zeichen keinen Neustart, und das Netz ist in den Sekunden bis zur neuen Firewall nicht offen.

## Netz

Standard ist DROP. Erlaubt sind:

- GitHub, und zwar die Bereiche aus `[netz] github_meta` (`web`, `api`, `git` aus `api.github.com/meta`);
- die Domains aus `[netz] domains` in `harness.toml`, nur auf Port 443;
- der Broker über `host.docker.internal` auf seinem Port;
- DNS zu den Nameservern des Containers.

Die **GitHub-Netze** holt `github-netze.sh` einmal beim Bauen des Images (in der CI mit dem Token des Workflows) und legt sie nach `/etc/harness/github-netze.txt`. Ein Start fragt die GitHub-API also nicht, denn anonym erlaubt GitHub nur 60 Abfragen je Stunde und IP. Ändert GitHub seine Netze, scheitert der Selbsttest mit „github.com ist nicht erreichbar“. Dann baut **Actions → devcontainer → Run workflow** (auf `main`) ein neues Image. Die **Domains** werden bei jedem Start per DNS aufgelöst. Die Allowlist wird beim Bauen aus dem `harness.toml` von `main` ins Image übernommen. Der Clone im Volume kann sie nicht ändern. **Neue Domains kommen per PR in `harness.toml`**, danach baut der Workflow ein neues Image.

Restrisiken:

- **DNS:** DNS-Anfragen gehen weiter hinaus. Das ist ein schmaler Kanal nach außen.
- **Geteilte CDN-IPs, ein breiter Kanal:** `registry.npmjs.org` (Cloudflare) sowie `pypi.org` und `files.pythonhosted.org` (Fastly) teilen ihre IPs mit beliebigen fremden Seiten. Ein reingelegter Agent kann über eine erlaubte IP (`curl --resolve …`) unbemerkt und in voller Bandbreite an eine eigene Seite senden, auch das `setup-token`. Die Firewall begrenzt also IPs, nicht Hostnamen. Abhilfe schafft ein Egress-Proxy mit Hostname-Allowlist (#70).
- **Wechselnde IPs:** Ändert ein Dienst während einer Session seine IPs, hilft ein Neustart des Containers (`docker stop agent-<name>`, dann `just agent …`).
- **Abmelden:** Nach dem Abmelden gibt der Broker kein neues Token mehr aus. Ein schon geholtes Token gilt aber bis zu 1 h weiter. Sofort wirkt nur der Kill-Switch im [Broker-README](../broker/README.md#kill-switch).

## Skills

Agenten im Container haben nur die Skill-Sammlungen aus `[[devcontainer.skills]]` in `harness.toml`, in fester Version ([ADR 0005](../docs/adr/0005-agenten-isolation.md), „Selbstschutz“). Dort stehen auch Version und Commit. Die Plugins des Owners auf dem Host kommen bewusst nicht hinein. Derzeit:

| Sammlung | Inhalt (Auswahl) |
|---|---|
| [`mattpocock-skills`](https://github.com/mattpocock/skills) (MIT) | `implement`, `tdd`, `code-review`, `to-spec`, `to-tickets`, `grilling`, `domain-modeling`, `wayfinder`, `wizard` |

`superpowers` fehlt mit Absicht: Es überschneidet sich mit diesen Skills und erzwingt per Hook einen eigenen Ablauf.

Beim Bauen holt `skills-holen.sh` jede Sammlung von GitHub nach `/opt/harness/skills/<plugin>` und prüft, ob der Tag (`version`) auf den Commit (`commit`) zeigt. Gibt es den Tag nicht oder zeigt er woanders hin, bricht der Bau mit Meldung ab. `skills-installieren.sh` installiert sie danach als User `agent` per `claude plugin install`. Claude lädt sie aus seiner Kopie unter `~/.claude/plugins/cache`. Die gehört `agent`: Ein Agent kann seine Skills also im eigenen Container ändern, aber nicht im Image. Jeder neue Container startet wieder mit dem Stand aus `main`. Im Container zeigt `claude plugin list` den Stand.

**Aktualisieren oder neue Sammlung:** per PR auf `harness.toml`. Den Commit zu einem Tag zeigt

```bash
git ls-remote https://github.com/<owner>/<repo>.git 'refs/tags/<tag>^{}'
```

(bei einem einfachen Tag ohne `^{}`). Eine Sammlung muss ein Claude-Code-Marketplace sein (`.claude-plugin/marketplace.json`). Nach dem Merge baut der Workflow ein neues Image. Laufende Container behalten ihren Stand, erst ein neuer Container (`just weg`, dann `just agent`) hat die neuen Skills.

## Image

Das Image baut nur der Workflow [`devcontainer`](../.github/workflows/devcontainer.yml): bei jedem PR zum Testen, aus `main` nach `ghcr.io/<repository klein>/devcontainer` (`latest` und Commit-SHA). Agenten bauen nie Images. Lokal gebaute Images dienen nur den Tests.

## Entwicklung

```bash
uv run python -m pytest -m "not container"   # ohne Docker
uv run python -m pytest -m container         # baut harness-devcontainer:test und prüft die Negativproben
uv run python -m ruff check . && uv run python -m ruff format --check .
uv run python -m pyright
```

Unter Windows mit Smart App Control braucht `uv` ein signiertes Python: `uv venv --python "C:\Program Files\Python313\python.exe"`. Die Container-Tests brauchen Docker Desktop. Mit `HARNESS_TEST_IMAGE` laufen sie gegen ein fertiges Image.
