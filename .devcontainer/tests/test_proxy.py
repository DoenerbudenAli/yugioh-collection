"""Der Pförtner (Egress-Proxy) als Netzwerkdienst: Anfrage rein, Antwort und Weiterleitung beobachten.

Das Internet ist hier ein Test-Server auf 127.0.0.1. `oeffne` des Proxys wird darauf umgelenkt und merkt sich,
wohin der Proxy wollte.
"""

import asyncio
import contextlib
import ssl
import struct
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import pytest

from devcontainer.proxy import starte

ERLAUBT = ("pakete.example.org", "api.example.org")
OFFEN = b"HTTP/1.1 200 Connection established"


def _mit_laenge(daten: bytes, breite: int) -> bytes:
    return len(daten).to_bytes(breite, "big") + daten


def sni(name: str) -> tuple[int, bytes]:
    eintrag = b"\x00" + _mit_laenge(name.encode(), 2)
    return 0x0000, _mit_laenge(eintrag, 2)


def client_hello(*erweiterungen: tuple[int, bytes], anhang: bytes = b"") -> bytes:
    """Ein minimaler TLS-ClientHello als ein Record, mit den gegebenen Erweiterungen (Typ, Inhalt).

    `anhang` kommt roh hinter die Erweiterungen, etwa eine Erweiterung mit falscher Längenangabe.
    """
    exts = b"".join(struct.pack("!H", typ) + _mit_laenge(inhalt, 2) for typ, inhalt in erweiterungen) + anhang
    koerper = (
        b"\x03\x03" + bytes(32) + b"\x00" + _mit_laenge(b"\x13\x01", 2) + b"\x01\x00" + _mit_laenge(exts, 2)
    )
    handshake = b"\x01" + _mit_laenge(koerper, 3)
    return b"\x16\x03\x01" + _mit_laenge(handshake, 2)


def echter_client_hello(name: str | None) -> bytes:
    """Der ClientHello, den Pythons ssl wirklich schickt (mit großen Schlüsseln, wie curl oder Node)."""
    kontext = ssl.create_default_context()
    if name is None:
        kontext.check_hostname = False
    ein, aus = ssl.MemoryBIO(), ssl.MemoryBIO()
    tls = kontext.wrap_bio(ein, aus, server_hostname=name)
    with contextlib.suppress(ssl.SSLWantReadError):
        tls.do_handshake()
    return aus.read()


@dataclass
class Internet:
    """Ein Test-Server, der alles mitschreibt, was ankommt, und mit ANTWORT antwortet."""

    port: int = 0
    empfangen: bytearray = field(default_factory=bytearray)
    ziele: list[tuple[str, int]] = field(default_factory=list[tuple[str, int]])

    async def oeffne(self, host: str, port: int) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        self.ziele.append((host, port))
        return await asyncio.open_connection("127.0.0.1", self.port)


async def _mit_proxy(
    szenario: Callable[[asyncio.StreamReader, asyncio.StreamWriter, Internet], Awaitable[None]],
) -> Internet:
    internet = Internet()

    async def bediene(lesen: asyncio.StreamReader, schreiben: asyncio.StreamWriter) -> None:
        while daten := await lesen.read(65536):
            internet.empfangen.extend(daten)
            schreiben.write(b"ANTWORT")
            await schreiben.drain()
        schreiben.close()

    server = await asyncio.start_server(bediene, "127.0.0.1", 0)
    internet.port = server.sockets[0].getsockname()[1]
    proxy = await starte(ERLAUBT, port=0, oeffne=internet.oeffne, frist=1)
    lesen, schreiben = await asyncio.open_connection("127.0.0.1", proxy.sockets[0].getsockname()[1])
    try:
        await asyncio.wait_for(szenario(lesen, schreiben, internet), timeout=5)
    finally:
        schreiben.close()
        proxy.close()
        server.close()
    return internet


def laufe(
    szenario: Callable[[asyncio.StreamReader, asyncio.StreamWriter, Internet], Awaitable[None]],
) -> Internet:
    return asyncio.run(_mit_proxy(szenario))


