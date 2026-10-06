# Agenten-Isolation

Status: akzeptiert

Jede Agenten-Session zu diesem Repo läuft in einem **Devcontainer unter Docker Desktop**, auch Planungs-Sessions. Ihr GitHub-Zugang ist ein **Rollen-Token der eigenen GitHub App**, das ein **Broker** auf dem Host bei Bedarf ausstellt. Den Private Key der App und den Login des Owners sieht kein Agent. Leitregel: **Mehr als ein Rollen-Token der App bekommt ein Agent auf diesem Rechner nirgends.** Wir haben uns so entschieden, weil alle Server-Gates (CODEOWNERS, Ruleset) wertlos sind, sobald ein Agent den Login des Owners lesen kann: Ein PR, den der Owner öffnet, braucht kein Approval (Smoke-Test, Issue #11). Das Repo ist public, also rechnen wir neben Versehen auch mit Prompt-Injection samt Exfiltration.

## Regeln

- **Grenze:** Container aus `.devcontainer/`, User ohne sudo, kein Docker-Socket, keine Weiterleitung von Credential-Helper, `.gitconfig` oder SSH-Agent des Hosts. Der Agent baut keine Images, das macht die CI.
- **Clone:** Jeder Container hat einen eigenen Clone in einem eigenen Volume. Ein `.git` mit dem Host teilt er nicht, sonst könnte er Hooks oder `core.fsmonitor` setzen, die beim nächsten Commit des Owners auf dem Host laufen.
- **Arbeitsstränge:** ein Container pro Strang (Ticket oder Session), alle aus demselben Image, mit genau einer Rolle. Start per `just agent <rolle> <name>`, nach dem Merge wird der Container samt Volume weggeworfen.
- **Rollen:** *Planung* bekommt Issues RW und Contents R, *Bau* bekommt Contents RW, Pull requests RW und Issues R. Die App selbst hat nie Workflows- oder Administration-Rechte und steht auf keiner Bypass-Liste. Commits laufen unter `<app-slug>[bot]` mit dessen noreply-Adresse, signiert wird nicht.
- **Broker:** ein kleiner Dienst auf dem Windows-Host unter einem eigenen Dienstkonto, erreichbar über `host.docker.internal`. Er hält den Private Key (DPAPI des Dienstkontos, das Original offline) und stellt bei Anfrage ein Installation-Token aus: 1 h gültig, nur für dieses Repo, mit den Rechten der Rolle. Ein Git-Credential-Helper und ein `gh`-Wrapper im Container fragen ihn an.
- **Rollenbindung:** Das Startskript erzeugt je Container einen Zufallsschlüssel und meldet „Schlüssel → Rolle, Ablauf“ beim Broker an. Der Broker stellt nur Tokens der angemeldeten Rolle aus. Beim Wegwerfen des Containers meldet das Skript den Schlüssel ab.
- **Netz:** Default DROP per iptables, erlaubt sind nur die Domains einer versionierten Allowlist (Anthropic-API, GitHub, Paketquellen, Broker). Neue Domains kommen per PR.
- **Claude-Zugang:** `claude setup-token` per Env-Variable. Es kann weniger als ein voller Login und lässt sich einzeln widerrufen. Remote Control braucht einen vollen Login und entfällt deshalb.
- **Berechtigungsmodus:** `bypassPermissions` ist im Container erlaubt, außerhalb nie. Deny-Regeln und der `PreToolUse`-Guard für Tests und Harness gelten weiter, als Leitplanke.
- **Bedienung:** die CLI per `docker exec`, gestartet mit `just agent <rolle> <name>` aus PowerShell. Eine SSH-Umgebung der Desktop-App entfällt: Sie reicht die Claude-Anmeldung und die Connectors des Hosts in den Container (Spike #26).
- **Selbstschutz:** Image, Allowlist und Broker werden immer aus `origin/main` gebaut, nie aus dem Arbeitsstand eines Agenten. Diese Pfade sind Kern, eine Sandbox kann sich also nicht selbst lockern.
- **Host:** Auf dem Host liegen keine GitHub-Credentials, weder ein `gh`-Login noch Einträge des Git Credential Managers. Der Owner reviewt, approvt, merged und ändert Einstellungen im Browser. Sein lokaler Clone holt anonym und ist nur zum Lesen da. Local-Sessions für andere Projekte bleiben erlaubt, weil dort nichts mehr zu holen ist.
- **Eigene Änderungen des Owners:** github.dev im Browser, Commit und PR laufen unter dem Owner. Lokal pusht der Owner nicht. Codespaces nur ohne Agenten darin, denn dort arbeitet jeder Agent mit dem Token des Owners.
- **Kill-Switch:** Broker stoppen, App-Installation sperren, `setup-token` widerrufen.

## Restrisiken

- Wer aus dem Container ausbricht, landet in der VM von Docker Desktop, und die sieht `C:` mit den Rechten des Owners. Dafür braucht es einen Kernel-Exploit, das liegt über dem Bedrohungsmodell.
- Über GitHub selbst (Issue-Kommentar, Push) kann ein Agent weiterhin etwas nach außen schreiben. Deshalb gibt es im Container keine Geheimnisse außer dem Rollen-Token und dem `setup-token`.
- Ein Local-Agent auf dem Host kann per `docker exec` an einen Container-Schlüssel kommen. Er bekommt damit höchstens ein Rollen-Token, die Leitregel hält.
- Die Browser-Sitzung des Owners bei GitHub ist nicht geschützt, falls ein Agent einen Browser fernsteuert.

## Verworfene Alternativen

- **Cloud-Sessions (claude.ai/code):** Sie pushen und öffnen PRs mit dem OAuth-Token des Owners, eine eigene App ist dort nicht vorgesehen. Das Kern-Gate entfiele.
- **Eigene WSL2-Distro:** Microsoft führt WSL nicht als Sicherheitsgrenze. Bash in WSL hat die Rechte des Windows-Users, Interop und Automount sind Default, und root in der Distro kann sie wieder einschalten.
- **Separater Windows-User:** eine echte Grenze, aber ohne Bash-Sandbox und ohne einfache Netz-Allowlist, mit einer Windows-Toolchain statt der Linux-Toolchain der CI.
- **Docker Sandboxes (`sbx`):** microVM, das Token verlässt den Host nie. Neu, braucht einen Docker-Login und lässt sich nicht aus der Desktop-App steuern. Ein späterer Wechsel bleibt billig, weil Broker und Allowlist gleich bleiben.
- **Token einmal pro Session:** Lange Sessions brächen nach 1 h ab. Eine regelmäßig erneuerte Token-Datei hängt an einem Timer, der still ausfallen kann.
- **Key per DPAPI unter dem Owner-User:** DPAPI schützt nur gegen andere User. Jeder Local-Agent des Owners könnte ihn entschlüsseln.
- **Docker-in-Docker:** braucht `--privileged`. Docker-Zugriff ist root-äquivalent und hebt die Grenze auf.
- **SSH-Schlüssel `ed25519-sk` auf einem FIDO2-Key für lokale Pushes des Owners:** Jeder Push bräuchte eine Berührung, ein Agent könnte ihn also nicht allein abschließen. Der Owner hält Kauf und Einrichtung eines Keys für unverhältnismäßig, github.dev reicht (#31). Windows Hello ersetzt den Key nicht: Unter Windows 25H2 verlangt OpenSSH für Windows trotz Windows Hello einen externen Key (Win32-OpenSSH, Issues 2408 und 2413).
- **Signierte Commits:** Die Signatur käme aus derselben Sandbox wie der Push und bewiese nichts zusätzlich.
