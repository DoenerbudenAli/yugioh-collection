from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from conftest import FakeBroker
from test_konfig import BEISPIEL_TOML

from devcontainer.agent import (
    AgentFehler,
    BrokerAdmin,
    CliDocker,
    Umgebung,
    Zustand,
    abmelden,
    main,
    start,
    weg,
)
from devcontainer.konfig import lade_konfig

JETZT = 1_800_000_000.0
TOKEN = "sk-ant-oat-geheim"
ADMIN = "admin-geheimnis"


@dataclass
class FakeDocker:
    zustaende: dict[str, Zustand] = field(default_factory=dict[str, Zustand])
    envs: dict[str, dict[str, str]] = field(default_factory=dict[str, dict[str, str]])
    aufrufe: list[tuple[Any, ...]] = field(default_factory=list[tuple[Any, ...]])

    def zustand(self, name: str) -> Zustand:
        return self.zustaende.get(name, "fehlt")

    def env_von(self, name: str) -> dict[str, str]:
        return self.envs[name]

    def pull(self, image: str) -> None:
        self.aufrufe.append(("pull", image))

    def volume_anlegen(self, name: str) -> None:
        self.aufrufe.append(("volume_anlegen", name))

    def run(self, name: str, image: str, env: Mapping[str, str]) -> None:
        self.aufrufe.append(("run", name, image, dict(env)))

    def start(self, name: str) -> None:
        self.aufrufe.append(("start", name))

    def warte_bereit(self, name: str, pfad: str) -> None:
        self.aufrufe.append(("warte_bereit", name, pfad))

    def exec_claude(self, name: str, arbeitsordner: str, token: str) -> int:
        self.aufrufe.append(("exec_claude", name, arbeitsordner, token))
        return 0

    def entfernen(self, name: str) -> None:
        self.aufrufe.append(("entfernen", name))

    def namen(self) -> list[str]:
        return [a[0] for a in self.aufrufe]


@pytest.fixture
def docker() -> FakeDocker:
    return FakeDocker()


@pytest.fixture
def umgebung(tmp_path: Path, broker: FakeBroker, docker: FakeDocker) -> Umgebung:
    toml = tmp_path / "harness.toml"
    toml.write_text(BEISPIEL_TOML, encoding="utf-8")
    token_datei = tmp_path / "claude-setup-token"
    token_datei.write_text(f"{TOKEN}\n", encoding="utf-8")
    return Umgebung(
        konfig=lade_konfig(toml),
        docker=docker,
        broker=BrokerAdmin(broker.url, ADMIN),
        setup_token_datei=token_datei,
        jetzt=lambda: JETZT,
        ausgabe=lambda _: None,
    )


def _container_env(schluessel: str = "k" * 43, rolle: str = "bau") -> dict[str, str]:
    return {"HARNESS_SCHLUESSEL": schluessel, "HARNESS_ROLLE": rolle, "PATH": "/usr/bin"}


def test_neu_meldet_an_und_startet_den_container(
    umgebung: Umgebung, broker: FakeBroker, docker: FakeDocker
) -> None:
    assert start(umgebung, "bau", "probe") == 0

    pfad, bearer, koerper = broker.aufrufe[0]
    assert (pfad, bearer) == ("/schluessel", ADMIN)
    assert koerper["rolle"] == "bau"
    assert koerper["ablauf"] == JETZT + 86400
    schluessel = koerper["schluessel"]
    assert len(schluessel) >= 32

    assert docker.namen() == ["pull", "volume_anlegen", "run", "warte_bereit", "exec_claude"]
    _, name, image, env = docker.aufrufe[2]
    assert (name, image) == ("agent-probe", "ghcr.io/beispiel/repo/devcontainer")
    assert env == {
        "HARNESS_SCHLUESSEL": schluessel,
        "HARNESS_ROLLE": "bau",
        "HARNESS_BROKER_URL": "http://host.docker.internal:8790",
        "HARNESS_REPOSITORY": "Beispiel/Repo",
        "GIT_AUTHOR_NAME": "beispiel-app[bot]",
        "GIT_COMMITTER_NAME": "beispiel-app[bot]",
        "GIT_AUTHOR_EMAIL": "42+beispiel-app[bot]@users.noreply.github.com",
        "GIT_COMMITTER_EMAIL": "42+beispiel-app[bot]@users.noreply.github.com",
    }
    assert docker.aufrufe[3] == ("warte_bereit", "agent-probe", "/run/harness/bereit")
    assert docker.aufrufe[4] == ("exec_claude", "agent-probe", "/arbeit/Repo", TOKEN)


