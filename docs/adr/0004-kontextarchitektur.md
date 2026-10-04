# Kontextarchitektur

Status: akzeptiert

Die einzige Kontextdatei für Agenten ist **`AGENTS.md`**, auf Deutsch. Die Root-Datei ist ein kurzer Index mit harten Constraints. Dateien in Unterordnern entstehen nur bei Bedarf. Langlebiges Wissen liegt in `docs/`, Pläne liegen nur in Issues, und die CI prüft die Doku wie Code. Wir haben uns so entschieden, weil die einzige unabhängige Messung (ETH, arXiv 2602.11988) Kontextdateien keinen generellen Nutzen bei über 20 % Mehrkosten bescheinigt. Nur nicht ableitbare Mindestanforderungen lohnen sich, und jede Zeile Prosa ist eine Zeile, die veralten oder widersprechen kann. Eine einzige toolneutrale Datei hält Claude Code und Copilot auf demselben Stand.

## Regeln

- **Nur `AGENTS.md`.** Im Repo gibt es kein `CLAUDE.md`. Claude Code liest `AGENTS.md` selbst (ab v2.1.277), Copilot nimmt die nächstgelegene. Existiert ein `CLAUDE.md`, liest Claude nur noch dieses und ignoriert alle `AGENTS.md`, auch die in Unterordnern. Wer ein privates `CLAUDE.local.md` nutzt, stellt in seinen User-Settings `claude-md-and-agents-md` ein. Was nur Claude betrifft (Hooks, Permissions), steht in `.claude/settings.json`.
- **Sprache:** Deutsch, mit den Begriffen aus `CONTEXT.md`.
- **Root-`AGENTS.md`**, höchstens 120 Zeilen, genau diese Abschnitte: Worum es geht (mit Verweis auf `CONTEXT.md`), Befehle (ein Einstieg `just check`), Harte Constraints, Wo was liegt, Arbeitsweise. Eine Übersicht über die Codestruktur gehört nicht hinein.
- **Harte Constraints** sind je eine Zeile mit Link auf ein ADR oder `[check: <name>]`, wobei `<name>` ein Rezept der `justfile` ist. Eine Regel, die sich wiederholt bewährt, wandert von Prosa in einen Check.
- **`AGENTS.md` in Unterordnern** gibt es nur für eine nicht ableitbare Regel, die kein Linter abdeckt, mit höchstens 40 Zeilen. Pfadgebundene Regeln in toolspezifischen Formaten (`.claude/rules/`, `.github/instructions/`, `.github/copilot-instructions.md`) sind verboten. Skills entstehen erst, wenn ein Ablauf zum zweiten Mal vorkommt.
- **`docs/`:** `adr/` (Entscheidungen), `produkt/` (PRD und Specs), `agents/` (Konventionen für Agenten-Werkzeuge) und `qualitaet.md` (Note je Modul). `CONTEXT.md` bleibt im Root, weil es einen fachlichen Kontext gibt, auch wenn er in fünf Module geschnitten ist.
- **Pläne leben nur in Issues** (Wayfinder-Map, Tickets). Exec-Plans gibt es im Repo nicht. Ein Agent schreibt den Fortschritt einer langen Arbeit als Kommentar ins Issue. Research liegt auf Wegwerf-Branches, und die tragenden Fakten wandern ins ADR.
- **Auto-Memory ist für dieses Repo aus** (`.claude/settings.json`). Was ein Agent über das Repo lernt, geht per PR in `AGENTS.md`, ein ADR oder einen Check. Jeder Agentenfehler wird so behoben, dass er nicht wiederkehrt.
- **ADRs:**
  - Jedes ADR trägt unter dem Titel eine Statuszeile: `Status: akzeptiert`, `Status: ersetzt durch ADR NNNN` oder zusätzlich `Präzisiert: ADR NNNN`.
  - ADR 0001–0003 bekommen ihre Statuszeile einmalig beim Bau des Harness.
  - Akzeptierte ADRs sind unveränderlich, ersetzt wird per neuem ADR (Supersede). An einem bestehenden ADR erlaubt die CI nur die Statuszeile. Tippfehler gehen mit dem Label `adr-korrektur` durch, die eigentliche Sperre bleibt das Owner-Review.
  - Neues ADR, Statuszeile des ersetzten ADR und die Constraint-Zeile in `AGENTS.md` ändern sich im selben PR.
  - Ein ADR ist nur angebracht, wenn eine Entscheidung schwer umkehrbar, ohne Kontext überraschend und ein echter Trade-off ist.
