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
        f'BROKER_PORT={KONFIG.broker_port}\nDOMAINS="{domains}"\n',
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


# Egress-Proxy (Ticket #70): Nach außen darf nur der Proxy, und der nur zu Hostnamen der Allowlist.
PROXY_USER = "egress"  # eigener User des Proxys im Image, iptables lässt nur ihn hinaus
CDN_NAME = "registry.npmjs.org"  # liegt bei einem CDN, dessen IPs sich viele fremde Seiten teilen
CDN_IP = f"$(getent ahostsv4 {CDN_NAME} | awk 'NR==1 {{print $1}}')"


@pytest.mark.parametrize("ohne_proxy", ["", "--noproxy '*'"], ids=["mit-proxy", "ohne-proxy"])
def test_fremde_seite_ueber_cdn_ip_scheitert(container: str, ohne_proxy: str) -> None:
    befehl = f"curl -sS --max-time 10 {ohne_proxy} --resolve example.com:443:{CDN_IP} https://example.com"
    assert _als_agent(container, befehl).returncode != 0


# Öffnet einen Tunnel zu einem erlaubten Namen und spricht darin TLS mit dem Namen aus argv[1] (SNI).
SNI_PROBE = r"""
import os, socket, ssl, sys
port = os.environ["HTTPS_PROXY"].rsplit(":", 1)[1]
s = socket.create_connection(("127.0.0.1", int(port)), timeout=10)
s.sendall(b"CONNECT %s:443 HTTP/1.1

" % sys.argv[2].encode())
assert s.recv(4096).startswith(b"HTTP/1.1 200"), "Tunnel abgelehnt"
k = ssl.create_default_context(); k.check_hostname = False; k.verify_mode = ssl.CERT_NONE
k.wrap_socket(s, server_hostname=sys.argv[1]).close()
"""


def test_fremder_name_im_tunnel_zu_erlaubtem_namen_scheitert(container: str) -> None:
    probe = f"python3 -c '{SNI_PROBE}'"
    gegenprobe = _als_agent(container, f"{probe} {CDN_NAME} {CDN_NAME}")
    assert gegenprobe.returncode == 0, gegenprobe.stderr
    assert _als_agent(container, f"{probe} example.com {CDN_NAME}").returncode != 0


@pytest.mark.parametrize("ziel", [f"https://{CDN_NAME}", "https://github.com"])
def test_direkter_verkehr_am_proxy_vorbei_scheitert(container: str, ziel: str) -> None:
    assert _als_agent(container, f"curl -sS --max-time 10 --noproxy '*' {ziel}").returncode != 0


def test_proxy_weist_namen_ausserhalb_der_allowlist_ab(container: str) -> None:
    ergebnis = _als_agent(container, "curl -sS --max-time 10 https://example.com")
    assert ergebnis.returncode != 0
    assert "403" in ergebnis.stderr


def test_agent_kann_den_proxy_nicht_beenden(container: str) -> None:
    pids = _als_agent(container, f"pgrep -u {PROXY_USER} -f devcontainer.proxy").stdout.split()
    assert pids, f"kein Proxy-Prozess als {PROXY_USER}"
    versuch = _als_agent(container, f"kill {' '.join(pids)}")
    assert versuch.returncode != 0
    assert "Operation not permitted" in versuch.stderr
    assert (
        _als_agent(container, "curl -sS --max-time 10 -o /dev/null https://api.github.com/zen").returncode
        == 0
    )


@pytest.mark.parametrize(
    "befehl",
    [
        "cd $(mktemp -d) && uv init --bare --name probe && uv add iniconfig",
        "cd $(mktemp -d) && pnpm init && pnpm add is-number",
        "npm view is-number version",
        f"git ls-remote https://github.com/{KONFIG.repository}.git HEAD",
    ],
    ids=["uv", "pnpm", "npm", "git"],
)
def test_werkzeuge_erreichen_die_echten_quellen_ueber_den_proxy(container: str, befehl: str) -> None:
    ergebnis = _als_agent(container, befehl)
    assert ergebnis.returncode == 0, ergebnis.stderr


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