def test_schluessel_ist_je_container_verschieden(umgebung: Umgebung, broker: FakeBroker) -> None:
    start(umgebung, "bau", "eins")
    start(umgebung, "bau", "zwei")
    assert broker.aufrufe[0][2]["schluessel"] != broker.aufrufe[1][2]["schluessel"]


def test_gestoppter_container_wird_mit_demselben_schluessel_neu_angemeldet(
    umgebung: Umgebung, broker: FakeBroker, docker: FakeDocker
) -> None:
    docker.zustaende["agent-probe"] = "gestoppt"
    docker.envs["agent-probe"] = _container_env("alt" * 11)

    assert start(umgebung, "bau", "probe") == 0

    assert broker.aufrufe[0][2] == {"schluessel": "alt" * 11, "rolle": "bau", "ablauf": JETZT + 86400}
    assert docker.namen() == ["start", "warte_bereit", "exec_claude"]


def test_laufender_container_wird_nur_neu_angemeldet(
    umgebung: Umgebung, broker: FakeBroker, docker: FakeDocker
) -> None:
    docker.zustaende["agent-probe"] = "laeuft"
    docker.envs["agent-probe"] = _container_env()

    start(umgebung, "bau", "probe")

    assert [a[0] for a in broker.aufrufe] == ["/schluessel"]
    assert docker.namen() == ["warte_bereit", "exec_claude"]


def test_vorhandener_container_mit_anderer_rolle_bricht_ab(
    umgebung: Umgebung, broker: FakeBroker, docker: FakeDocker
) -> None:
    docker.zustaende["agent-probe"] = "laeuft"
    docker.envs["agent-probe"] = _container_env(rolle="planung")

    with pytest.raises(AgentFehler, match="planung"):
        start(umgebung, "bau", "probe")
    assert broker.aufrufe == []


def test_unbekannte_rolle_bricht_vor_docker_ab(
    umgebung: Umgebung, broker: FakeBroker, docker: FakeDocker
) -> None:
    with pytest.raises(AgentFehler, match="Rolle"):
        start(umgebung, "admin", "probe")
    assert docker.aufrufe == []
    assert broker.aufrufe == []


@pytest.mark.parametrize("name", ["", "Gross", "mit leer", "a/b", "-x"])
def test_ungueltiger_name_bricht_ab(umgebung: Umgebung, docker: FakeDocker, name: str) -> None:
    with pytest.raises(AgentFehler, match="Name"):
        start(umgebung, "bau", name)
    assert docker.aufrufe == []


def test_fehlende_setup_token_datei_bricht_vor_der_anmeldung_ab(
    umgebung: Umgebung, broker: FakeBroker, docker: FakeDocker
) -> None:
    umgebung.setup_token_datei.unlink()
    with pytest.raises(AgentFehler, match="claude-setup-token"):
        start(umgebung, "bau", "probe")
    assert broker.aufrufe == []
    assert docker.aufrufe == []


@pytest.mark.parametrize("status", [400, 403])
def test_absage_des_brokers_bricht_vor_dem_start_ab(
    umgebung: Umgebung, broker: FakeBroker, docker: FakeDocker, status: int
) -> None:
    broker.status["/schluessel"] = status
    with pytest.raises(AgentFehler, match="Broker"):
        start(umgebung, "bau", "probe")
    assert docker.aufrufe == []


def test_broker_nicht_erreichbar_bricht_vor_dem_start_ab(umgebung: Umgebung, docker: FakeDocker) -> None:
    umgebung.broker = BrokerAdmin("http://127.0.0.1:9", ADMIN)
    with pytest.raises(AgentFehler, match="Broker"):
        start(umgebung, "bau", "probe")
    assert docker.aufrufe == []


def test_weg_meldet_ab_und_entfernt(umgebung: Umgebung, broker: FakeBroker, docker: FakeDocker) -> None:
    docker.zustaende["agent-probe"] = "laeuft"
    docker.envs["agent-probe"] = _container_env("weg" * 11)

    assert weg(umgebung, "probe") == 0

    assert broker.aufrufe == [("/schluessel/abmelden", ADMIN, {"schluessel": "weg" * 11})]
    assert docker.aufrufe == [("entfernen", "agent-probe")]


