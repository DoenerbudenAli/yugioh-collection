import io
import os
import stat
from pathlib import Path

import pytest
from conftest import FakeBroker, Uhr

from devcontainer.ausweis import AusweisFehler, hole_token, main

SCHLUESSEL = "s" * 32


def test_erster_aufruf_fragt_den_broker_mit_schluessel_und_rolle(
    broker: FakeBroker, uhr: Uhr, tmp_path: Path
) -> None:
    token = hole_token(broker.url, SCHLUESSEL, "bau", tmp_path / "token.json", uhr)
    assert token == "tok-1"
    assert broker.aufrufe == [("/token", SCHLUESSEL, {"rolle": "bau"})]


def test_zweiter_aufruf_nutzt_den_cache(broker: FakeBroker, uhr: Uhr, tmp_path: Path) -> None:
    cache = tmp_path / "token.json"
    hole_token(broker.url, SCHLUESSEL, "bau", cache, uhr)
    uhr.vorstellen(3600 - 301)
    assert hole_token(broker.url, SCHLUESSEL, "bau", cache, uhr) == "tok-1"
    assert len(broker.aufrufe) == 1


def test_fast_abgelaufenes_token_wird_neu_geholt(broker: FakeBroker, uhr: Uhr, tmp_path: Path) -> None:
    cache = tmp_path / "token.json"
    hole_token(broker.url, SCHLUESSEL, "bau", cache, uhr)
    uhr.vorstellen(3600 - 299)
    assert hole_token(broker.url, SCHLUESSEL, "bau", cache, uhr) == "tok-2"
    assert len(broker.aufrufe) == 2


@pytest.mark.skipif(os.name != "posix", reason="Dateirechte nur unter POSIX")
def test_cache_datei_gehoert_nur_dem_besitzer(broker: FakeBroker, uhr: Uhr, tmp_path: Path) -> None:
    cache = tmp_path / "harness" / "token.json"
    hole_token(broker.url, SCHLUESSEL, "bau", cache, uhr)
    assert stat.S_IMODE(cache.stat().st_mode) == 0o600


def test_absage_wirft_fehler_und_legt_keinen_cache_an(broker: FakeBroker, uhr: Uhr, tmp_path: Path) -> None:
    broker.status["/token"] = 403
    cache = tmp_path / "token.json"
    with pytest.raises(AusweisFehler, match="403"):
        hole_token(broker.url, SCHLUESSEL, "bau", cache, uhr)
    assert not cache.exists()


def test_broker_nicht_erreichbar_wirft_fehler(uhr: Uhr, tmp_path: Path) -> None:
    with pytest.raises(AusweisFehler, match="Broker"):
        hole_token("http://127.0.0.1:9", SCHLUESSEL, "bau", tmp_path / "token.json", uhr)


def _cli(broker: FakeBroker, uhr: Uhr, tmp_path: Path, argv: list[str], eingabe: str = "") -> tuple[int, str]:
    env = {
        "HARNESS_BROKER_URL": broker.url,
        "HARNESS_SCHLUESSEL": SCHLUESSEL,
        "HARNESS_ROLLE": "bau",
        "XDG_CACHE_HOME": str(tmp_path),
    }
    aus = io.StringIO()
    code = main(argv, env, io.StringIO(eingabe), aus, uhr)
    return code, aus.getvalue()


def test_cli_token_gibt_das_token_aus(broker: FakeBroker, uhr: Uhr, tmp_path: Path) -> None:
    assert _cli(broker, uhr, tmp_path, ["token"]) == (0, "tok-1\n")
    assert (tmp_path / "harness" / "token.json").exists()


def test_git_credential_antwortet_fuer_github(broker: FakeBroker, uhr: Uhr, tmp_path: Path) -> None:
    code, aus = _cli(broker, uhr, tmp_path, ["git-credential", "get"], "protocol=https\nhost=github.com\n\n")
    assert code == 0
    assert aus == "username=x-access-token\npassword=tok-1\n"


def test_git_credential_schweigt_fuer_andere_hosts(broker: FakeBroker, uhr: Uhr, tmp_path: Path) -> None:
    code, aus = _cli(
        broker, uhr, tmp_path, ["git-credential", "get"], "protocol=https\nhost=gist.github.com\n\n"
    )
    assert (code, aus) == (0, "")
    assert broker.aufrufe == []


def test_git_credential_bei_absage_ohne_passwort(broker: FakeBroker, uhr: Uhr, tmp_path: Path) -> None:
    broker.status["/token"] = 403
    code, aus = _cli(broker, uhr, tmp_path, ["git-credential", "get"], "protocol=https\nhost=github.com\n\n")
    assert code == 1
    assert "password=" not in aus


def test_git_credential_store_und_erase_tun_nichts(broker: FakeBroker, uhr: Uhr, tmp_path: Path) -> None:
    for aktion in ("store", "erase"):
        assert _cli(broker, uhr, tmp_path, ["git-credential", aktion], "host=github.com\n\n") == (0, "")
    assert broker.aufrufe == []
