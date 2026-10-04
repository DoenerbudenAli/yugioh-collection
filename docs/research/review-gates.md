# Review-Gates für ein Solo-Repo auf GitHub Free

Research-Ticket #4 · Stand: 2026-10-04 · Repo: `DoenerbudenAli/yugioh-collection` (public, persönlicher Account, GitHub Free)

Frage: Wie lässt sich risikogestaffeltes Review mit **genau einem Menschen** auf einem public Repo mit GitHub Free umsetzen?

---

## Kurzfazit

**Es geht ohne Organisation und ohne Bezahlplan, aber nur mit einem Trick: Das Pfad-Gate macht allein CODEOWNERS, nicht die Approval-Zahl.** GitHub Free bietet auf public Repos Rulesets, CODEOWNERS und Auto-Merge. Merge Queue und pfadbezogene „Required reviewers“ gibt es dagegen nur für Organisationen. Weil der PR-Autor nie selbst approven darf, braucht jeder Agent eine **eigene Bot-Identität**. Am besten ist dafür eine eigene GitHub App.

### Empfohlenes Setup

1. **Ruleset auf `main`** (kein klassischer Branch-Schutz):
   - Pull Request ist Pflicht, mit `required_approving_review_count: 0`.
   - `require_code_owner_review: true` und `dismiss_stale_reviews_on_push: true`.
   - Required status checks: `ci`, `ai-review` und optional `harness-guard`.
   - Force-Push und Löschen blockieren; nur Squash-Merge erlauben.
   - Bypass: nur die Rolle *Repository admin* im Modus „For pull requests only“. Die Agent-App steht **nicht** auf der Bypass-Liste.
2. **`.github/CODEOWNERS` ohne Default-Owner (`*`).** Einträge bekommen nur Kern, Schnittstellen, **alle Testverzeichnisse** und die Harness-Konfiguration (`/.github/`, `/.claude/`, `AGENTS.md`, `CLAUDE.md`, CODEOWNERS selbst). Jeder dieser Pfade gehört `@DoenerbudenAli`.
   - Folge: Ein PR, der eine dieser Dateien ändert, braucht die Freigabe des Owners.
   - Ein reiner Peripherie-PR braucht 0 Approvals und nur grüne Checks.
3. **Agent-Identität: eigene GitHub App.** Sie gehört dem persönlichen Account und ist nur auf diesem Repo installiert.
   - Rechte: Contents RW, Pull requests RW, optional Issues RW. **Keine** Rechte für Workflows und Administration.
   - Der lokale Claude Code holt sich ein Installation-Token, das 1 h gilt. Damit pusht er (`x-access-token`) und öffnet PRs (`GH_TOKEN=… gh pr create`).
   - PR-Autor ist dann `<app>[bot]`, also kann der Owner approven.
4. **Auto-Merge im Repo einschalten** (`allow_auto_merge` steht aktuell auf `false`). Der Agent setzt bei jedem PR `gh pr merge --auto --squash`.
   - Peripherie-PRs mergen, sobald die Checks grün sind.
   - Kern-PRs warten auf das Code-Owner-Approval und mergen danach von selbst.
   - Eine eigene Label-Logik ist nicht nötig.
5. **Schutz der Tests in drei Schichten:**
   - CODEOWNERS (harte Grenze auf dem Server).
   - Claude-Code-`permissions.deny` (`Edit(/tests/**)` usw.) plus ein `PreToolUse`-Hook, der Schreibzugriffe per Bash abfängt. Copilot kann dasselbe Hook-Skript über `.github/hooks/*.json` mitnutzen.
   - Lokal gilt das nur als Leitplanke, nicht als Sicherheitsgrenze.
6. **Actions:**
   - Standardrechte von `GITHUB_TOKEN` bleiben `read` (aktuell schon so). „Allow GitHub Actions to create and approve pull requests“ bleibt aus (aktuell aus).
   - Kein `pull_request_target` mit Checkout des PR-Heads.
   - Das KI-Review läuft über `anthropics/claude-code-action` mit `CLAUDE_CODE_OAUTH_TOKEN` aus dem Pro/Max-Abo. Es ist ein **Status-Check, kein Approval**.
   - Test-/CI-Jobs bekommen keine Secrets.

**Wichtigster Vorbehalt:** Läuft der lokale Agent unter demselben Windows-User wie der Owner, kann er grundsätzlich an dessen `gh`-Login und an den App-Private-Key herankommen. Damit wären alle Server-Gates umgehbar (Admin-Bypass). Echte Trennung entsteht erst, wenn der Agent in WSL2/Devcontainer läuft und nur das kurzlebige App-Token sieht (siehe Offene Punkte).