def test_weg_entfernt_auch_ohne_broker(umgebung: Umgebung, docker: FakeDocker) -> None:
    docker.zustaende["agent-probe"] = "gestoppt"
    docker.envs["agent-probe"] = _container_env()
    umgebung.broker = BrokerAdmin("http://127.0.0.1:9", ADMIN)
    meldungen: list[str] = []
    umgebung.ausgabe = meldungen.append

    assert weg(umgebung, "probe") == 0

    assert docker.aufrufe == [("entfernen", "agent-probe")]
    assert any("Broker" in m for m in meldungen)


def test_weg_ohne_container_raeumt_das_volume_trotzdem_auf(
    umgebung: Umgebung, broker: FakeBroker, docker: FakeDocker
) -> None:
    assert weg(umgebung, "probe") == 0
    assert broker.aufrufe == []
    assert docker.aufrufe == [("entfernen", "agent-probe")]


def test_abmelden_laesst_den_container_stehen(
    umgebung: Umgebung, broker: FakeBroker, docker: FakeDocker
) -> None:
    docker.zustaende["agent-probe"] = "laeuft"
    docker.envs["agent-probe"] = _container_env("ab" * 16)

    assert abmelden(umgebung, "probe") == 0

    assert broker.aufrufe == [("/schluessel/abmelden", ADMIN, {"schluessel": "ab" * 16})]
    assert docker.aufrufe == []


def test_abmelden_ohne_container_bricht_ab(umgebung: Umgebung) -> None:
    with pytest.raises(AgentFehler, match="agent-probe"):
        abmelden(umgebung, "probe")


# --- echte Docker-Befehle, mit aufgezeichnetem Aufruf statt Docker ---


@dataclass
class Aufruf:
    argv: list[str]
    env: dict[str, str] | None
    interaktiv: bool


@dataclass
class FakeAusfuehren:
    stdout: str = ""
    returncode: int = 0
    stderr: str = ""
    aufrufe: list[Aufruf] = field(default_factory=list[Aufruf])

    def __call__(
        self, argv: Sequence[str], env: Mapping[str, str] | None = None, interaktiv: bool = False
    ) -> tuple[int, str, str]:
        self.aufrufe.append(Aufruf(list(argv), dict(env) if env is not None else None, interaktiv))
        return self.returncode, self.stdout, self.stderr


def test_run_gibt_geheimnisse_nur_ueber_die_umgebung_weiter() -> None:
    ausfuehren = FakeAusfuehren()
    CliDocker(ausfuehren).run("agent-probe", "img", {"HARNESS_SCHLUESSEL": "geheim-schluessel"})

    aufruf = ausfuehren.aufrufe[0]
    assert aufruf.argv[:3] == ["docker", "run", "-d"]
    for teil in ("--cap-add=NET_ADMIN", "--cap-add=NET_RAW", "--security-opt=no-new-privileges"):
        assert teil in aufruf.argv
    assert "--volume=agent-probe:/arbeit" in aufruf.argv
    # Bereit-Zeichen auf tmpfs: Nach einem Neustart ist es weg, bis Firewall und Clone wieder stehen.
    assert "--tmpfs=/run/harness:uid=1000,gid=1000,mode=0700" in aufruf.argv
    assert aufruf.argv[-1] == "img"
    assert not any("geheim-schluessel" in a for a in aufruf.argv)
    assert aufruf.argv[aufruf.argv.index("--env") :][:2] == ["--env", "HARNESS_SCHLUESSEL"]
    assert aufruf.env is not None
    assert aufruf.env["HARNESS_SCHLUESSEL"] == "geheim-schluessel"


def test_exec_claude_gibt_das_token_nur_ueber_die_umgebung_weiter() -> None:
    ausfuehren = FakeAusfuehren()
    CliDocker(ausfuehren).exec_claude("agent-probe", "/arbeit/Repo", TOKEN)

    aufruf = ausfuehren.aufrufe[0]
    assert aufruf.interaktiv
    assert aufruf.argv == [
        "docker", "exec", "-it", "--user", "agent", "--workdir", "/arbeit/Repo",
        "--env", "CLAUDE_CODE_OAUTH_TOKEN", "agent-probe", "claude",
    ]  # fmt: skip
    assert aufruf.env is not None
    assert aufruf.env["CLAUDE_CODE_OAUTH_TOKEN"] == TOKEN


