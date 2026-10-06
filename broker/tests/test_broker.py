"""Verhalten des Brokers an seiner HTTP-Schnittstelle (ADR 0005, „Broker“, „Rollenbindung“)."""

import urllib.error
import urllib.request

import pytest
from conftest import ADMIN_GEHEIMNIS, BrokerClient, FakeGitHub, Uhr

STUNDE = 3600


def test_angemeldeter_schluessel_bekommt_token_mit_den_rechten_seiner_rolle(
    broker: BrokerClient, github: FakeGitHub, uhr: Uhr
) -> None:
    assert broker.anmelden("schluessel-fuer-bau", "bau", uhr() + STUNDE).status == 204

    antwort = broker.token("schluessel-fuer-bau", "bau")

    assert antwort.status == 200
    assert antwort.daten["token"] == "ghs_fake_1"
    assert github.anfragen == [
        {
            "repositories": ["beispiel-repo"],
            "permissions": {"contents": "write", "pull_requests": "write", "issues": "read"},
        }
    ]


def test_unbekannter_schluessel_bekommt_kein_token(broker: BrokerClient, github: FakeGitHub) -> None:
    antwort = broker.token("niemals-angemeldet", "bau")

    assert antwort.status == 403
    assert github.anfragen == []


def test_schluessel_bekommt_kein_token_einer_fremden_rolle(
    broker: BrokerClient, github: FakeGitHub, uhr: Uhr
) -> None:
    broker.anmelden("schluessel-planung", "planung", uhr() + STUNDE)

    antwort = broker.token("schluessel-planung", "bau")

    assert antwort.status == 403
    assert github.anfragen == []


def test_abgemeldeter_schluessel_bekommt_kein_token(
    broker: BrokerClient, github: FakeGitHub, uhr: Uhr
) -> None:
    broker.anmelden("schluessel-fuer-bau", "bau", uhr() + STUNDE)

    assert broker.abmelden("schluessel-fuer-bau").status == 204
    antwort = broker.token("schluessel-fuer-bau", "bau")

    assert antwort.status == 403
    assert github.anfragen == []


def test_abgelaufener_schluessel_bekommt_kein_token(
    broker: BrokerClient, github: FakeGitHub, uhr: Uhr
) -> None:
    broker.anmelden("schluessel-fuer-bau", "bau", uhr() + STUNDE)

    uhr.vorstellen(STUNDE + 1)
    antwort = broker.token("schluessel-fuer-bau", "bau")

    assert antwort.status == 403
    assert github.anfragen == []


def test_anmelden_ohne_admin_geheimnis_wird_abgelehnt(
    broker: BrokerClient, github: FakeGitHub, uhr: Uhr
) -> None:
    antwort = broker.anmelden("selbst-ernannter-schluessel", "bau", uhr() + STUNDE, admin="geraten")

    assert antwort.status == 403
    assert broker.token("selbst-ernannter-schluessel", "bau").status == 403
    assert github.anfragen == []


def test_abmelden_ohne_admin_geheimnis_wird_abgelehnt(broker: BrokerClient, uhr: Uhr) -> None:
    broker.anmelden("schluessel-fuer-bau", "bau", uhr() + STUNDE)

    assert broker.abmelden("schluessel-fuer-bau", admin="geraten").status == 403
    assert broker.token("schluessel-fuer-bau", "bau").status == 200


def test_anmelden_mit_unbekannter_rolle_wird_abgelehnt(broker: BrokerClient, uhr: Uhr) -> None:
    assert broker.anmelden("schluessel-mit-rolle-admin", "admin", uhr() + STUNDE).status == 400
    assert broker.token("schluessel-mit-rolle-admin", "admin").status == 403


def test_planung_bekommt_issues_schreibend_und_code_nur_lesend(
    broker: BrokerClient, github: FakeGitHub, uhr: Uhr
) -> None:
    broker.anmelden("schluessel-planung", "planung", uhr() + STUNDE)

    assert broker.token("schluessel-planung", "planung").status == 200
    assert github.anfragen == [
        {"repositories": ["beispiel-repo"], "permissions": {"issues": "write", "contents": "read"}}
    ]


def test_lehnt_github_ab_meldet_der_broker_502(broker: BrokerClient, github: FakeGitHub, uhr: Uhr) -> None:
    broker.anmelden("schluessel-fuer-bau", "bau", uhr() + STUNDE)
    github.gesperrt = True

    antwort = broker.token("schluessel-fuer-bau", "bau")

    assert antwort.status == 502
    assert "token" not in antwort.daten


@pytest.mark.parametrize("schluessel", ["", "zu-kurz", 12345678901234567])
def test_anmelden_mit_leerem_kurzem_oder_falschem_schluessel_wird_abgelehnt(
    broker: BrokerClient, uhr: Uhr, schluessel: object
) -> None:
    assert broker.anmelden(schluessel, "bau", uhr() + STUNDE).status == 400  # type: ignore[arg-type]


def test_anfrage_ohne_schluessel_bekommt_kein_token(broker: BrokerClient, uhr: Uhr) -> None:
    broker.anmelden("", "bau", uhr() + STUNDE)

    assert broker.token("", "bau").status == 403


@pytest.mark.parametrize("koerper", [b"kein json", b"[1, 2]", b'{"rolle": "bau"}'])
def test_kaputte_anmeldung_wird_mit_400_beantwortet(broker: BrokerClient, koerper: bytes) -> None:
    anfrage = urllib.request.Request(
        broker.url + "/schluessel",
        data=koerper,
        headers={"Authorization": f"Bearer {ADMIN_GEHEIMNIS}"},
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as fehler:
        urllib.request.urlopen(anfrage)

    assert fehler.value.code == 400
