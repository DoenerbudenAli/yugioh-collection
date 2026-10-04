# Risikostaffelung

Status: akzeptiert

Der Owner reviewt, **was** das System verspricht. Wie es das einlöst, dürfen Agenten ohne ihn mergen. **Kern** ist jede Datei, die eine Schnittstelle, einen Vertrag, ein Schema, eine fachliche Schwelle, einen Test, eine Regel oder die Sicherheit des Harness festlegt. Änderungen daran brauchen den Owner als Code-Owner. Was ausdrücklich **Peripherie** ist, mergt nach grüner CI und grünem KI-Review automatisch. Damit das per Pfad funktioniert, berührt jede Änderung an einem Versprechen zwangsläufig eine Kern-Datei (**Stolperdraht**), etwa den generierten Schnittstellen-Snapshot eines Moduls. Wir haben uns so entschieden, weil Owner-Review die knappste Ressource ist und „Tests grün“ wenig über Wartbarkeit sagt (METR). Der Owner prüft die Spezifikation, das Innere prüfen die Sensoren: Tests, Mutation Score, Typen, Boundary-Linter, KI-Review und Garbage-Collection-Agenten.

## Regeln

### Gates

- **Ruleset auf `main`:** PR ist Pflicht, `required_approving_review_count: 0`, `require_code_owner_review: true`, Stale-Approvals werden verworfen. Required Checks sind `ci` und `ai-review`. Bypass hat nur die Admin-Rolle („for pull requests only“). `allow_auto_merge` ist an.
- Agenten öffnen PRs nur als `<app-slug>[bot]` (ADR 0005). Öffnet der Owner selbst einen PR, prüft GitHub die Code-Owner-Pflicht nicht (Issue #11). Im Solo-Betrieb ist das bewusst so.
- Harness-Skripte werten `mergeStateStatus` und `reviewRequests.asCodeOwner` aus, nicht `reviewDecision`. Das bleibt bei diesem Ruleset `null`.
- Merge Queue und pfadbezogene „Required reviewers“ gibt es auf einem persönlichen Repo nicht. Das Pfad-Gate ist allein CODEOWNERS.

### Kern und Peripherie

- **CODEOWNERS ist fail-closed.** Die erste Zeile ist `* @DoenerbudenAli`. Darunter stehen die Peripherie-Globs ohne Owner, darunter werden Kern-Dateien innerhalb der Peripherie wieder dem Owner zugeordnet (die letzte passende Zeile gewinnt). Ein neuer Pfad ist Kern, bis ein PR an CODEOWNERS ihn zur Peripherie erklärt.
- **Kern:**
  - Harness und Sicherheit: `.github/` (mit CODEOWNERS und Workflows), `.claude/`, `.devcontainer/` mit Netz-Allowlist, Broker-Code, `justfile`, Paket `harness`, alle Tool-Konfigurationen (ruff, pyright, import-linter, mutmut samt Score-Schwelle, ESLint, `tsconfig`, Stryker, Vitest, Playwright, markdownlint, lychee), Dockerfiles und Deploy-Konfiguration (Caddy, Compose).
  - Kontext und Entscheidungen: `AGENTS.md` auf allen Ebenen, `CONTEXT.md`, `docs/adr/`, `docs/agents/`, `docs/produkt/`, `LICENSE`.
  - Versprechen: die Regeldatei der Kanten (ADR 0001), der Schnittstellen-Snapshot je Modul, die generierten Verträge (OpenAPI, JSON Schema, TS-Typen), die Alembic-Migrationen, die Parameterdatei je Modul und die Betriebseinstellungen jeder Komposition (Bind-Adressen, Origins, Pfade, Ziel des Erkennungsdienstes).
  - Tests: alle Testverzeichnisse und Testdateien samt `conftest.py` und Fixtures, `eval/` samt Referenzfotos.
  - Abhängigkeiten: alle `pyproject.toml`, `uv.lock`, `web/package.json`, `pnpm-lock.yaml`, die Versionsdateien für Python und Node.
- **Peripherie:** das Innere jedes Modulpakets (Kern-Schicht und Adapter), der Code der Kompositionen ohne ihre Betriebseinstellungen, `web/src/` ohne generierte Typen, `docs/qualitaet.md`, `README.md` und die Listen offener Tests.
- **Schnittstellen-Snapshot:** Je Modul wird die öffentliche API an seinem Einstiegspunkt als Datei erzeugt und committet. Die CI erzeugt sie neu und bricht bei jeder Abweichung ab, wie bei den Verträgen (ADR 0003). Ändert ein Agent eine Signatur oder einen Fachtyp, ändert er den Snapshot und braucht den Owner, egal in welcher Datei der Code liegt.
- **Parameterdatei:** Jede Zahl oder Konstante, die eine Produktentscheidung ist (z. B. die Schwellen der Scan-UX, je Halterung und freihändig, oder die Latenzgrenze aus ADR 0002), steht in der Parameterdatei ihres Moduls. Technische Konstanten (Puffer, Retries) bleiben im Code. ruff `PLR2004` ist an. Eine fachliche Zahl außerhalb der Parameterdatei ist ein blockierender Befund für `ai-review`, weil kein deterministischer Check „fachlich“ erkennt.

### Tests vor dem Implementierer schützen

- Ein Feature kommt in zwei PRs. Zuerst öffnet eine *Testschreiber*-Session einen PR nur mit Tests. Er ist Kern, mit seinem Approval nimmt der Owner die Spezifikation ab.
- Damit `main` grün bleibt, stehen neue, noch rote Tests in einer **Liste offener Tests** je Paket. Pytest markiert sie als `xfail(strict=True)`, Vitest und Playwright als `fails`.
- Danach baut eine *Implementierer*-Session in einem eigenen Container den Code. Der `PreToolUse`-Guard sperrt dort die Testpfade. Der Implementierer streicht erledigte Einträge aus der Liste. Bleibt ein Eintrag stehen, obwohl sein Test grün ist, ist die CI rot.
- Die Liste offener Tests darf in einem PR **nur schrumpfen**. Wachsen darf sie nur in einem PR, der auch Kern-Testpfade ändert. So lässt sich kein kaputt gemachter Test in der Liste verstecken.
- Hält der Implementierer einen Test für falsch, hört er auf und kommentiert das Ticket. Die Korrektur kommt als eigener Kern-PR.

### Automerge-Bedingungen

- **`ai-review`** läuft auf jedem PR, bei Kern-PRs als Vorfilter für den Owner. Rot ist es nur bei blockierenden Befunden: Verstoß gegen eine Constraint in `AGENTS.md` oder ein ADR, Korrektheitsfehler, Testmanipulation (umgangene Schwellen, hartkodierte Sonderfälle), ein Begriff gegen `CONTEXT.md`, eine fachliche Zahl außerhalb der Parameterdatei. Alles andere ist ein Kommentar. Diff und PR-Text gelten als nicht vertrauenswürdig: Der Reviewer hat nur Lesewerkzeuge, kein Bash und führt keinen PR-Code aus. Er gibt ein festes JSON-Urteil aus, das ein deterministischer Schritt in den Status übersetzt. Er ist ein Check, nie ein Approval.
- **Iterationslimit:** Jeder Push des Bots auf den PR-Branch ist eine CI-Runde, auch das Öffnen und ein Rebase. Nach höchstens **zwei Runden** ist beim dritten Bot-Push der Check `iterationslimit` (Teil von `ci`) rot. Der Agent kommentiert dann den Stand und hört auf. Lokal ist `just check` unbegrenzt, dort laufen dieselben Gates.
- **Größenlimit:** Ein Bot-PR, der nur Peripherie ändert, hat höchstens **400 geänderte Zeilen**, ohne generierte Dateien und Lockfiles. Darüber ist der Check `groesse` rot, und der Agent teilt den PR auf. Für Kern-PRs gilt kein Limit.
- **Aufheben** lassen sich beide Limits auf zwei Wegen. Entweder pusht der Owner selbst einen Commit (ein Mensch übernimmt). Oder er setzt das Label `weiter`. Das Label zählt nur, wenn laut Timeline (`labeled`) der Owner es gesetzt hat. Die Rolle *Bau* darf Labels setzen.

### Abhängigkeiten

- Dependabot öffnet gruppierte PRs, einmal pro Woche, mit `cooldown` von 7 Tagen. Weil Manifeste und Lockfiles Kern sind, mergt keiner davon ohne den Owner.

## Verworfene Alternativen

- **Ganzer Modulcode ist Kern:** Fast jeder Feature-PR bräuchte den Owner, Automerge bliebe auf Aufräum-PRs beschränkt. Eine Staffelung wäre das nicht.
- **Kern-Schicht ist Kern, Adapter sind Peripherie:** Das Gate hinge am Ordner statt am Versprechen. Eine Signaturänderung im Adapter rutschte durch, eine reine Umbenennung in der Kern-Schicht nicht.
- **CODEOWNERS als Liste der Kernpfade ohne `*`-Default** (Research zu Review-Gates, Issue #4): Ein neuer Top-Level-Ordner, etwa ein Skript, das die CI aufruft, mergte ungeprüft.
- **Tests und Code im selben PR:** Jeder Feature-PR wäre Kern. Testschreiber und Implementierer wären nicht getrennt, die Gegenmaßnahme zu ImpossibleBench fehlte.
- **`xfail`-Marker direkt in der Testdatei:** Der Implementierungs-PR müsste die Testdatei anfassen und wäre damit Kern. **Liste offener Tests ohne die Regel „nur schrumpfen“:** Ein Agent könnte einen Test, den er gebrochen hat, dort verstecken.
- **Automerge für Dependency-Patches:** Gängige Praxis, aber genau dort griffen die Supply-Chain-Würmer auf npm 2025. Eine neue Version ist zudem der einfachste Weg für eine Prompt-Injection mit Folgen.
- **Iterationslimit nur als Prosa in `AGENTS.md`:** Ein Agent in einer Schleife hält sich nicht daran. Erst das Gate macht das Limit hart.
- **Aufheben per Label ohne Prüfung, wer es gesetzt hat:** Die Rolle *Bau* hat PR-Schreibrechte und könnte sich selbst freigeben.
- **KI-Review als Approval:** Freigaben eines Bots zählen im Ruleset nicht als Owner-Review und wären eine Selbstfreigabe der App. Als Check ist das Urteil prüfbar und abschaltbar. **KI-Review mit Bash oder Ausführung von PR-Code:** Per Prompt-Injection im Diff ließe sich das `CLAUDE_CODE_OAUTH_TOKEN` abgreifen.