@pytest.mark.parametrize(
    ("returncode", "stdout", "stderr", "erwartet"),
    [
        (1, "", "Error response from daemon: No such container: agent-probe", "fehlt"),
        (0, "true\n", "", "laeuft"),
        (0, "false\n", "", "gestoppt"),
    ],
)
def test_zustand_aus_docker_inspect(returncode: int, stdout: str, stderr: str, erwartet: Zustand) -> None:
    ausfuehren = FakeAusfuehren(stdout, returncode, stderr)
    assert CliDocker(ausfuehren).zustand("agent-probe") == erwartet
    # Nur Container: Das gleichnamige Volume agent-<name> darf nicht als Treffer zählen.
    assert ausfuehren.aufrufe[0].argv[:3] == ["docker", "container", "inspect"]


def test_zustand_bei_nicht_laufendem_docker_ist_ein_fehler() -> None:
    ausfuehren = FakeAusfuehren("", 1, "error during connect: Docker Desktop is not running")
    with pytest.raises(AgentFehler, match="Docker Desktop is not running"):
        CliDocker(ausfuehren).zustand("agent-probe")


@pytest.mark.parametrize(
    "stderr",
    ["Error response from daemon: No such container: agent-probe", "Error: No such volume: agent-probe"],
)
def test_entfernen_toleriert_fehlende_objekte(stderr: str) -> None:
    CliDocker(FakeAusfuehren("", 1, stderr)).entfernen("agent-probe")


def test_entfernen_meldet_andere_docker_fehler() -> None:
    with pytest.raises(AgentFehler, match="error during connect"):
        CliDocker(FakeAusfuehren("", 1, "error during connect: pipe not found")).entfernen("agent-probe")


def test_fehlermeldung_enthaelt_die_ausgabe_von_docker() -> None:
    ausfuehren = FakeAusfuehren("", 125, 'Conflict. The container name "/agent-probe" is already in use')
    with pytest.raises(AgentFehler, match="already in use"):
        CliDocker(ausfuehren).run("agent-probe", "img", {})


def test_pull_zeigt_den_fortschritt() -> None:
    ausfuehren = FakeAusfuehren()
    CliDocker(ausfuehren).pull("img")
    assert ausfuehren.aufrufe[0].argv == ["docker", "pull", "img"]
    assert ausfuehren.aufrufe[0].interaktiv


def test_env_von_liest_die_container_umgebung() -> None:
    ausfuehren = FakeAusfuehren('["HARNESS_SCHLUESSEL=a=b", "HARNESS_ROLLE=bau"]\n')
    assert CliDocker(ausfuehren).env_von("agent-probe") == {
        "HARNESS_SCHLUESSEL": "a=b",
        "HARNESS_ROLLE": "bau",
    }


# --- main: Abbrüche vor jedem Docker-Aufruf ---


@pytest.fixture
def kein_docker(monkeypatch: pytest.MonkeyPatch) -> None:
    def verboten(*args: object, **kwargs: object) -> None:
        raise AssertionError("docker darf nicht aufgerufen werden")

    monkeypatch.setattr("devcontainer.agent.subprocess.run", verboten)


def test_main_ohne_admin_geheimnis_bricht_vor_docker_ab(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], kein_docker: None
) -> None:
    toml = tmp_path / "harness.toml"
    toml.write_text(BEISPIEL_TOML, encoding="utf-8")
    monkeypatch.setenv("HARNESS_ADMIN_GEHEIMNIS", str(tmp_path / "fehlt"))

    assert main(["start", "bau", "probe"], toml) == 1
    assert "Admin-Geheimnis" in capsys.readouterr().err


@pytest.mark.parametrize("inhalt", ["kein toml [", "[github_app]\nslug = 1\n"])
def test_main_mit_kaputter_harness_toml_meldet_einen_fehler(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], kein_docker: None, inhalt: str
) -> None:
    toml = tmp_path / "harness.toml"
    toml.write_text(inhalt, encoding="utf-8")

    assert main(["weg", "probe"], toml) == 1
    assert "harness.toml" in capsys.readouterr().err
