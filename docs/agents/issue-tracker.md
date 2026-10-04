# Issue tracker: GitHub

Issues and specs for this repo live as GitHub issues in `DoenerbudenAli/yugioh-collection`. Use the `gh` CLI for all operations.

## Conventions

- **Create an issue**: `gh issue create --title "..." --body "..."`. Use a heredoc for multi-line bodies.
- **Read an issue**: `gh issue view <number> --comments`.
- **List issues**: `gh issue list --state open --json number,title,labels,assignees` with `--label` / `--state` filters.
- **Comment**: `gh issue comment <number> --body "..."`
- **Labels**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **Close**: `gh issue close <number> --comment "..."`

## Pull requests as a triage surface

**PRs as a request surface: no.**

## Wayfinding operations

Used by `/wayfinder`. The **map** is a single issue with **child** issues as tickets.

- **Map**: the issue labelled `wayfinder:map`.
- **Child ticket**: a GitHub sub-issue of the map (`POST repos/DoenerbudenAli/yugioh-collection/issues/<map>/sub_issues -F sub_issue_id=<child-db-id>`). Labels: `wayfinder:<type>` (`research`/`prototype`/`grilling`/`task`).
- **Blocking**: native issue dependencies: `gh api --method POST repos/DoenerbudenAli/yugioh-collection/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>`, where the db id comes from `gh api repos/DoenerbudenAli/yugioh-collection/issues/<n> --jq .id`.
- **Frontier query**: open sub-issues of the map without open blockers (`issue_dependencies_summary.blocked_by == 0`) and without assignee; first in map order wins.
- **Claim**: `gh issue edit <n> --add-assignee @me`, the session's first write.
- **Resolve**: `gh issue comment <n> --body "<answer>"`, then `gh issue close <n>`, then append a context pointer (gist + link) to the map's Decisions-so-far.
