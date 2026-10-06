"""Konfiguration des Agenten-Containers.

Alles Projektspezifische kommt aus `harness.toml`, der Code bleibt projektneutral.
"""

import json
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Arbeitsordner im Container (Volume); der Clone liegt in /arbeit/<repo>.
ARBEIT = "/arbeit"

# Nur Zeichen, die in einem Hostnamen vorkommen. Die Werte landen in einer Datei, die Bash einliest.
_DOMAIN = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?$")
_WORT = re.compile(r"^[a-z0-9_]+$")
# Die Felder einer Skill-Sammlung landen in einer Datei, die das Bau-Skript zeilenweise einliest.
_SAMMLUNG_MUSTER = {
    "plugin": re.compile(r"^[a-z0-9][a-z0-9-]*$"),
    "github": re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9][A-Za-z0-9._-]*$"),
    "version": re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$"),
    "commit": re.compile(r"^[0-9a-f]{40}$"),
}


@dataclass(frozen=True)
class Sammlung:
    """Eine Skill-Sammlung (Claude-Code-Plugin) aus GitHub, fest auf einen Tag und dessen Commit."""

    plugin: str
    github: str
    version: str
    commit: str


@dataclass(frozen=True)
class Konfig:
    repository: str
    broker_port: int
    rollen: tuple[str, ...]
    app_slug: str
    bot_user_id: int
    github_meta: tuple[str, ...]
    domains: tuple[str, ...]
    skills: tuple[Sammlung, ...]

    @property
    def bot_name(self) -> str:
        return f"{self.app_slug}[bot]"

    @property
    def bot_email(self) -> str:
        return f"{self.bot_user_id}+{self.app_slug}[bot]@users.noreply.github.com"

    @property
    def image(self) -> str:
        return f"ghcr.io/{self.repository.lower()}/devcontainer"

    @property
    def repo_name(self) -> str:
        return self.repository.split("/", 1)[1]

    @property
    def klon(self) -> str:
        return f"{ARBEIT}/{self.repo_name}"


def lade_konfig(pfad: Path) -> Konfig:
    daten = tomllib.loads(pfad.read_text(encoding="utf-8"))
    app = daten["github_app"]
    broker = daten["broker"]
    netz = daten["netz"]
    devcontainer = daten["devcontainer"]
    repository = str(devcontainer["repository"])
    if repository.count("/") != 1:
        raise ValueError(f"[devcontainer] repository muss <owner>/<repo> sein: {repository}")
    return Konfig(
        repository=repository,
        broker_port=int(broker["port"]),
        rollen=tuple(broker["rollen"]),
        app_slug=str(app["slug"]),
        bot_user_id=int(app["bot_user_id"]),
        github_meta=tuple(str(s) for s in netz["github_meta"]),
        domains=tuple(str(d) for d in netz["domains"]),
        skills=tuple(
            Sammlung(
                plugin=str(s["plugin"]),
                github=str(s["github"]),
                version=str(s["version"]),
                commit=str(s["commit"]),
            )
            for s in devcontainer.get("skills", [])
        ),
    )


def netz_env(k: Konfig) -> str:
    """Die Allowlist als Datei für `firewall.sh` (Shell-Variablen)."""
    for domain in k.domains:
        if not _DOMAIN.match(domain):
            raise ValueError(f"Domain ungültig: {domain!r}")
    for schluessel in k.github_meta:
        if not _WORT.match(schluessel):
            raise ValueError(f"github_meta ungültig: {schluessel!r}")
    return (
        f"BROKER_PORT={k.broker_port}\n"
        f'GITHUB_META="{" ".join(k.github_meta)}"\n'
        f'DOMAINS="{" ".join(k.domains)}"\n'
    )


def skills_liste(k: Konfig) -> str:
    """Die Skill-Sammlungen als Liste für `skills-holen.sh`: je Zeile Plugin, GitHub-Repo, Tag und Commit."""
    zeilen: list[str] = []
    for sammlung in k.skills:
        werte: list[str] = []
        for feld, muster in _SAMMLUNG_MUSTER.items():
            wert: str = getattr(sammlung, feld)
            if not muster.match(wert):
                raise ValueError(f"Skill-Sammlung {sammlung.plugin!r}: {feld} ungültig: {wert!r}")
            werte.append(wert)
        zeilen.append(" ".join(werte) + "\n")
    return "".join(zeilen)


def claude_json(k: Konfig, basis: dict[str, Any]) -> dict[str, Any]:
    """`~/.claude.json` des Users agent: Claude fragt beim ersten Start nicht, ob es dem Clone vertraut."""
    return {**basis, "projects": {k.klon: {"hasTrustDialogAccepted": True}}}


def main(argv: list[str]) -> int:
    match argv:
        case ["netz-env", toml]:
            sys.stdout.write(netz_env(lade_konfig(Path(toml))))
        case ["skills-liste", toml]:
            sys.stdout.write(skills_liste(lade_konfig(Path(toml))))
        case ["claude-json", toml, basis]:
            daten = claude_json(lade_konfig(Path(toml)), json.loads(Path(basis).read_text(encoding="utf-8")))
            sys.stdout.write(json.dumps(daten, indent=2) + "\n")
        case _:
            print(
                "Aufruf: python -m devcontainer.konfig netz-env|skills-liste <harness.toml>\n"
                "        python -m devcontainer.konfig claude-json <harness.toml> <basis.json>",
                file=sys.stderr,
            )
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
