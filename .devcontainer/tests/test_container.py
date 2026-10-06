"""Negativproben am echten Image (ADR 0005, „Grenze“, „Netz“). Brauchen Docker und Netz.

Das Image kommt aus `HARNESS_TEST_IMAGE` (CI) oder wird hier als `harness-devcontainer:test` gebaut.
Lokal gebaute Images dienen nur diesen Tests, Sessions laufen immer aus GHCR.
"""

import os
import shutil
import subprocess
import time
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest

from devcontainer.agent import CliDocker
from devcontainer.konfig import lade_konfig

pytestmark = [
    pytest.mark.container,
    pytest.mark.skipif(shutil.which("docker") is None, reason="Docker fehlt"),
]

REPO_ROOT = Path(__file__).resolve().parents[2]
KONFIG = lade_konfig(REPO_ROOT / "harness.toml")
KLON = f"/arbeit/{KONFIG.repo_name}"


def _docker(*argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["docker", *argv], capture_output=True, text=True, check=False)


@pytest.fixture(scope="session")
def image() -> str:
    if name := os.environ.get("HARNESS_TEST_IMAGE"):
        return name
    name = "harness-devcontainer:test"
    gebaut = subprocess.run(
        [
            "docker",
            "build",
            "-f",
            str(REPO_ROOT / ".devcontainer" / "Dockerfile"),
            "-t",
            name,
            str(REPO_ROOT),
        ],
        check=False,
    )
    assert gebaut.returncode == 0, "docker build ist fehlgeschlagen"
    return name


def _starten(image: str, *extra: str) -> str:
    name = f"harness-test-{uuid.uuid4().hex[:8]}"
    ergebnis = _docker(
        "run", "-d", "--name", name,
        "--cap-add=NET_ADMIN", "--cap-add=NET_RAW", "--security-opt=no-new-privileges",
        "--add-host=host.docker.internal:host-gateway",
        "--env", f"HARNESS_REPOSITORY={KONFIG.repository}",
        "--env", "HARNESS_SCHLUESSEL=test-schluessel-ohne-broker-0000",
        "--env", "HARNESS_ROLLE=bau",
        "--env", f"HARNESS_BROKER_URL=http://host.docker.internal:{KONFIG.broker_port}",
        *extra, image,
    )  # fmt: skip
    assert ergebnis.returncode == 0, ergebnis.stderr
    return name


@pytest.fixture(scope="session")
def container(image: str) -> Iterator[str]:
    name = _starten(image)
    try:
        CliDocker().warte_bereit(name, f"{KLON}/.git")
        yield name
    finally:
        _docker("rm", "--force", name)


def _als_agent(container: str, befehl: str) -> subprocess.CompletedProcess[str]:
    return _docker("exec", "--user", "agent", container, "bash", "-lc", befehl)


def test_fremde_domain_ist_gesperrt(container: str) -> None:
    assert _als_agent(container, "curl -sS --max-time 5 https://example.com").returncode != 0


def test_github_ist_erreichbar(container: str) -> None:
    ergebnis = _als_agent(container, "curl -fsS --max-time 10 https://api.github.com/zen")
    assert ergebnis.returncode == 0, ergebnis.stderr


def test_anthropic_api_ist_erreichbar(container: str) -> None:
    ergebnis = _als_agent(container, "curl -sS --max-time 10 -o /dev/null https://api.anthropic.com")
    assert ergebnis.returncode == 0, ergebnis.stderr


@pytest.mark.parametrize("programm", ["sudo", "docker"])
def test_kein_weg_zu_root_oder_docker(container: str, programm: str) -> None:
    assert _als_agent(container, f"command -v {programm}").returncode != 0
    assert _als_agent(container, "test -S /var/run/docker.sock").returncode != 0


def test_agent_ist_nicht_root_und_kann_die_firewall_nicht_aendern(container: str) -> None:
    assert _als_agent(container, "id -u").stdout.strip() != "0"
    assert _als_agent(container, "iptables -P OUTPUT ACCEPT").returncode != 0
    assert _als_agent(container, "curl -sS --max-time 5 https://example.com").returncode != 0


def test_clone_liegt_im_arbeitsordner(container: str) -> None:
    assert _als_agent(container, f"git -C {KLON} rev-parse --is-inside-work-tree").stdout.strip() == "true"


def test_git_und_gh_holen_den_ausweis_beim_broker(container: str) -> None:
    assert _als_agent(container, "git config --get credential.helper").stdout.strip() == "broker"
    assert _als_agent(container, "command -v gh").stdout.strip() == "/usr/local/bin/gh"


@pytest.mark.parametrize(
    "befehl", ["python3 --version", "uv --version", "node --version", "pnpm --version", "just --version",
               "gh --version", "claude --version", "git --version"],
)  # fmt: skip
def test_werkzeuge_sind_da(container: str, befehl: str) -> None:
    ergebnis = _als_agent(container, befehl)
    assert ergebnis.returncode == 0, ergebnis.stderr


def test_claude_laeuft_ohne_rueckfragen(container: str) -> None:
    einstellungen = _als_agent(container, "cat ~/.claude/settings.json").stdout
    assert '"defaultMode": "bypassPermissions"' in einstellungen


@pytest.mark.parametrize(
    ("domains", "meldung"),
    [
        ("example.com", "Selbsttest fehlgeschlagen: example.com ist erreichbar"),
        ("gibt-es-nicht.invalid", "Domain ohne IPv4-Adresse: gibt-es-nicht.invalid"),
    ],
)
def test_kaputte_allowlist_startet_nicht(image: str, tmp_path: Path, domains: str, meldung: str) -> None:
    netz = tmp_path / "netz.env"
    netz.write_text(
        f'BROKER_PORT={KONFIG.broker_port}\nGITHUB_META="web api git"\nDOMAINS="{domains}"\n',
        encoding="utf-8",
        newline="\n",
    )
    name = _starten(image, f"--volume={netz}:/etc/harness/netz.env:ro")
    try:
        ende = time.monotonic() + 120
        while _docker("inspect", "--format", "{{.State.Running}}", name).stdout.strip() == "true":
            assert time.monotonic() < ende, "Container läuft trotz kaputter Allowlist"
            time.sleep(1)
        assert _docker("inspect", "--format", "{{.State.ExitCode}}", name).stdout.strip() != "0"
        log = _docker("logs", name)
        assert meldung in log.stdout + log.stderr
    finally:
        _docker("rm", "--force", name)


def test_neustart_setzt_die_firewall_wieder(image: str) -> None:
    name = _starten(image)
    try:
        CliDocker().warte_bereit(name, f"{KLON}/.git")
        assert _docker("restart", name).returncode == 0
        CliDocker().warte_bereit(name, f"{KLON}/.git")
        assert _als_agent(name, "curl -sS --max-time 5 https://example.com").returncode != 0
        assert _als_agent(name, "curl -fsS --max-time 10 https://api.github.com/zen").returncode == 0
    finally:
        _docker("rm", "--force", name)
