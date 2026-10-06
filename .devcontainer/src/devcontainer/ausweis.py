"""Ausweis vom Broker: ein Rollen-Token für git und gh im Container (ADR 0005, „Broker“, „Rollenbindung“).

Das Token liegt bis kurz vor seinem Ablauf in einem Cache, damit nicht jeder git-Aufruf den Broker fragt.
Lehnt der Broker ab, gibt es keine Ausgabe auf stdout: git und gh laufen dann ohne Token.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, TextIO

# So lange muss ein Token aus dem Cache noch gelten, sonst wird ein neues geholt.
RESTZEIT = timedelta(seconds=300)
GIT_HOST = "github.com"
AUFRUFE = (("token",), ("git-credential", "get"), ("git-credential", "store"), ("git-credential", "erase"))


class AusweisFehler(Exception):
    pass


def _jetzt_utc() -> datetime:
    return datetime.now(UTC)


def _lies_cache(cache: Path, jetzt: datetime) -> str | None:
    try:
        daten = json.loads(cache.read_text(encoding="utf-8"))
        ablauf = datetime.fromisoformat(daten["expires_at"])
        token = str(daten["token"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return token if ablauf - jetzt > RESTZEIT else None


def _schreib_cache(cache: Path, daten: dict[str, Any]) -> None:
    cache.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = cache.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as datei:
        json.dump({"token": daten["token"], "expires_at": daten["expires_at"]}, datei)
    tmp.replace(cache)


def hole_token(
    broker_url: str, schluessel: str, rolle: str, cache: Path, jetzt: Callable[[], datetime] = _jetzt_utc
) -> str:
    if token := _lies_cache(cache, jetzt()):
        return token
    url = f"{broker_url.rstrip('/')}/token"
    if not url.startswith(("http://", "https://")):
        raise AusweisFehler(f"Broker-URL muss http(s) sein: {broker_url}")
    anfrage = urllib.request.Request(  # noqa: S310 (Schema oben geprüft)
        url,
        data=json.dumps({"rolle": rolle}).encode(),
        headers={"Authorization": f"Bearer {schluessel}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(anfrage, timeout=15) as antwort:  # noqa: S310
            daten = json.loads(antwort.read())
    except urllib.error.HTTPError as fehler:
        raise AusweisFehler(f"Broker lehnt ab: HTTP {fehler.code}") from fehler
    except (urllib.error.URLError, OSError) as fehler:
        raise AusweisFehler(f"Broker nicht erreichbar ({broker_url}): {fehler}") from fehler
    _schreib_cache(cache, daten)
    return str(daten["token"])


def _cache_pfad(env: Mapping[str, str]) -> Path:
    basis = Path(env["XDG_CACHE_HOME"]) if env.get("XDG_CACHE_HOME") else Path.home() / ".cache"
    return basis / "harness" / "token.json"


def _git_attribute(stdin: TextIO) -> dict[str, str]:
    attribute: dict[str, str] = {}
    for zeile in stdin:
        zeile = zeile.rstrip("\n")
        if not zeile:
            break
        name, _, wert = zeile.partition("=")
        attribute[name] = wert
    return attribute


def main(
    argv: list[str],
    env: Mapping[str, str] = os.environ,
    stdin: TextIO = sys.stdin,
    stdout: TextIO = sys.stdout,
    jetzt: Callable[[], datetime] = _jetzt_utc,
) -> int:
    if tuple(argv) not in AUFRUFE:
        print(
            f"Aufruf: python -m devcontainer.ausweis {' | '.join(' '.join(a) for a in AUFRUFE)}",
            file=sys.stderr,
        )
        return 2
    if argv[0] == "git-credential":
        if argv[1] != "get":
            return 0
        if _git_attribute(stdin).get("host") != GIT_HOST:
            return 0
    try:
        token = hole_token(
            env["HARNESS_BROKER_URL"],
            env["HARNESS_SCHLUESSEL"],
            env["HARNESS_ROLLE"],
            _cache_pfad(env),
            jetzt,
        )
    except KeyError as fehler:
        print(f"ausweis: Umgebungsvariable {fehler} fehlt", file=sys.stderr)
        return 1
    except AusweisFehler as fehler:
        print(f"ausweis: {fehler}", file=sys.stderr)
        return 1
    if argv[0] == "token":
        stdout.write(f"{token}\n")
    else:
        stdout.write(f"username=x-access-token\npassword={token}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
