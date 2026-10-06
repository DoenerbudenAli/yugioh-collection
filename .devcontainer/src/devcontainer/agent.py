"""Startskript auf dem Host: `just agent <rolle> <name>` und `just weg <name>` (ADR 0005, „Arbeitsstränge“).

Je Arbeitsstrang ein Container `agent-<name>` mit eigenem Volume. Das Skript meldet den Schlüssel des
Containers beim Broker an und ab und öffnet Claude im Container. Das `setup-token` gelangt nur über die
Umgebung von `docker exec` in den Container, nie auf eine Kommandozeile oder in die Container-Konfiguration.
"""

import json
import os
import re
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

from devcontainer.konfig import Konfig, lade_konfig

Zustand = Literal["fehlt", "gestoppt", "laeuft"]

ANMELDEDAUER = 24 * 3600
ARBEIT = "/arbeit"
# Bereit-Zeichen: entsteht erst, wenn Firewall und Clone stehen. Es liegt auf tmpfs, damit es nach einem
# Neustart fehlt, bis die Firewall wieder gesetzt ist. uid 1000 ist der User agent im Image.
BEREIT = "/run/harness/bereit"
BEREIT_TMPFS = "--tmpfs=/run/harness:uid=1000,gid=1000,mode=0700"
BEREIT_WARTEN = 180.0
# So meldet docker ein fehlendes Objekt; jeder andere Fehler (z. B. Docker Desktop aus) ist echt.
_FEHLT = "No such "
_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
ADMIN_GEHEIMNIS_STANDARD = Path(r"C:\ProgramData\harness-broker\admin-geheimnis")
SETUP_TOKEN_STANDARD = Path.home() / ".config" / "harness" / "claude-setup-token"


class AgentFehler(Exception):
    pass


class Docker(Protocol):
    def zustand(self, name: str) -> Zustand: ...
    def env_von(self, name: str) -> dict[str, str]: ...
    def pull(self, image: str) -> None: ...
    def volume_anlegen(self, name: str) -> None: ...
    def run(self, name: str, image: str, env: Mapping[str, str]) -> None: ...
    def start(self, name: str) -> None: ...
    def warte_bereit(self, name: str, pfad: str) -> None: ...
    def exec_claude(self, name: str, arbeitsordner: str, token: str) -> int: ...
    def entfernen(self, name: str) -> None: ...


