"""Negativproben am echten Image (ADR 0005, „Grenze“, „Netz“). Brauchen Docker und Netz.

Das Image kommt aus `HARNESS_TEST_IMAGE` (CI) oder wird hier als `harness-devcontainer:test` gebaut.
Lokal gebaute Images dienen nur diesen Tests, Sessions laufen immer aus GHCR.
"""

import json
import os
import re
import shutil
import subprocess
import time
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest

from devcontainer.agent import CliDocker
from devcontainer.konfig import Sammlung, lade_konfig

pytestmark = [
    pytest.mark.container,
    pytest.mark.skipif(shutil.which("docker") is None, reason="Docker fehlt"),
]

REPO_ROOT = Path(__file__).resolve().parents[2]
KONFIG = lade_konfig(REPO_ROOT / "harness.toml")
KLON = KONFIG.klon
BEREIT = "/run/harness/bereit"


def _docker(*argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *argv], capture_output=True, text=True, encoding="utf-8", errors="replace", check=False
    )


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
        "--add-host=host.docker.internal:host-gateway", "--tmpfs=/run/harness:uid=1000,gid=1000,mode=0700",
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
        CliDocker().warte_bereit(name, BEREIT)
        yield name
    finally:
        _docker("rm", "--force", name)


def _als_agent(container: str, befehl: str) -> subprocess.CompletedProcess[str]:
    return _docker("exec", "--user", "agent", container, "bash", "-lc", befehl)


def test_fremde_domain_ist_gesperrt(container: str) -> None:
    assert _als_agent(container, "curl -sS --max-time 5 https://example.com").returncode != 0


def test_github_ist_erreichbar(container: str) -> None:
    # Ohne -f: Jede HTTP-Antwort beweist die Verbindung, auch ein 403 wegen des anonymen Abfragelimits.
    ergebnis = _als_agent(container, "curl -sS --max-time 10 -o /dev/null https://api.github.com/zen")
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
    # Voller Pfad: In der Login-Shell fehlt /usr/sbin im PATH, ein „command not found“ bewiese nichts.
    versuch = _als_agent(container, "/usr/sbin/iptables -P OUTPUT ACCEPT")
    assert versuch.returncode != 0
    assert "Permission denied" in versuch.stderr
    assert _als_agent(container, "curl -sS --max-time 5 https://example.com").returncode != 0


def test_docker_exec_hat_keine_wirksamen_rechte(container: str) -> None:
    status = _als_agent(container, "grep -E '^(CapEff|NoNewPrivs)' /proc/self/status").stdout.split()
    assert status == ["CapEff:", "0000000000000000", "NoNewPrivs:", "1"]


def test_bereit_zeichen_liegt_auf_tmpfs(container: str) -> None:
    assert _als_agent(container, "stat -f -c %T /run/harness").stdout.strip() == "tmpfs"


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
        CliDocker().warte_bereit(name, BEREIT)
        assert _docker("restart", name).returncode == 0
        CliDocker().warte_bereit(name, BEREIT)
        assert _als_agent(name, "curl -sS --max-time 5 https://example.com").returncode != 0
        assert (
            _als_agent(name, "curl -sS --max-time 10 -o /dev/null https://api.github.com/zen").returncode == 0
        )
    finally:
        _docker("rm", "--force", name)


def test_claude_bietet_keinen_auto_mode_an(container: str) -> None:
    # Ohne diese Sperre fragt Claude beim ersten Start, ob Auto-Mode statt bypassPermissions Standard wird.
    einstellungen = _als_agent(container, "cat ~/.claude/settings.json").stdout
    assert '"disableAutoMode": "disable"' in einstellungen


# Fake für api.github.com/meta im Container: Status, Kopfzeilen und Körper kommen aus der Umgebung.
FAKE_META = r"""
import http.server, json, os
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(int(os.environ["FAKE_STATUS"]))
        for name, wert in json.loads(os.environ.get("FAKE_KOPF", "{}")).items():
            self.send_header(name, wert)
        self.end_headers()
        self.wfile.write(os.environ.get("FAKE_KOERPER", "").encode())
    def log_message(self, *a): pass
http.server.HTTPServer(("127.0.0.1", 8099), H).serve_forever()
"""


def _github_netze(image: str, schluessel: str, **fake: str) -> subprocess.CompletedProcess[str]:
    """Führt github-netze.sh im Image gegen den Fake aus (so wie beim Bauen, ohne Token)."""
    umgebung = [f"--env={name.upper()}={wert}" for name, wert in fake.items()]
    skript = (
        f"python3 -c '{FAKE_META}' & sleep 1; "
        f"HARNESS_GITHUB_META_URL=http://127.0.0.1:8099/meta /opt/harness/github-netze.sh {schluessel}"
    )
    return _docker("run", "--rm", *umgebung, "--entrypoint", "bash", image, "-c", skript)