async def connect(lesen: asyncio.StreamReader, schreiben: asyncio.StreamWriter, ziel: str) -> bytes:
    """Schickt CONNECT und gibt die Statuszeile der Antwort zurück."""
    schreiben.write(f"CONNECT {ziel} HTTP/1.1\r\nHost: {ziel}\r\n\r\n".encode())
    await schreiben.drain()
    kopf = await lesen.readuntil(b"\r\n\r\n")
    return kopf.split(b"\r\n", 1)[0]


def test_erlaubter_name_mit_passendem_sni_wird_durchgereicht() -> None:
    hallo = client_hello(sni("pakete.example.org"))

    async def szenario(lesen: asyncio.StreamReader, schreiben: asyncio.StreamWriter, _: Internet) -> None:
        assert await connect(lesen, schreiben, "pakete.example.org:443") == OFFEN
        schreiben.write(hallo)
        await schreiben.drain()
        assert await lesen.readexactly(7) == b"ANTWORT"

    internet = laufe(szenario)
    assert internet.ziele == [("pakete.example.org", 443)]
    assert bytes(internet.empfangen) == hallo


def test_name_ausserhalb_der_allowlist_wird_abgewiesen() -> None:
    async def szenario(lesen: asyncio.StreamReader, schreiben: asyncio.StreamWriter, _: Internet) -> None:
        assert await connect(lesen, schreiben, "boese.example.com:443") == b"HTTP/1.1 403 Forbidden"

    assert laufe(szenario).ziele == []


async def tunnel_wird_gekappt(
    lesen: asyncio.StreamReader, schreiben: asyncio.StreamWriter, hallo: bytes
) -> None:
    """Öffnet einen Tunnel zu einem erlaubten Namen, schickt `hallo` und erwartet, dass der Proxy auflegt."""
    assert await connect(lesen, schreiben, "pakete.example.org:443") == OFFEN
    schreiben.write(hallo)
    await schreiben.drain()
    assert await lesen.read() == b""


def test_fremder_name_im_sni_kappt_den_tunnel() -> None:
    # Der CDN-Trick: CONNECT zu einem erlaubten Namen, im TLS-Umschlag aber eine fremde Seite.
    async def szenario(lesen: asyncio.StreamReader, schreiben: asyncio.StreamWriter, _: Internet) -> None:
        await tunnel_wird_gekappt(lesen, schreiben, client_hello(sni("boese.example.com")))

    assert laufe(szenario).empfangen == b""


def test_verschluesselter_umschlag_ech_kappt_den_tunnel() -> None:
    # Mit ECH stünde der echte Name verschlüsselt im ClientHello; außen ein erlaubter Name wäre nur Tarnung.
    hallo = client_hello(sni("pakete.example.org"), (0xFE0D, b"\x00" * 40))

    async def szenario(lesen: asyncio.StreamReader, schreiben: asyncio.StreamWriter, _: Internet) -> None:
        await tunnel_wird_gekappt(lesen, schreiben, hallo)

    assert laufe(szenario).empfangen == b""


@pytest.mark.parametrize(
    "hallo",
    [
        pytest.param(echter_client_hello(None), id="ohne-sni"),
        pytest.param(b"GET / HTTP/1.1\r\nHost: boese.example.com\r\n\r\n", id="kein-tls"),
        pytest.param(client_hello(sni("pakete.example.org"))[:-3], id="abgeschnitten"),
        pytest.param(b"\x16\x03\x01\x00\x08\x01\x00\x00\x04\x03\x03\x00\x00", id="kaputt"),
    ],
)
def test_umschlag_ohne_lesbaren_namen_kappt_den_tunnel(hallo: bytes) -> None:
    async def szenario(lesen: asyncio.StreamReader, schreiben: asyncio.StreamWriter, _: Internet) -> None:
        await tunnel_wird_gekappt(lesen, schreiben, hallo)

    assert laufe(szenario).empfangen == b""