class BrokerAdmin:
    """Meldet Schlüssel mit dem Admin-Geheimnis beim Broker an und ab."""

    def __init__(self, url: str, admin_geheimnis: str) -> None:
        if not url.startswith(("http://", "https://")):
            raise ValueError(f"Broker-URL muss http(s) sein: {url}")
        self._url = url.rstrip("/")
        self._admin = admin_geheimnis

    def _post(self, pfad: str, koerper: dict[str, Any]) -> None:
        anfrage = urllib.request.Request(  # noqa: S310 (Schema im Konstruktor geprüft)
            f"{self._url}{pfad}",
            data=json.dumps(koerper).encode(),
            headers={"Authorization": f"Bearer {self._admin}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(anfrage, timeout=15):  # noqa: S310
                pass
        except urllib.error.HTTPError as fehler:
            raise AgentFehler(f"Broker lehnt {pfad} ab: HTTP {fehler.code}") from fehler
        except (urllib.error.URLError, OSError) as fehler:
            raise AgentFehler(f"Broker nicht erreichbar ({self._url}): {fehler}") from fehler

    def anmelden(self, schluessel: str, rolle: str, ablauf: float) -> None:
        self._post("/schluessel", {"schluessel": schluessel, "rolle": rolle, "ablauf": ablauf})

    def abmelden(self, schluessel: str) -> None:
        self._post("/schluessel/abmelden", {"schluessel": schluessel})


@dataclass
class Umgebung:
    konfig: Konfig
    docker: Docker
    broker: BrokerAdmin
    setup_token_datei: Path = SETUP_TOKEN_STANDARD
    jetzt: Callable[[], float] = time.time
    ausgabe: Callable[[str], None] = field(default=print)


def _container(name: str) -> str:
    if not _NAME.match(name):
        raise AgentFehler(f"Name ungültig: {name!r} (erlaubt: a-z, 0-9, '-', höchstens 40 Zeichen)")
    return f"agent-{name}"


def _setup_token(datei: Path) -> str:
    try:
        token = datei.read_text(encoding="utf-8").strip()
    except OSError as fehler:
        raise AgentFehler(f"setup-token nicht lesbar: {datei} ({fehler.strerror})") from fehler
    if not token:
        raise AgentFehler(f"setup-token ist leer: {datei}")
    return token


def _container_env(u: Umgebung, schluessel: str, rolle: str) -> dict[str, str]:
    k = u.konfig
    return {
        "HARNESS_SCHLUESSEL": schluessel,
        "HARNESS_ROLLE": rolle,
        "HARNESS_BROKER_URL": f"http://host.docker.internal:{k.broker_port}",
        "HARNESS_REPOSITORY": k.repository,
        "GIT_AUTHOR_NAME": k.bot_name,
        "GIT_COMMITTER_NAME": k.bot_name,
        "GIT_AUTHOR_EMAIL": k.bot_email,
        "GIT_COMMITTER_EMAIL": k.bot_email,
    }


def start(u: Umgebung, rolle: str, name: str) -> int:
    """Neuen Container anlegen oder einen vorhandenen fortsetzen, dann Claude darin öffnen."""
    if rolle not in u.konfig.rollen:
        raise AgentFehler(f"Rolle {rolle!r} gibt es nicht (harness.toml: {', '.join(u.konfig.rollen)})")
    container = _container(name)
    token = _setup_token(u.setup_token_datei)
    zustand = u.docker.zustand(container)
    ablauf = u.jetzt() + ANMELDEDAUER

    if zustand == "fehlt":
        schluessel = secrets.token_urlsafe(32)
        u.broker.anmelden(schluessel, rolle, ablauf)
        u.ausgabe(f"Neuer Container {container} (Rolle {rolle}) aus {u.konfig.image}")
        u.docker.pull(u.konfig.image)
        u.docker.volume_anlegen(container)
        u.docker.run(container, u.konfig.image, _container_env(u, schluessel, rolle))
    else:
        env = u.docker.env_von(container)
        if env.get("HARNESS_ROLLE") != rolle:
            raise AgentFehler(f"{container} läuft mit Rolle {env.get('HARNESS_ROLLE')!r}, nicht {rolle!r}")
        u.broker.anmelden(env["HARNESS_SCHLUESSEL"], rolle, ablauf)
        if zustand == "gestoppt":
            u.ausgabe(f"Starte {container} neu")
            u.docker.start(container)

    u.docker.warte_bereit(container, BEREIT)
    return u.docker.exec_claude(container, f"{ARBEIT}/{u.konfig.repo_name}", token)


def weg(u: Umgebung, name: str) -> int:
    """Schlüssel abmelden, Container und Volume löschen. Ein fehlender Broker hält das Aufräumen nicht auf."""
    container = _container(name)
    if u.docker.zustand(container) != "fehlt":
        try:
            u.broker.abmelden(u.docker.env_von(container)["HARNESS_SCHLUESSEL"])
        except AgentFehler as fehler:
            u.ausgabe(f"Warnung: {fehler}. Der Schlüssel verfällt spätestens mit seinem Ablauf.")
    u.docker.entfernen(container)
    u.ausgabe(f"{container} samt Volume entfernt")
    return 0


def abmelden(u: Umgebung, name: str) -> int:
    """Nur den Schlüssel abmelden: Der Container läuft weiter, bekommt aber keine neuen Tokens."""
    container = _container(name)
    if u.docker.zustand(container) == "fehlt":
        raise AgentFehler(f"{container} gibt es nicht")
    u.broker.abmelden(u.docker.env_von(container)["HARNESS_SCHLUESSEL"])
    u.ausgabe(f"Schlüssel von {container} abgemeldet")
    return 0


Ausfuehren = Callable[..., tuple[int, str, str]]


def _ausfuehren(
    argv: Sequence[str], env: Mapping[str, str] | None = None, interaktiv: bool = False
) -> tuple[int, str, str]:
    ergebnis = subprocess.run(  # noqa: S603 (feste docker-Befehle, keine Shell)
        list(argv),
        env=None if env is None else dict(env),
        capture_output=not interaktiv,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return ergebnis.returncode, ergebnis.stdout or "", ergebnis.stderr or ""


class CliDocker:
    """Die Docker-Befehle des Startskripts. Geheimnisse gehen nur über die Umgebung an `docker`."""

    def __init__(self, ausfuehren: Ausfuehren = _ausfuehren) -> None:
        self._ausfuehren = ausfuehren

    def _muss(self, argv: list[str], env: Mapping[str, str] | None = None, interaktiv: bool = False) -> str:
        code, aus, fehler = self._ausfuehren(argv, env, interaktiv)
        if code != 0:
            raise AgentFehler(f"{' '.join(argv[:3])} … ist fehlgeschlagen (Exit {code}): {fehler.strip()}")
        return aus

    def zustand(self, name: str) -> Zustand:
        code, aus, fehler = self._ausfuehren(
            ["docker", "container", "inspect", "--format", "{{.State.Running}}", name]
        )
        if code != 0:
            if _FEHLT in fehler:
                return "fehlt"
            raise AgentFehler(f"docker antwortet nicht: {fehler.strip()}")
        return "laeuft" if aus.strip() == "true" else "gestoppt"

    def env_von(self, name: str) -> dict[str, str]:
        aus = self._muss(["docker", "container", "inspect", "--format", "{{json .Config.Env}}", name])
        eintraege: list[str] = json.loads(aus)
        return dict(e.split("=", 1) for e in eintraege)

    def pull(self, image: str) -> None:
        self._muss(["docker", "pull", image], interaktiv=True)

    def volume_anlegen(self, name: str) -> None:
        self._muss(["docker", "volume", "create", name])

    def run(self, name: str, image: str, env: Mapping[str, str]) -> None:
        argv = [
            "docker", "run", "-d", "--name", name, "--hostname", name,
            "--cap-add=NET_ADMIN", "--cap-add=NET_RAW", "--security-opt=no-new-privileges",
            f"--volume={name}:{ARBEIT}", BEREIT_TMPFS,
        ]  # fmt: skip
        for schluessel in env:
            argv += ["--env", schluessel]
        self._muss([*argv, image], {**os.environ, **env})

    def start(self, name: str) -> None:
        self._muss(["docker", "start", name])

    def warte_bereit(self, name: str, pfad: str) -> None:
        ende = time.monotonic() + BEREIT_WARTEN
        while time.monotonic() < ende:
            if self.zustand(name) != "laeuft":
                _, log, log_fehler = self._ausfuehren(["docker", "logs", "--tail", "30", name])
                raise AgentFehler(f"{name} ist beim Start beendet worden:\n{log}{log_fehler}")
            if self._ausfuehren(["docker", "exec", name, "test", "-e", pfad])[0] == 0:
                return
            time.sleep(1)
        raise AgentFehler(f"{name} ist nach {BEREIT_WARTEN:.0f} s nicht bereit ({pfad} fehlt)")

    def exec_claude(self, name: str, arbeitsordner: str, token: str) -> int:
        argv = [
            "docker", "exec", "-it", "--user", "agent", "--workdir", arbeitsordner,
            "--env", "CLAUDE_CODE_OAUTH_TOKEN", name, "claude",
        ]  # fmt: skip
        code, _, _ = self._ausfuehren(argv, {**os.environ, "CLAUDE_CODE_OAUTH_TOKEN": token}, interaktiv=True)
        return code

    def entfernen(self, name: str) -> None:
        for argv in (["docker", "rm", "--force", name], ["docker", "volume", "rm", "--force", name]):
            code, _, fehler = self._ausfuehren(argv)
            if code != 0 and _FEHLT not in fehler:
                raise AgentFehler(f"{' '.join(argv[:3])} … ist fehlgeschlagen: {fehler.strip()}")


def main(argv: list[str], harness_toml: Path) -> int:
    befehle = {"start": 2, "weg": 1, "abmelden": 1}
    if not argv or befehle.get(argv[0]) != len(argv) - 1:
        print("Aufruf: agent.py start <rolle> <name> | weg <name> | abmelden <name>", file=sys.stderr)
        return 2
    try:
        try:
            konfig = lade_konfig(harness_toml)
        except (OSError, KeyError, ValueError, TypeError) as fehler:
            raise AgentFehler(
                f"harness.toml unvollständig oder kaputt ({harness_toml}): {fehler!r}"
            ) from fehler
        admin_datei = Path(os.environ.get("HARNESS_ADMIN_GEHEIMNIS", ADMIN_GEHEIMNIS_STANDARD))
        try:
            admin = admin_datei.read_text(encoding="ascii").strip()
        except OSError as fehler:
            raise AgentFehler(f"Admin-Geheimnis nicht lesbar: {admin_datei} – läuft der Broker?") from fehler
        u = Umgebung(konfig, CliDocker(), BrokerAdmin(f"http://127.0.0.1:{konfig.broker_port}", admin))
        if argv[0] == "start":
            return start(u, argv[1], argv[2])
        return weg(u, argv[1]) if argv[0] == "weg" else abmelden(u, argv[1])
    except AgentFehler as fehler:
        print(f"Fehler: {fehler}", file=sys.stderr)
        return 1