def test_abfragelimit_von_github_wird_klar_gemeldet(image: str) -> None:
    ergebnis = _github_netze(
        image,
        "web",
        fake_status="403",
        fake_kopf='{"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1791289200"}',
    )
    assert ergebnis.returncode != 0
    assert "Abfragelimit" in ergebnis.stderr
    assert "1791289200" not in ergebnis.stderr


def test_github_netze_gibt_nur_ipv4_netze_der_schluessel_aus(image: str) -> None:
    ergebnis = _github_netze(
        image,
        "web git",
        fake_status="200",
        fake_koerper=json.dumps(
            {"web": ["192.0.2.0/24", "2001:db8::/32"], "git": ["198.51.100.0/24"], "actions": ["10.0.0.0/8"]}
        ),
    )
    assert ergebnis.returncode == 0, ergebnis.stderr
    assert ergebnis.stdout.split() == ["192.0.2.0/24", "198.51.100.0/24"]


def test_unbekannter_meta_schluessel_bricht_ab(image: str) -> None:
    ergebnis = _github_netze(
        image, "web gibtsnicht", fake_status="200", fake_koerper='{"web": ["192.0.2.0/24"]}'
    )
    assert ergebnis.returncode != 0
    assert "gibtsnicht" in ergebnis.stderr


def test_github_netze_liegen_im_image(image: str) -> None:
    netze = _docker(
        "run", "--rm", "--entrypoint", "cat", image, "/etc/harness/github-netze.txt"
    ).stdout.split()
    assert len(netze) > 5
    assert all("/" in n and ":" not in n for n in netze)


def test_start_braucht_keine_github_api(image: str) -> None:
    # api.github.com zeigt ins Leere: Fragte der Start die API, endete der Container mit Fehler.
    name = _starten(image, "--add-host=api.github.com:127.0.0.1")
    try:
        CliDocker().warte_bereit(name, BEREIT)
        assert _als_agent(name, "curl -sS --max-time 5 https://example.com").returncode != 0
    finally:
        _docker("rm", "--force", name)


def test_ohne_github_netze_startet_der_container_nicht(image: str, tmp_path: Path) -> None:
    leer = tmp_path / "github-netze.txt"
    leer.write_text("", encoding="utf-8")
    name = _starten(image, f"--volume={leer}:/etc/harness/github-netze.txt:ro")
    try:
        ende = time.monotonic() + 60
        while _docker("inspect", "--format", "{{.State.Running}}", name).stdout.strip() == "true":
            assert time.monotonic() < ende, "Container läuft ohne GitHub-Netze"
            time.sleep(1)
        log = _docker("logs", name)
        assert "keine GitHub-Netze" in log.stdout + log.stderr
    finally:
        _docker("rm", "--force", name)


def _skills_holen(image: str, zeile: str) -> subprocess.CompletedProcess[str]:
    """Führt skills-holen.sh im Image mit einer Zeile aus `skills-liste` aus (so wie beim Bauen)."""
    skript = f"echo '{zeile}' | /opt/harness/skills-holen.sh /tmp/skills"
    return _docker("run", "--rm", "--entrypoint", "bash", image, "-c", skript)


# Je Sammlung aus harness.toml; ohne Sammlung überspringt pytest diese Tests.
JE_SAMMLUNG = pytest.mark.parametrize("s", KONFIG.skills, ids=lambda s: s.plugin)


@JE_SAMMLUNG
def test_skill_version_die_es_nicht_gibt_bricht_den_bau_ab(image: str, s: Sammlung) -> None:
    ergebnis = _skills_holen(image, f"{s.plugin} {s.github} v0.0.0-gibtsnicht {s.commit}")
    assert ergebnis.returncode != 0
    assert f"Version v0.0.0-gibtsnicht gibt es in {s.github} nicht" in ergebnis.stderr


@JE_SAMMLUNG
def test_skill_tag_auf_anderem_commit_bricht_den_bau_ab(image: str, s: Sammlung) -> None:
    ergebnis = _skills_holen(image, f"{s.plugin} {s.github} {s.version} {'0' * 40}")
    assert ergebnis.returncode != 0
    assert f"{s.version} zeigt auf {s.commit}" in ergebnis.stderr


@JE_SAMMLUNG
def test_skill_sammlungen_sind_installiert_und_bringen_skills_mit(container: str, s: Sammlung) -> None:
    liste = _als_agent(container, "claude plugin list").stdout
    assert f"❯ {s.plugin}@" in liste
    assert "✔ enabled" in liste
    details = _als_agent(container, f"claude plugin details {s.plugin}").stdout
    assert re.search(r"Skills \([1-9]\d*\)", details), details


def test_claude_vertraut_dem_clone(container: str) -> None:
    daten = json.loads(_als_agent(container, "cat ~/.claude.json").stdout)
    assert daten["projects"][KLON]["hasTrustDialogAccepted"] is True