def _in_zwei_records(hallo: bytes) -> bytes:
    handshake = hallo[5:]
    mitte = len(handshake) // 2
    return b"".join(b"\x16\x03\x01" + _mit_laenge(teil, 2) for teil in (handshake[:mitte], handshake[mitte:]))


@pytest.mark.parametrize(
    "hallo",
    [
        pytest.param(echter_client_hello("pakete.example.org"), id="echter-client"),
        pytest.param(_in_zwei_records(echter_client_hello("pakete.example.org")), id="zwei-records"),
    ],
)
def test_echter_client_hello_kommt_auch_haeppchenweise_durch(hallo: bytes) -> None:
    async def szenario(lesen: asyncio.StreamReader, schreiben: asyncio.StreamWriter, _: Internet) -> None:
        assert await connect(lesen, schreiben, "pakete.example.org:443") == OFFEN
        for start in range(0, len(hallo), 100):
            schreiben.write(hallo[start : start + 100])
            await schreiben.drain()
            await asyncio.sleep(0)
        assert await lesen.readexactly(7) == b"ANTWORT"

    assert bytes(laufe(szenario).empfangen).startswith(hallo)


async def antwort_auf(lesen: asyncio.StreamReader, schreiben: asyncio.StreamWriter, anfrage: bytes) -> bytes:
    schreiben.write(anfrage)
    await schreiben.drain()
    return (await lesen.read()).split(b"\r\n", 1)[0]


@pytest.mark.parametrize(
    ("anfrage", "status"),
    [
        pytest.param(b"CONNECT pakete.example.org:22 HTTP/1.1\r\n\r\n", b"403", id="anderer-port"),
        pytest.param(b"CONNECT pakete.example.org HTTP/1.1\r\n\r\n", b"400", id="ohne-port"),
        pytest.param(b"GET http://pakete.example.org/ HTTP/1.1\r\n\r\n", b"405", id="unverschluesselt"),
        pytest.param(b"Unsinn\r\n\r\n", b"400", id="unsinn"),
    ],
)
def test_nur_connect_auf_port_443(anfrage: bytes, status: bytes) -> None:
    async def szenario(lesen: asyncio.StreamReader, schreiben: asyncio.StreamWriter, _: Internet) -> None:
        assert (await antwort_auf(lesen, schreiben, anfrage)).split(b" ")[1] == status

    assert laufe(szenario).ziele == []


def test_unerreichbares_ziel_meldet_502() -> None:
    async def szenario(
        lesen: asyncio.StreamReader, schreiben: asyncio.StreamWriter, internet: Internet
    ) -> None:
        internet.port = 1  # dort hört niemand zu
        anfrage = b"CONNECT pakete.example.org:443 HTTP/1.1\r\n\r\n"
        assert (await antwort_auf(lesen, schreiben, anfrage)).split(b" ")[1] == b"502"

    laufe(szenario)


def _zwei_namen_in_einer_liste() -> tuple[int, bytes]:
    eintraege = b"".join(b"\x00" + _mit_laenge(n, 2) for n in (b"pakete.example.org", b"boese.example.com"))
    return 0x0000, _mit_laenge(eintraege, 2)


@pytest.mark.parametrize(
    "hallo",
    [
        pytest.param(client_hello(sni("boese.example.com"), sni("pakete.example.org")), id="zwei-sni"),
        pytest.param(client_hello(_zwei_namen_in_einer_liste()), id="zwei-namen-in-einer-liste"),
        pytest.param(
            client_hello(sni("pakete.example.org"), anhang=b"\x00\x10\x00\x09\x00\x00"), id="laenge-falsch"
        ),
    ],
)
def test_mehrdeutiger_umschlag_kappt_den_tunnel(hallo: bytes) -> None:
    # Nähme der Server einen anderen Namen als der Proxy, wäre die Prüfung umgangen: nur Eindeutiges gilt.
    async def szenario(lesen: asyncio.StreamReader, schreiben: asyncio.StreamWriter, _: Internet) -> None:
        await tunnel_wird_gekappt(lesen, schreiben, hallo)

    assert laufe(szenario).empfangen == b""
