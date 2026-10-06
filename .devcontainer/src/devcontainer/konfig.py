"""Konfiguration des Agenten-Containers.

Alles Projektspezifische kommt aus `harness.toml`, der Code bleibt projektneutral.
"""

import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

# Nur Zeichen, die in einem Hostnamen vorkommen. Die Werte landen in einer Datei, die Bash einliest.
_DOMAIN = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?$")
_WORT = re.compile(r"^[a-z0-9_]+$")


@dataclass(frozen=True)
class Konfig:
    repository: str
    broker_port: int
    rollen: tuple[str, ...]
    app_slug: str
    bot_user_id: int
    github_meta: tuple[str, ...]
    domains: tuple[str, ...]

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


def lade_konfig(pfad: Path) -> Konfig:
    daten = tomllib.loads(pfad.read_text(encoding="utf-8"))
    app = daten["github_app"]
    broker = daten["broker"]
    netz = daten["netz"]
    repository = str(daten["devcontainer"]["repository"])
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


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] != "netz-env":
        print("Aufruf: python -m devcontainer.konfig netz-env <harness.toml>", file=sys.stderr)
        return 2
    sys.stdout.write(netz_env(lade_konfig(Path(argv[1]))))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
