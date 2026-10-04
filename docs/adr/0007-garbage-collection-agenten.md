# Garbage-Collection-Agenten

Status: akzeptiert
Präzisiert: ADR 0005

Garbage-Collection-Agenten laufen periodisch in **GitHub Actions** und tragen Drift ab, die kein Gate erkennt. Jeder Lauf besteht aus **zwei Jobs**. Der Agent liest das Repo ohne Schreibrechte und liefert nur einen Patch und einen Bericht. Ein deterministischer Job ohne LLM öffnet daraus den PR oder das Issue, mit einem kurzlebigen Token der GitHub App aus einem **zweiten Private Key**. Dieser Key liegt in einem Actions-Environment, nicht beim Broker. Damit präzisiert dieses ADR die Regel aus ADR 0005, dass der Broker den Key hält: Er hält ihn für alle Agenten-Sessions. Die Leitregel gilt in Actions sogar strenger, denn der Agent bekommt dort gar kein App-Token. Wir haben uns so entschieden, weil der Heimrechner nur bei Bedarf läuft und ein Zeitplan im Devcontainer still ausfiele. Actions-Minuten kosten in einem public Repo nichts, und ein PR mit `GITHUB_TOKEN` löst keine CI aus (Issue #11).

## Regeln

### Ablauf

- **Job 1 (Agent):** `permissions: contents: read`, Checkout mit `persist-credentials: false`, Claude Code über `CLAUDE_CODE_OAUTH_TOKEN`. Bash ist auf eine Allowlist begrenzt (`just check`, die Scan-Werkzeuge, `git diff`). Egress ist per harden-runner im Block-Modus gesperrt, erlaubt sind die Domains der Netz-Allowlist des Devcontainers. Ergebnis ist ein Artefakt aus Patch und Bericht mit Befunden.
- **Job 2 (deterministisch):** läuft im Environment `gc`, das nur von `main` aus nutzbar ist und den zweiten Private Key hält. Er holt per `actions/create-github-app-token` ein Token mit den Rechten der Rolle *Bau* und öffnet daraus den PR auf einem Branch `gc/<agent>/…` mit Label `gc` oder legt Issues an. Einen Patch, der `.github/` berührt, lehnt er ab. Der Key lässt sich unabhängig vom Broker-Key widerrufen.
- **Ausgabe:** Ein mechanischer, eindeutiger Fix kommt als PR. Alles, was eine Entscheidung braucht (etwa Code, der einem ADR widerspricht), wird ein Issue mit Label `drift`. Jedes Issue trägt einen Fingerabdruck des Befunds. Findet ein Lauf einen bekannten Befund wieder, kommentiert er das bestehende Issue, statt ein neues zu öffnen. `drift`-Issues sortiert der Owner. Agenten greifen sie nicht von sich aus auf.
- GC-PRs folgen allen Regeln aus ADR 0006. Peripherie mergt automatisch, Kern wartet auf den Owner, die Limits für Runden und Größe gelten.

### Katalog

| Agent | Scannt | Takt |
|---|---|---|
| Doku-Drift | `AGENTS.md`, `docs/agents/` und `CONTEXT.md` gegen den Code, Begriffe im Code gegen das Glossar. Meldet außerdem Constraint-Zeilen ohne `[check: …]`, für die ein deterministischer Check machbar wäre. | wöchentlich |
| Aufräumen | Duplikation, Komplexitäts-Hotspots, toter Code. Die Erkennung ist deterministisch, das LLM baut nur den Fix. | wöchentlich |
| Qualitätsnoten | pflegt `docs/qualitaet.md` | wöchentlich, nach dem Aufräumen |
| ADR-Abgleich | Code gegen alle nicht ersetzten ADRs | monatlich |
| Modellwechsel-Revision | `AGENTS.md`, der Prompt von `ai-review` und die GC-Prompts: Workarounds für alte Modelle, tote Verweise, Widersprüche | beim Merge einer Änderung an der Modell-ID, sonst per Hand |

- Verstöße gegen Architekturregeln sind keine GC-Aufgabe, sie sind Gates (ADR 0001, ADR 0004, ADR 0006).
- Die Modell-ID für `ai-review` und alle GC-Agenten steht in genau einer Kern-Datei. Ein Modellwechsel ist damit immer ein sichtbarer Kern-PR und startet die Revision.
- Die Läufe liegen auf verschiedenen Nächten.

### Budget

- Ein Lauf entfällt, wenn sich seit dem letzten erfolgreichen Lauf auf `main` nichts in seinem Scan-Bereich geändert hat.
- Je Agent gibt es höchstens einen offenen PR. Ist er noch offen, liefert der Agent nur Issues.
- Je Lauf entstehen höchstens drei neue `drift`-Issues.
- Turns (`--max-turns`) und Laufzeit (`timeout-minutes`) sind hart begrenzt. Die Zahlen stehen in einer Kern-Konfiguration.

### Ausfälle

- Jeder fehlgeschlagene oder übersprungene Lauf aktualisiert ein einziges Issue „GC-Ausfall“ (Label `gc`) mit Datum und Ursache. Ein erfolgreicher Lauf schließt es. So fällt ein abgelaufenes `setup-token` oder ein erschöpftes Kontingent auf.
- GitHub schaltet geplante Workflows nach 60 Tagen ohne Aktivität im Repo ab. Das steht als Hinweis in `docs/agents/`, einen Keepalive gibt es nicht.

## Restrisiken

- Der Inhalt von `main` ist nur halb vertrauenswürdig, weil Peripherie automatisch mergt. Eine Prompt-Injection im Code kann den Agenten in Job 1 steuern. Seine Bash sieht das `CLAUDE_CODE_OAUTH_TOKEN`. Ausleiten kann er es nur über erlaubte Domains, etwa über GitHub selbst. Das entspricht dem Restrisiko des Devcontainers (ADR 0005). Das Token lässt sich einzeln widerrufen.
- Wer Workflows ändern kann, kommt an den zweiten Key. `.github/` ist Kern, die App hat kein Workflows-Recht, und das Environment ist an `main` gebunden.

## Verworfene Alternativen

- **Devcontainer auf dem Heimrechner per Aufgabenplanung:** Das passt ohne Präzisierung zu ADR 0005, läuft aber nur, wenn der Rechner zufällig an ist. Ausfälle wären die Regel.
- **Agent und PR in einem Job:** Der Agent sähe das App-Token und könnte es per Prompt-Injection ausleiten. Mit dem getrennten Job sieht er es nie.
- **Zweite GitHub App nur für GC:** Sie brächte eine eigene Bot-Identität und einen eigenen Kill-Switch, aber doppelten Einrichtungsaufwand. Branch-Präfix und Label unterscheiden GC-PRs genauso, und der zweite Key lässt sich einzeln widerrufen.
- **Agent ohne Bash wie `ai-review`:** Der Aufräum-Agent könnte seinen Fix nicht prüfen, und PRs, die schon an `just check` scheitern, verbrauchten die beiden CI-Runden.
- **Immer PR:** Befunde, die eine Entscheidung brauchen, kämen als PR, der eigentlich eine Frage ist. **Rollierendes Bericht-Issue je Agent:** Einzelne Befunde gingen darin unter.
- **Eigener periodischer Prompt-Audit:** Ohne Modellwechsel ändern sich die Prompts nur per Kern-PR, den der Owner ohnehin sieht. Der Audit ist Teil der Modellwechsel-Revision.
- **Architekturregeln als GC-Scan:** Sie sind bereits Gates, ein Agent fände dort nie etwas.