- **Task-Runner:** `just`, eine `justfile` für die Python-Seite und `web/`.

## Doku-Checks

Gates im Check `ci`, lokal über denselben Befehl `just check`:

1. **Interne Links und Anker** in allen `.md` sind gültig (lychee, offline).
2. **Pfad-Zitate:** Jeder Pfad in Backticks in einer `AGENTS.md` und in `docs/agents/` existiert. ADRs sind ausgenommen, weil sie unveränderlich sind. In ihnen werden nur Verweise auf andere ADRs geprüft.
3. **Form der Kontextdateien:** Zeilengrenzen 120 bzw. 40. Verboten sind `CLAUDE.md`, `.claude/rules/`, `.github/instructions/` und `.github/copilot-instructions.md`.
4. **Constraint-Zeilen** verweisen auf ein ADR oder auf ein existierendes `just`-Rezept.
5. **ADRs:** Nummern fortlaufend, Dateinamen nach Muster, Statuszeile gültig, Ziele von „ersetzt durch“ und „präzisiert“ existieren, Unveränderlichkeit gegen den Basis-Branch. Ein `ADR NNNN` in einem Code-Kommentar zeigt auf ein existierendes, nicht ersetztes ADR.
6. **Kanten-Abgleich:** Die Regeldatei aus ADR 0001 stimmt mit dem markierten Kantenblock im jüngsten gültigen ADR überein, das einen solchen Block enthält. Eine Kantenänderung erzwingt so ein neues ADR. Der Block in ADR 0001 bekommt seine Markierung einmalig per `adr-korrektur`.
7. **Markdown-Lint** (markdownlint-cli2 oder rumdl, lockere Konfiguration).

Externe Links laufen wöchentlich außerhalb der Gates und öffnen bei Fehlern ein Issue. Die Checks 2–6 liegen als pytest-Tests im Paket `harness` des uv-Workspace. Es steht nicht in der Regeldatei, kein Modul darf es importieren, und es gehört zum Kern. Inhaltliche Veraltung (Doku sagt X, Code tut Y) und die Überarbeitung nach Modellwechseln prüfen keine Gates, das übernehmen die Garbage-Collection-Agenten.

## Verworfene Alternativen

- **`CLAUDE.md` mit `@AGENTS.md`-Import:** Das liefe auch auf alten Versionen. Aber jeder Ordner mit eigener `AGENTS.md` bräuchte dann eine weitere `CLAUDE.md` als Weiche, sonst sieht Claude die Ordnerdatei nicht.
- **`CLAUDE.md` mit eigenem Inhalt neben `AGENTS.md`:** Das wären zwei Quellen, die auseinanderlaufen, und Claude wählt bei Widersprüchen beliebig.
- **Englische Kontextdateien:** Dafür spräche die größere Übung der Agenten. Die Übersetzung der deutschen Fachbegriffe würde aber genau die Begriffsdrift erzeugen, die das Glossar verhindern soll.
- **`AGENTS.md` als Pflicht pro Modul mit fester Struktur:** Das wäre eine Übersicht, die den Code wiederholt. Übersichten helfen laut ETH-Studie nicht und veralten.
- **`.claude/rules/` oder Copilot-`.instructions.md`:** Sie leisten dasselbe wie Ordner-`AGENTS.md`, sind aber an ein Werkzeug gebunden.
- **Exec-Plans im Repo (OpenAI):** Pläne leben bereits in Issues, ein zweiter Ort würde veralten.
- **Auto-Memory an:** Das wäre maschinenlokaler Kontext, den Copilot, die CI und jede frische Agenten-Sandbox nicht sehen.
- **Tippfehler nur per neuem ADR:** Das wäre Zeremonie ohne Schutzgewinn, weil ADRs ohnehin Owner-Review brauchen.
- **Externe Links als Gate:** Fremde Server würden unbeteiligte PRs rot färben.
- **Alle Checks selbst geschrieben oder nur als Actions im Workflow-YAML:** Für Links und Lint gibt es Standardwerkzeuge. Reine YAML-Checks liefen lokal nicht.
- **poethepoet oder Make statt `just`:** poethepoet deckt nur die Python-Seite ab, Make ist unter Windows unhandlich.
