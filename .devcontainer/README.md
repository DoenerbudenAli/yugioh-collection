# Agenten-Container

Jede Agenten-Session für Feature- und Planungs-Arbeit läuft in einem eigenen Container aus diesem Ordner ([ADR 0005](../docs/adr/0005-agenten-isolation.md)). Harness-Arbeit läuft auf dem Host ([ADR 0011](../docs/adr/0011-harness-arbeit-auf-dem-host.md)). Der Container kennt nur zwei Geheimnisse: einen Schlüssel, mit dem er beim [Broker](../broker/README.md) ein 1-h-Rollen-Token holt, und das `setup-token` für Claude. Ins Netz darf er nur über die Allowlist.

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

`einstieg.sh` läuft beim Start als root. Er startet den Egress-Proxy als User `egress`, setzt die Firewall (`firewall.sh`), prüft sie und wechselt dann endgültig zu `agent`. Scheitern Proxy, Firewall oder ihr Selbsttest, endet der Container mit Fehler. `docker logs agent-<name>` zeigt warum.

Erst wenn Firewall und Clone stehen, entsteht `/run/harness/bereit`, und erst danach öffnet `just agent` Claude. Das Verzeichnis ist ein tmpfs (`docker run --tmpfs`). So überlebt das Zeichen keinen Neustart, und das Netz ist in den Sekunden bis zur neuen Firewall nicht offen.

## Netz

Standard ist DROP. Nach außen dürfen nur:

- der **Egress-Proxy** (`devcontainer.proxy`, User `egress`) auf Port 443;
- der Broker über `host.docker.internal` auf seinem Port;
- DNS zu den Nameservern des Containers.

```
agent (git, gh, uv, pnpm, npm, curl, Claude)
   │  HTTPS_PROXY=http://127.0.0.1:3128
   ▼
Egress-Proxy (User egress) ── nur Hostnamen aus [netz] domains ──► Internet, Port 443
   ✗ agent direkt nach außen: verworfen (iptables, owner match)
```

Der Proxy lässt nur `CONNECT <name>:443` zu, wenn `<name>` in `[netz] domains` in `harness.toml` steht. Außerdem liest er den TLS-ClientHello im Tunnel und kappt ihn, wenn dort ein anderer Name (SNI) steht, gar keiner oder ein verschlüsselter (ECH). So kommt ein Agent nicht über eine IP, die sich ein CDN mit fremden Seiten teilt, zu einer eigenen Seite. Der Proxy löst die Namen selbst auf, `curl --resolve` oder `--connect-to` helfen also nicht. Er schreibt jede Entscheidung nach `docker logs agent-<name>` (`proxy: erlaubt: …`, `proxy: abgewiesen: …`, `proxy: gekappt: …`).

Auch **GitHub** läuft über den Proxy (`github.com` für git, `api.github.com` für gh). Die Werkzeuge finden ihn über `HTTPS_PROXY`/`HTTP_PROXY` aus dem Image, ohne Einstellungen pro Werkzeug. Der Broker ist per `NO_PROXY` ausgenommen.

Die Allowlist wird beim Bauen aus dem `harness.toml` von `main` ins Image übernommen. Der Clone im Volume kann sie nicht ändern. **Neue Hostnamen kommen per PR in `harness.toml`**, danach baut der Workflow ein neues Image. Ein Werkzeug, das einen anderen Hostnamen braucht (etwa `codeload.github.com` für Tarballs), scheitert bis dahin mit `403` vom Proxy.

Beim Start prüft `firewall.sh`, dass jeder Hostname auflösbar ist, dass `example.com` gesperrt ist, dass `github.com` am Proxy vorbei gesperrt ist und dass `github.com` über den Proxy erreichbar ist. Scheitert etwas davon, startet der Container nicht.

Restrisiken:

- **DNS:** DNS-Anfragen gehen weiter hinaus. Das ist ein schmaler Kanal nach außen.
- **Domain Fronting:** Im verschlüsselten Teil einer erlaubten Verbindung könnte ein Agent im HTTP-Kopf `Host:` eine fremde Seite beim selben CDN nennen. Der Proxy sieht das nicht. Cloudflare (npm) und Fastly (PyPI) sollen solche Anfragen abweisen, geprüft ist das hier nicht. Bis zu #70 stand dieser Weg ohne jede Hürde offen (`curl --resolve`), jetzt hängt er davon ab, ob ein CDN fremde `Host`-Köpfe annimmt.
- **GitHub:** Über GitHub selbst kann ein Agent weiter etwas nach außen schreiben (ADR 0005, Restrisiken).
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