---

## Befunde

### 1. Was GitHub Free auf einem public Repo eines persönlichen Accounts kann

| Funktion | Verfügbar? | Beleg |
|---|---|---|
| Rulesets (Branch/Tag) | **Ja.** „available in public repositories with GitHub Free“ | [About rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets) (Kasten „Who can use this feature?“) |
| Klassische Protected Branches | **Ja**, auf public Repos mit GitHub Free | [About protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches) |
| CODEOWNERS | **Ja**, auf public Repos mit GitHub Free | [About code owners](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners) |
| Auto-Merge | **Ja**, auf public Repos mit GitHub Free | [Automatically merging a pull request](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/automatically-merging-a-pull-request) |
| Required approvals, Code-Owner-Review, Stale-Dismissal, Last-Push-Approval, Thread-Resolution, Merge-Methode | **Ja** (Teil der Regel „Require a pull request before merging“) | [Available rules for rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets#require-a-pull-request-before-merging) |
| Required status checks (strict/loose, optional mit festgelegter App als Quelle) | **Ja** | ebd., Abschnitt „Require status checks to pass before merging“ |
| Signed commits | **Ja** (Ruleset-Regel bzw. Branch-Protection) | ebd. und [About protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches#require-signed-commits) |
| **Required reviewers je Dateipfad** (Teams) | **Nein.** „This rule is not available on user-owned repositories as they do not contain teams.“ | [Available rules for rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets#required-reviewers) |
| **Merge Queue** | **Nein.** Nur „in any public repository owned by an organization“ | [Managing a merge queue](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue) |
| **Push-Rulesets** (z. B. „Restrict file paths“) | **Nein** für public Repos. Push-Rulesets blockieren Pushes „to a private or internal repository“ | [About rulesets → Push rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets#push-rulesets) |
| Bypass-Liste im **klassischen** Branch-Schutz | **Nein.** „Actors may only be added to bypass lists when the repository belongs to an organization.“ | [About protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches) |
| Bypass-Liste in **Rulesets** | **Ja.** Erlaubt sind Repository-Admins, Rollen maintain/write, Teams, GitHub Apps und Dependabot. Mit Modus `pull_request` („For pull requests only“) ist kein Direkt-Push möglich, aber ein Merge mit Bypass. `OrganizationAdmin` gilt nicht für persönliche Repos. | [Creating rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository#granting-bypass-permissions-for-your-branch-or-tag-ruleset), [REST: Rules (`bypass_mode`)](https://docs.github.com/en/rest/repos/rules) |

**Rulesets oder klassischer Branch-Schutz?** Rulesets sind hier klar besser:
- Mehrere Rulesets können sich überlagern.
- Es gibt den Status „Evaluate“/„Disabled“, ohne dass man ein Ruleset löschen muss.
- Jeder mit Lesezugriff sieht die Regeln. Das ist gut für die Transparenz gegenüber Agenten.
- Vor allem gibt es auf persönlichen Repos nur bei Rulesets eine Bypass-Liste.
- Quelle: [About rulesets → About rulesets and protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets#about-rulesets-and-protected-branches).

**Ist-Zustand des Repos** (lesend per `gh api` geprüft am 2026-10-04):
- `owner.type = User`, `visibility = public`.
- Keine Rulesets, `main` ist ungeschützt.
- `allow_auto_merge = false`.
- Secret Scanning und Push Protection sind an.
- Für Actions: `default_workflow_permissions = read`, `can_approve_pull_request_reviews = false`.

### 2. Kern-Constraint: Der Autor kann nicht approven

- „Pull request authors cannot approve their own pull requests.“ Außerdem kann man einen von Copilot erstellten PR nicht approven, wenn man Copilot selbst auf das Issue gesetzt hat. Quelle: [Reviewing proposed changes in a pull request](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/reviewing-changes-in-pull-requests/reviewing-proposed-changes-in-a-pull-request).
- Der Repo-Owner kann auf einem persönlichen Repo trotzdem „Merge a pull request on a protected branch, even if there are no approving reviews“. Quelle: [Permission levels for a personal account repository](https://docs.github.com/en/account-and-profile/reference/permission-levels-for-a-personal-account-repository).
  - Bei Rulesets gilt das nur, wenn die Admin-Rolle auf der Bypass-Liste steht.
  - Ein solcher Merge ist ein *Bypass*, kein Approval. Er erscheint im Audit, zählt aber nicht als Review.

**Konsequenz:** Öffnet der lokale Claude Code PRs mit dem `gh`-Login des Owners, ist der Owner der Autor. Dann ist kein Approval möglich, und das Gate besteht nur noch aus Bypass-Klicks. Deshalb braucht der Agent eine eigene Identität.

### 3. Bot-Identitäten im Vergleich

| Option | Identität im PR | Rechte/Token | Kosten | Bewertung |
|---|---|---|---|---|
| **Eigene GitHub App** | `<app-slug>[bot]` | Feingranulare Rechte. Das Installation-Token läuft nach **1 h** ab und lässt sich beim Ausstellen auf einzelne Repos und weniger Rechte einschränken ([Generating an installation access token](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app)). Für Dateien unter `.github/workflows` braucht die App die eigene Berechtigung „Workflows“ ([Choosing permissions](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/choosing-permissions-for-a-github-app)). Lässt man sie weg, kann der Agent keine Workflows ändern. | kostenlos | **Empfohlen** für lokale und CI-Agenten |
| **Offizielle Claude-App** (`claude[bot]`, via `/install-github-app`) | `claude[bot]` | Fordert Contents, Pull requests und Issues RW an. Außerdem schon „für künftige Features“ Discussions RW, Actions R, Checks R und **Workflows RW** ([claude-code-action docs/security.md](https://github.com/anthropics/claude-code-action/blob/main/docs/security.md#github-app-permissions)). Die FAQ sagt dagegen, die App habe „doesn't have workflow write access“ ([faq.md](https://github.com/anthropics/claude-code-action/blob/main/docs/faq.md)). Das widerspricht sich. | App kostenlos; Modell über Abo oder API | Für minimale Rechte lieber eine **eigene App** an die Action übergeben ([setup.md → Using a Custom GitHub App](https://github.com/anthropics/claude-code-action/blob/main/docs/setup.md)) |
| **Copilot cloud agent** (früher „Coding Agent“) | Copilot. Der Auftraggeber zählt als beteiligt und darf **nicht approven**. | Pusht nur auf einen `copilot/…`-Branch, erstellt Draft-PRs, kann nicht approven oder mergen. Workflows laufen standardmäßig erst nach „Approve and run workflows“. ([Risks and mitigations](https://docs.github.com/en/copilot/concepts/agents/cloud-agent/risks-and-mitigations)) | „available for all paid Copilot plans“, also **nicht mit Copilot Free** ([About cloud agent](https://docs.github.com/en/copilot/concepts/agents/cloud-agent/about-cloud-agent)) | Später möglich. Mit genau einem Menschen sind Kern-PRs von Copilot **nur per Admin-Bypass** mergebar (siehe 4.3). |
| **Machine-User** | eigener Account | Laut ToS erlaubt: „You may maintain no more than one free machine account in addition to your free Personal Account“. Der Account muss von einem Menschen angelegt sein, der verantwortlich bleibt ([GitHub Terms of Service → Account Terms](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service)). Braucht ein PAT, das lange lebt und nicht automatisch rotiert. Als Collaborator hat er auf persönlichen Repos immer Schreibrecht ([Permission levels](https://docs.github.com/en/account-and-profile/reference/permission-levels-for-a-personal-account-repository)). | kostenlos | Funktioniert, ist aber schlechter als eine App: statisches Token, kein Rechte-Zuschnitt, eigener Login samt 2FA |

#### 3.1 Lokaler Claude Code öffnet PRs als App

Ablauf laut GitHub-Doku:

1. **JWT erzeugen.** Es wird mit dem Private Key signiert, `iss` ist die Client-ID, `exp` höchstens 10 min ([Generating a JWT](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-json-web-token-jwt-for-a-github-app)).
2. **Installation-Token holen** per `POST /app/installations/{id}/access_tokens`. Dabei optional `repositories: ["yugioh-collection"]` und eine reduzierte `permissions`-Menge angeben. Das Token gilt 1 h.
3. **Git-Push** mit dem Token als HTTP-Passwort: `https://x-access-token:TOKEN@github.com/owner/repo.git` ([Authenticating as an installation](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/authenticating-as-a-github-app-installation)).
4. **`gh`** mit `GH_TOKEN=<token>`. GH_TOKEN „takes precedence over previously stored credentials“ ([gh help environment](https://cli.github.com/manual/gh_help_environment)). Danach `gh pr create` und `gh pr merge --auto --squash`.
5. **Commits bekommen das Bot-Label „Verified“ nur**, wenn sie über die API ohne eigene Autor- oder Committer-Angaben entstehen ([About commit signature verification → bots](https://docs.github.com/en/authentication/managing-commit-signature-verification/about-commit-signature-verification#signature-verification-for-bots)). Lokale `git commit` per CLI bleiben unsigniert. Das ist relevant, falls man „Require signed commits“ einschaltet (siehe Offene Punkte).

**Private Key:** Laut GitHub ist er „the single most valuable secret for a GitHub App“. Empfohlen ist ein Key-Vault, eine Umgebungsvariable ist schwächer ([Managing private keys](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/managing-private-keys-for-github-apps#storing-private-keys)).
- Der Agent selbst sollte den Key nie sehen. Ein Wrapper außerhalb der Agent-Umgebung erzeugt das Token und reicht nur das Token weiter.

#### 3.2 `anthropics/claude-code-action` – Identität, Rechte, Kosten

- **Auth:** entweder `ANTHROPIC_API_KEY` (API-Abrechnung pro Token) oder `CLAUDE_CODE_OAUTH_TOKEN` aus `claude setup-token`. Letzteres geht mit Pro, Max, Team und Enterprise.
  - „If you authenticate with an OAuth token, runs use your Claude subscription instead of API billing.“
  - Das OAuth-Token hängt am Abo der Person, die es erzeugt hat.
  - Quelle: [code.claude.com/docs/en/github-actions](https://code.claude.com/docs/en/github-actions).
  - Anthropic sieht OAuth für „ordinary use of Claude Code“ durch Abo-Inhaber vor. Für eigene Repos des Abo-Inhabers ist das gedeckt, ein Weiterreichen an Dritte nicht ([Legal and compliance](https://code.claude.com/docs/en/legal-and-compliance)).
- **Actions-Minuten:** Auf public Repos mit Standard-Runnern sind sie kostenlos ([Billing for GitHub Actions](https://docs.github.com/en/billing/concepts/product-billing/github-actions)).
- **Verhalten:**
  - Claude **kann keine PRs approven** ([capabilities-and-limitations.md](https://github.com/anthropics/claude-code-action/blob/main/docs/capabilities-and-limitations.md)).
  - Standardmäßig erstellt Claude **keine PRs**. Es pusht auf einen Branch und verlinkt eine vorausgefüllte PR-Seite ([security.md](https://github.com/anthropics/claude-code-action/blob/main/docs/security.md#pull-request-creation)).
  - Achtung: Klickt der Owner diesen Link, ist **er** der PR-Autor und kann nicht approven. Für Agenten-PRs muss der PR also per App-Token entstehen, z. B. im Automation-Modus mit erlaubtem `gh pr create`.
  - Auslösen dürfen nur Nutzer mit Schreibrecht. Bots sind standardmäßig ausgeschlossen.
  - Bei PRs stellt die Action `.claude/`, `CLAUDE.md`, `.mcp.json` u. a. aus dem **Base-Branch** wieder her. Ein PR kann also die Claude-Konfiguration nicht unterwandern (ebd.).
- **Rolle im Setup:** KI-Review als **Required Status Check** (Job schlägt bei blockierenden Befunden fehl), nicht als Approval. Damit bleibt „Approval“ immer eine menschliche Entscheidung (siehe OWASP ASI09).

### 4. Mechanismus: Peripherie automatisch, Kern mit Owner-Review

#### 4.1 Warum CODEOWNERS und nicht die Approval-Zahl

- `required_approving_review_count` gilt **global** für alle PRs auf `main`. Pfadabhängige Approvals über `required_reviewers` gibt es auf persönlichen Repos nicht (Befund 1).
- CODEOWNERS ist damit der **einzige pfadabhängige Hebel**:
  - „any pull request that modifies content with a code owner must be approved by that code owner“.
  - Dateien ohne Owner lassen sich mit dem Approval jedes Schreibberechtigten ändern ([Available rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets#require-a-pull-request-before-merging), [About code owners](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners)).
- In der REST-API sind `required_approving_review_count` und `require_code_owner_review` getrennte Pflichtparameter.
  - Ruleset: „Require an approving review in pull requests that modify files that have a designated code owner“.
  - Klassischer Schutz: Wert 0 heißt „0 to not require reviewers“.
  - Quellen: [REST: Rules](https://docs.github.com/en/rest/repos/rules), [REST: Branch protection](https://docs.github.com/en/rest/branches/branch-protection).
  - **Also: 0 Approvals global + Code-Owner-Pflicht = Approval nur für Pfade mit Owner.** Das ist aus der Doku abgeleitet und noch per Smoke-Test zu bestätigen (Offene Punkte, Nr. 1).
- **CODEOWNERS schützen:**
  - Maßgeblich ist immer die Version auf dem **Base-Branch** des PRs.
  - Ungültige Zeilen werden **still übersprungen**. Fehler liefert `GET /repos/{owner}/{repo}/codeowners/errors`. Das eignet sich als CI-Lint.
  - GitHub empfiehlt ausdrücklich, CODEOWNERS bzw. `/.github/` selbst einem Owner zuzuweisen.
  - Code Owner brauchen explizites Schreibrecht. Beim Repo-Owner ist das gegeben.
  - Quellen: [About code owners](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners), [REST: List CODEOWNERS errors](https://docs.github.com/en/rest/repos/repos#list-codeowners-errors).
- **Syntax:** Keine `!`-Negation und keine Zeichenbereiche. Die letzte passende Zeile gewinnt (ebd.).

Skizze (die Pfade sind Platzhalter, bis die Code-Struktur feststeht):

```gitignore
# .github/CODEOWNERS – bewusst KEIN "*"-Default: Peripherie bleibt owner-frei
/.github/            @DoenerbudenAli
/.claude/            @DoenerbudenAli
/AGENTS.md           @DoenerbudenAli
/CLAUDE.md           @DoenerbudenAli
/CONTEXT.md          @DoenerbudenAli
/docs/adr/           @DoenerbudenAli
# Kern & Schnittstellen (Platzhalter)
/src/core/           @DoenerbudenAli
/src/api/            @DoenerbudenAli
# Tests überall
/tests/              @DoenerbudenAli
**/*.test.*          @DoenerbudenAli
**/__tests__/        @DoenerbudenAli
# Build-/Lint-Konfiguration = Harness
/package.json        @DoenerbudenAli
/eslint.config.*     @DoenerbudenAli
```

#### 4.2 Auto-Merge als Durchsetzungs-Mechanismus

- Auto-Merge mergt, „after all required reviews and status checks pass“. Einschalten kann es jeder mit Schreibrecht, also auch die App.
- Wer **ohne** Schreibrecht pusht, schaltet es wieder ab.
- Die Option erscheint nur, wenn der PR nicht sofort mergebar ist ([Automatically merging a pull request](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/automatically-merging-a-pull-request)).
- Ablauf: Der Agent öffnet den PR als App und setzt sofort `gh pr merge --auto --squash`. Danach entscheidet GitHub selbst:
  - **Peripherie** (keine Owner-Datei geändert): merged, sobald `ci` und `ai-review` grün sind.
  - **Kern/Tests/Harness** (mindestens eine Owner-Datei geändert): wartet auf das Approval von `@DoenerbudenAli` und merged danach automatisch.
  - Pusht der Agent nach dem Approval noch einmal, verwirft `dismiss_stale_reviews_on_push` die Freigabe ([Available rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets#require-a-pull-request-before-merging)).
- Ein zusätzlicher Check `harness-guard` ist **optional** und nur für Sichtbarkeit gedacht, z. B. ein Label `risk:core`/`risk:periphery` aus `git diff --name-only`. Die eigentliche Durchsetzung macht CODEOWNERS.
- **Fallstricke bei Required Checks:**
  - Ein Workflow, der wegen `paths`-Filter gar nicht startet, bleibt „Pending“ und blockiert ([Workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)).
  - Ein Job, der per `if:` übersprungen wird, meldet dagegen „Success“ ([Using conditions to control job execution](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-jobs-with-conditions)).
  - Required Workflows also ohne `paths`-Filter anlegen und Jobs per `if:` steuern.
  - Der Check-Name ist der Job-Name ([Troubleshooting rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/troubleshooting-rules#troubleshooting-required-status-checks)).
- **Strict oder loose:** Ohne Merge Queue verlangt „strict“ (Branch muss aktuell sein) nach jedem Merge ein Update des Branches. Das blockiert parallele Agenten-PRs. Empfehlung: zunächst **loose** und dazu einen CI-Lauf auf `push` nach `main`, der Fehler nach dem Merge auffängt.
- **Fallback, falls 0 + Code-Owner nicht wie erwartet greift:** `required_approving_review_count: 1`, und Peripherie-PRs approvt eine *zweite* Reviewer-Identität nach grünem KI-Review. Das ist schwächer (siehe ASI09) und nur Plan B.

#### 4.3 Sonderfälle mit genau einem Menschen

- **Owner schreibt selbst einen Kern-PR:** Er kann ihn nicht approven und merged per Admin-Bypass („For pull requests only“).
- **Copilot-PR auf Kernpfade:** Der Owner hat Copilot beauftragt und darf daher nicht approven. Es bleibt nur der Admin-Bypass.
  - Die Ruleset-Option „Additional approval for unattributed Copilot pull requests“ greift nur bei mindestens 1 Pflicht-Approval und ist bei 0 wirkungslos ([Available rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets#additional-approval-for-unattributed-copilot-pull-requests)).
  - Peripherie-PRs von Copilot sind bei 0 Approvals mergebar. Copilot kann seinen Draft aber nicht selbst auf „Ready for review“ setzen ([Risks and mitigations](https://docs.github.com/en/copilot/concepts/agents/cloud-agent/risks-and-mitigations)).

### 5. Testverzeichnisse gegen den implementierenden Agenten schützen

Hintergrund: In ImpossibleBench widersprechen sich Spezifikation und Tests absichtlich. Ein „Bestehen“ beweist dort Schummeln, z. B. durch Testmanipulation. Das Paper untersucht auch, wie Testzugriff und Feedback-Schleife die Cheating-Rate beeinflussen ([Zhong, Raghunathan, Carlini 2025, arXiv:2510.20270](https://arxiv.org/abs/2510.20270)).

**Schicht 1 – Server (harte Grenze):** Testpfade stehen in CODEOWNERS (4.1). Jede Teständerung eines Agenten erzwingt ein Owner-Review, egal mit welchem Werkzeug sie entstand.

**Schicht 2 – Claude Code lokal (Leitplanke):**

- `permissions.deny` ([Permissions](https://code.claude.com/docs/en/permissions)):
  - Deny-Regeln werden vor ask und allow ausgewertet. Ein allow kann kein deny aufheben.
  - `Edit(...)`-Regeln nutzen gitignore-Syntax und gelten für die eingebauten Datei-Tools.
  - Sie gelten auch für erkannte Bash-Dateibefehle (`sed`, `tee` …) und für Umleitungsziele (`> file`).
  - **Sie gelten nicht** für Unterprozesse, die selbst Dateien schreiben, z. B. ein Python- oder Node-Skript.
  - Bash-Regeln sind „not a security boundary“.
- **`PreToolUse`-Hook** ([Hooks](https://code.claude.com/docs/en/hooks)):
  - Er kann mit `permissionDecision: "deny"` oder Exit-Code 2 blockieren. Exit 1 blockiert **nicht**.
  - Deny- und ask-Regeln werden zusätzlich ausgewertet, egal was der Hook zurückgibt.
  - Sinnvoll ist ein Skript, das bei `Bash` den Befehl auf Testpfade prüft und bei `Edit|Write|NotebookEdit` den `file_path`.
- **Die Deny-Regeln selbst schützen:** `.claude/` muss sowohl in CODEOWNERS als auch in den lokalen Deny-Regeln stehen, sonst kann der Agent sich die Regeln selbst wegeditieren.
- **OS-Grenze:** Nur die Sandbox setzt Pfadverbote auf Betriebssystem-Ebene für alle Prozesse durch (`sandbox.filesystem.denyWrite`). Sie läuft aber nur auf macOS, Linux und WSL2. „On native Windows, Claude Code runs commands unsandboxed“ ([Sandboxing](https://code.claude.com/docs/en/sandboxing)). Der Owner arbeitet unter Windows, also ginge das nur über WSL2.
- Skizze `.claude/settings.json`:

```json
{
  "permissions": {
    "deny": [
      "Edit(/tests/**)", "Edit(/**/*.test.*)", "Edit(/**/__tests__/**)",
      "Edit(/.claude/**)", "Edit(/.github/**)", "Edit(/AGENTS.md)", "Edit(/CLAUDE.md)"
    ]
  },
  "hooks": {
    "PreToolUse": [
      { "matcher": "Bash|Edit|Write|NotebookEdit",
        "hooks": [ { "type": "command", "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/guard-protected-paths.sh" } ] }
    ]
  }
}
```

- **Rollen trennen:** Für Aufgaben, bei denen Tests geschrieben werden sollen, eine eigene Session mit eigener Settings-Datei nutzen (`claude --settings tests-author.json`). Diese Rolle darf Tests ändern, aber nicht `src/`. Das Owner-Review über CODEOWNERS bleibt trotzdem bestehen.

**Schicht 3 – Copilot (toolneutral):**

- Copilot CLI und Copilot cloud agent unterstützen Hooks in `.github/hooks/*.json`. `preToolUse` kann „approve or deny tool executions“ ([About hooks](https://docs.github.com/en/copilot/concepts/agents/hooks)).
- Beim cloud agent gilt ([Hooks reference](https://docs.github.com/en/copilot/reference/hooks-reference)):
  - Er lädt **nur** `.github/hooks/*.json`.
  - Er läuft in einer Linux-Sandbox, nur `bash` bzw. `command` werden ausgeführt.
  - `"ask"` wird als `"deny"` behandelt.
- Mit dem PascalCase-Event `PreToolUse` liefert Copilot das Claude-kompatible Format (`tool_name`, `tool_input`) und Claude-Matcher. **Dasselbe Guard-Skript lässt sich also für Claude Code und Copilot nutzen.** Copilot CLI liest zusätzlich `.claude/settings.json`-Hooks (ebd.).
- Pfadbezogene Deny-Regeln wie bei Claude Code sind für Copilot nicht dokumentiert. Hooks plus CODEOWNERS sind dort das Mittel.

### 6. Secrets und Rechte für Agenten in GitHub Actions

**GitHub-Vorgaben:**

- **Standardrechte minimal halten:** „set the default permission for the `GITHUB_TOKEN` to read access only“, dann je Job gezielt erhöhen. Jeder Nutzer mit Schreibrecht kann alle Repo-Secrets lesen ([Secure use reference](https://docs.github.com/en/actions/reference/security/secure-use)). Im Repo stehen die Standardrechte schon auf `read`.
- **`pull_request_target`:**
  - Der Workflow bekommt Secrets und ein schreibfähiges Token. Sicher ist das nur, solange **kein Code aus dem PR** ausgeführt wird.
  - Wer den PR-Head auscheckt und dann baut oder testet, öffnet eine „pwn request“-Lücke.
  - Empfehlung: `pull_request_target` meiden, zur Trennung von Rechten besser `workflow_run` ([Securely using pull_request_target](https://docs.github.com/en/actions/reference/security/securely-using-pull_request_target)).
  - claude-code-action warnt ebenso: „Do not check out an untrusted ref into the workspace root before this action“ ([security.md](https://github.com/anthropics/claude-code-action/blob/main/docs/security.md)).
- **Agenten-Branches liegen im selben Repo, nicht in Forks.** Deshalb bekommen `pull_request`-Workflows **Secrets**. Secrets fehlen nur bei Fork-PRs ([Events that trigger workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)).
  - Folge: Test- und CI-Jobs, die PR-Code ausführen, bekommen **keine** Secrets.
  - Der `ai-review`-Job bekommt nur `CLAUDE_CODE_OAUTH_TOKEN`, minimale `permissions` (`contents: read`, `pull-requests: write`) und eine Tool-Freigabe ohne Ausführung von Repo-Skripten.
  - Weil die Agent-App **kein Workflows-Recht** hat, kann der Agent die Workflow-Dateien, die Secrets nutzen, gar nicht ändern.
- **`GITHUB_TOKEN` löst keine Folge-Workflows aus.** Ausnahme: PRs, die damit erstellt werden, starten Workflows im Zustand „approval-required“. Mit App-Token gibt es diese Bremse nicht ([GITHUB_TOKEN](https://docs.github.com/en/actions/concepts/security/github_token)). Das ist ein weiterer Grund, Agenten-PRs per App-Token statt per `GITHUB_TOKEN` zu öffnen.
- **„Allow GitHub Actions to create and approve pull requests“** ist bei persönlichen Repos standardmäßig aus ([Managing GitHub Actions settings](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository#preventing-github-actions-from-creating-or-approving-pull-requests)). **Aus lassen.** Sonst kann ein Workflow, den ein Agent beeinflusst, Approvals erzeugen.
- **Public-Repo-Spezifika:**
  - Bei claude-code-action ist `show_full_output` wegen öffentlicher Logs aus.
  - `allowed_bots: '*'` ist auf public Repos riskant, weil fremde Apps die Action auslösen könnten.
  - Gegen Prompt-Injection aus Kommentaren helfen `include_comments_by_actor` und `exclude_comments_by_actor` ([security.md](https://github.com/anthropics/claude-code-action/blob/main/docs/security.md)).
- **Actions per SHA pinnen** und OpenSSF Scorecard nutzen ([Secure use reference](https://docs.github.com/en/actions/reference/security/secure-use)).

**OWASP Top 10 for Agentic Applications 2026** (Version 2026, Dezember 2025; [genai.owasp.org](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/)). Relevante Punkte und ihre Umsetzung hier:

| Risiko | Kernaussage (OWASP) | Umsetzung hier |
|---|---|---|
| **ASI01 Agent Goal Hijack** | Manipulierte Eingaben lenken die Ziele des Agenten um. Mittel: Least Privilege für Tools und menschliche Freigabe bei folgenreichen Aktionen. | Public Repo: Jeder kann Issues und Kommentare schreiben. Agenten nur von Schreibberechtigten auslösen lassen (Default der Action), Kommentar-Allowlist nutzen. Kern-Änderungen brauchen immer den Owner. |
| **ASI02 Tool Misuse** | „Least Agency and Least Privilege for Tools“, Just-in-Time-Zugriff und ephemere Zugangsdaten | `--allowedTools` in der Action eng fassen, App-Token mit reduzierten `permissions` ausstellen |
| **ASI03 Identity & Privilege Abuse** | „Task-Scoped, Time-Bound Permissions“ und eigene Identitäten je Agent. Menschliche Freigabe bei Rechteausweitung. | Eigene App statt Owner-Login oder PAT, 1-h-Token, kein Admin- oder Workflows-Recht, App nicht auf der Bypass-Liste |
| **ASI05 Unexpected Code Execution** | Code, den der Agent erzeugt, wird ausgeführt. Mittel: Sandbox und Freigabe für „elevated runs“. | CI-Jobs ohne Secrets, kein `pull_request_target` mit Head-Checkout, lokal WSL2-Sandbox |
| **ASI09 Human-Agent Trust Exploitation** | Automation Bias und Gummistempel-Freigaben. Mittel: explizite Bestätigungen, unveränderliche Logs, „Adaptive Trust Calibration“. | Risikostaffelung hält menschliche Reviews selten und dadurch ernst gemeint. KI-Review ist ein Check, **kein** Approval. PR-Verlauf und Audit-Log dienen als Protokoll. |
| **ASI10 Rogue Agents** | Kill-Switch und Widerruf von Zugangsdaten | Die App-Installation lässt sich sperren oder deinstallieren, das OAuth-Token widerrufen. Das stoppt alle Agenten auf einen Schlag. |

---

## Offene Punkte

1. **Smoke-Test „0 Approvals + Code-Owner-Pflicht“.** Die REST-Doku trennt beide Parameter. Der Satz in [About code owners](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners) („When someone … has enabled required reviews, they also can optionally require approval from a code owner“) lässt aber Zweifel, ob bei Wert 0 der Owner wirklich Pflicht ist.
   - Test: Ruleset anlegen, Bot-PR nur auf Peripherie (muss ohne Approval mergen), Bot-PR auf `/tests/` (muss blockieren).
   - Erst nach Freigabe durch den Owner durchführen. Dieses Ticket hat keine Einstellungen geändert.
2. **Trennung von Agent und Owner auf derselben Maschine.** Ohne eigene OS-Umgebung kann der Agent den `gh`-Login des Owners (inkl. Admin-Bypass) oder den App-Private-Key lesen. Alle Server-Gates wären dann umgehbar.
   - Zu entscheiden: Claude Code in WSL2 oder Devcontainer mit Sandbox.
   - Ein Wrapper erzeugt das App-Token außerhalb und erneuert es nach 1 h.
   - Im Agent-Umfeld gibt es keinen `gh auth login` des Owners.
3. **Signed Commits.** Lokale CLI-Commits mit App-Token sind unsigniert. Unsignierte Head-Commits können selbst einen Squash-Merge blockieren ([About protected branches → Require signed commits](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches#require-signed-commits)).
   - Optionen: vorerst nicht verlangen; Commits über die API erzeugen (Bot-signiert); oder einen SSH-Signing-Key für den Agenten.
4. **Strict oder loose bei Status-Checks** ohne Merge Queue. Hängt davon ab, wie viele Agenten-PRs parallel laufen.
5. **Widerspruch in der claude-code-action-Doku** zum Workflows-Recht der offiziellen Claude-App (security.md: RW angefordert, faq.md: kein Schreibrecht). Das spricht zusätzlich für eine eigene App.
6. **Org-Umzug als spätere Option:** Ein Umzug in eine Free-Organisation brächte Merge Queue (public), `required_reviewers` je Pfad (mit Team) und Bypass-Listen im klassischen Schutz. Das ist für ein Solo-Projekt aktuell nicht nötig.
7. **Copilot cloud agent** setzt einen bezahlten Copilot-Plan voraus. Kern-PRs von Copilot gehen im Solo-Setup nur per Bypass durch. Zu klären ist, ob das als Review-Modell akzeptabel ist, oder ob Copilot nur für Peripherie eingesetzt wird.
8. **Konkrete Pfadliste für CODEOWNERS und Deny-Regeln.** Sie hängt von der noch offenen Code-Struktur ab. Die Pfade oben sind Platzhalter.
