# Harness-Arbeit auf dem Host

Status: akzeptiert
Präzisiert: ADR 0005

**Harness-Arbeit** (Epic [Harness-Bau](https://github.com/DoenerbudenAli/yugioh-collection/issues/25) und alles, was danach am Harness verbessert wird) läuft in der **Claude-Code-App auf dem Host, unter dem GitHub-Login des Owners**. Feature-Arbeit läuft weiter im Container mit der Rolle *Bau*, Wayfinder und Planung mit der Rolle *Planung*, beides wie in ADR 0005. Damit präzisiert dieses ADR die Regeln „Host“, „Eigene Änderungen des Owners“, „Bedienung“ und „Berechtigungsmodus“ aus ADR 0005: Sie gelten nur noch für Feature- und Planungs-Arbeit. Wir haben uns so entschieden, weil die Harness-Verbesserung ein dauernder Prozess ist, den der Owner immer selbst beaufsichtigt, und weil dort zwei Dinge enorm stören: Funde für andere Tickets kann *Bau* nicht selbst anlegen, und die Bedienung per `docker exec` ersetzt nicht die App ([Entscheidung](https://github.com/DoenerbudenAli/yugioh-collection/issues/77)).

## Regeln

- **Aufteilung:** Harness-Arbeit auf dem Host in der App, Feature-Arbeit im Container mit *Bau*, Wayfinder und Planung im Container mit *Planung*. Was Harness-Arbeit ist, bestimmt der Owner.
- **Zugang:** Der Host hat den normalen GitHub-Login des Owners (`gh` und Git Credential Manager). Kein Bot-Token, keine eigene Rolle, kein Broker für Host-Sessions. Der lokale Clone pusht wieder, auf `main` nur per PR (Ruleset).
- **Berechtigungsmodus:** `bypassPermissions` ist für Harness-Sessions auf dem Host erlaubt. Deny-Regeln und der `PreToolUse`-Guard für Tests und Harness greifen nur in Container-Sessions.
- **Abschottung der Container bleibt Pflicht:** Login, `gh`-Konfiguration und Credential-Helper des Owners gelangen nie in einen Container. Alle übrigen Regeln aus ADR 0005 für Container, Rollen, Broker, Netz und Selbstschutz gelten unverändert.
- **Merge:** Harness-PRs mergt der Owner.
- **Negativproben:** Der Owner darf das Ruleset umgehen, ein roter Check sperrt seinen eigenen PR also nicht. Proben, die eine Merge-Sperre oder Regeln für Bot-PRs beweisen, laufen als Bot-PR aus einem Container mit *Bau*.

## Folgen

- Bei Harness-PRs greift das Kern-Gate nicht. Sie laufen unter dem Owner, und Owner-PRs brauchen kein Approval (Issue #11). Der Owner beaufsichtigt Harness-Sessions selbst. Für Container-Agenten gelten die Gates weiter.
- Ein reingelegter Agent in einer Harness-Session kann Tickets, die Map und ADRs umschreiben und so Anweisungen für spätere Sessions einschleusen. Ohne Container fallen für Harness-Sessions auch Netz-Allowlist und Grenze weg: Der Agent erreicht jedes Ziel und sieht die Dateien des Owners. Der Owner hält seinen Rechner nicht für sensibel und nimmt das hin.
- Jede Local-Session auf dem Host erreicht den GitHub-Login des Owners, auch Sessions für andere Projekte. Die Begründung in ADR 0005, dort sei nichts mehr zu holen, gilt nicht mehr.
- Ein Commit des Owners beweist nicht mehr, dass ein Mensch eingegriffen hat. Auch Harness-Sessions committen als Owner.

## Verworfene Alternativen

- **Rolle `harness` mit Bot-Token vom Broker und Credential-Helper auf dem Host:** Das Kern-Gate bliebe für Bot-PRs erhalten, aber mit Broker-Umbau, neuer Rolle und Token-Verwaltung für einen Gewinn, den der Owner bei eigener Aufsicht nicht braucht.
- **Nur *Bau* bekommt Issues write und bleibt im Container:** Das löst die Funde für andere Tickets, nicht aber die Bedienung in der App.
- **Eigener Windows-User für Agenten:** Er schützt den Login des Owners, kostet aber eine zweite Toolchain und den Wechsel des Users im Alltag.
- **Befristet bis zum Ende des Harness-Baus:** Harness-Arbeit endet nie, eine Frist wäre nur ein Termin zum Verlängern.
