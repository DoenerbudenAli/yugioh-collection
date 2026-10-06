"""Konfiguration des Brokers.

Alles Projektspezifische kommt aus `harness.toml`, der Code bleibt projektneutral.
"""

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Konfig:
    app_id: int
    installation_id: int
    repository: str
    port: int
    rollen: dict[str, dict[str, str]]
    github_api: str = "https://api.github.com"


def lade_konfig(pfad: Path) -> Konfig:
    daten = tomllib.loads(pfad.read_text(encoding="utf-8"))
    app = daten["github_app"]
    broker = daten["broker"]
    return Konfig(
        app_id=int(app["app_id"]),
        installation_id=int(app["installation_id"]),
        repository=str(broker["repository"]),
        port=int(broker["port"]),
        rollen={name: dict(rechte) for name, rechte in broker["rollen"].items()},
    )
