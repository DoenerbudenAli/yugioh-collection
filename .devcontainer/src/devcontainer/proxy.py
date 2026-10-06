"""Egress-Proxy des Agenten-Containers (ADR 0005, „Netz“): lässt nur Hostnamen der Allowlist hinaus.

Werkzeuge im Container erreichen ihn per `HTTPS_PROXY` und öffnen einen Tunnel mit `CONNECT host:443`.
"""

import asyncio
import logging
import socket
import sys
from collections.abc import Awaitable, Callable, Iterable

# Ein ClientHello passt in einen Record (16 KiB); mehr lesen wir nicht, bevor der Name geprüft ist.
_GROESSTER_CLIENT_HELLO = 64 * 1024
# Erweiterungen, die den echten Namen verschlüsselt mitschicken: ECH und sein Vorläufer ESNI.
# Außen stünde dann nur ein Tarnname; ein CDN leitete nach dem inneren Namen weiter.
_VERSCHLUESSELTER_NAME = frozenset({0xFE0D, 0xFFCE})

_log = logging.getLogger("proxy")

type Oeffne = Callable[[str, int], Awaitable[tuple[asyncio.StreamReader, asyncio.StreamWriter]]]


async def _oeffne(host: str, port: int) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    # Nur IPv4: ip6tables verwirft allen Verkehr nach außen, ein IPv6-Versuch liefe erst in die Frist.
    return await asyncio.open_connection(host, port, family=socket.AF_INET)


class Abgelehnt(Exception):
    """Der Tunnel wird gekappt; der Text sagt warum."""


async def _lies_client_hello(lesen: asyncio.StreamReader) -> tuple[bytes, bytes]:
    """Liest TLS-Records bis zum ganzen ClientHello. Gibt die rohen Bytes und die Handshake-Nachricht."""
    roh = bytearray()
    handshake = bytearray()
    try:
        while len(handshake) < 4 or len(handshake) < 4 + int.from_bytes(handshake[1:4], "big"):
            kopf = await lesen.readexactly(5)
            if kopf[0] != 0x16:
                raise Abgelehnt("kein TLS")
            inhalt = await lesen.readexactly(int.from_bytes(kopf[3:5], "big"))
            roh += kopf + inhalt
            handshake += inhalt
            if len(roh) > _GROESSTER_CLIENT_HELLO:
                raise Abgelehnt("ClientHello zu groß")
    except asyncio.IncompleteReadError as fehler:
        raise Abgelehnt("ClientHello unvollständig") from fehler
    return bytes(roh), bytes(handshake)


def _sni(handshake: bytes) -> str:
    """Der Hostname aus der SNI-Erweiterung eines ClientHello."""
    try:
        return _sni_ungeprueft(handshake)
    except (IndexError, UnicodeDecodeError) as fehler:
        raise Abgelehnt("ClientHello kaputt") from fehler


def _sni_ungeprueft(handshake: bytes) -> str:
    # Streng: Jede Länge muss aufgehen, jede Erweiterung kommt höchstens einmal, genau ein Name. Was ein
    # Server anders deuten könnte als der Proxy (zwei Namen, Längen über das Ende hinaus), wird abgelehnt.
    if handshake[0] != 0x01:
        raise Abgelehnt("kein ClientHello")
    pos = 4 + 2 + 32
    pos += 1 + handshake[pos]  # session_id
    pos += 2 + int.from_bytes(handshake[pos : pos + 2], "big")  # cipher_suites
    pos += 1 + handshake[pos]  # compression_methods
    ende = pos + 2 + int.from_bytes(handshake[pos : pos + 2], "big")
    if ende != 4 + int.from_bytes(handshake[1:4], "big"):
        raise Abgelehnt("Länge der Erweiterungen passt nicht")
    pos += 2
    gesehen: set[int] = set()
    name = None
    while pos < ende:
        typ = int.from_bytes(handshake[pos : pos + 2], "big")
        laenge = int.from_bytes(handshake[pos + 2 : pos + 4], "big")
        inhalt = handshake[pos + 4 : pos + 4 + laenge]
        pos += 4 + laenge
        if pos > ende:
            raise Abgelehnt("Länge einer Erweiterung passt nicht")
        if typ in gesehen:
            raise Abgelehnt(f"Erweiterung {typ:#06x} doppelt")
        gesehen.add(typ)
        if typ in _VERSCHLUESSELTER_NAME:
            raise Abgelehnt("verschlüsselter ClientHello (ECH)")
        if typ == 0x0000:
            name = _name_aus_server_name_list(inhalt)
    if name is None:
        raise Abgelehnt("ohne SNI")
    return name


def _name_aus_server_name_list(inhalt: bytes) -> str:
    """Genau ein Eintrag vom Typ host_name (0), der die Liste ganz füllt (RFC 6066, Abschnitt 3)."""
    laenge_liste = int.from_bytes(inhalt[0:2], "big")
    laenge_name = int.from_bytes(inhalt[3:5], "big")
    if inhalt[2] != 0x00 or laenge_liste != len(inhalt) - 2 or laenge_name != laenge_liste - 3:
        raise Abgelehnt("SNI nicht eindeutig")
    return inhalt[5:].decode("ascii")


class Abgewiesen(Exception):
    """Die Anfrage wird mit einem HTTP-Status beantwortet, ein Tunnel entsteht nicht."""

    def __init__(self, status: int, text: str, grund: str) -> None:
        super().__init__(grund)
        self.antwort = f"HTTP/1.1 {status} {text}\r\n\r\n".encode()


def _ziel(kopf: bytes, namen: frozenset[str]) -> str:
    """Der erlaubte Hostname aus `CONNECT host:443 HTTP/1.1`."""
    teile = kopf.split(b"\r\n", 1)[0].decode("latin-1").split(" ")
    if len(teile) != 3 or not teile[2].startswith("HTTP/"):
        raise Abgewiesen(400, "Bad Request", "Anfrage unlesbar")
    methode, ziel, _ = teile
    if methode != "CONNECT":
        raise Abgewiesen(405, "Method Not Allowed", f"{methode} statt CONNECT")
    name, doppelpunkt, port = ziel.rpartition(":")
    if not doppelpunkt or not port.isdigit():
        raise Abgewiesen(400, "Bad Request", f"Ziel ohne Port: {ziel}")
    name = name.lower()
    if port != "443" or name not in namen:
        raise Abgewiesen(403, "Forbidden", f"nicht in der Allowlist: {ziel}")
    return name


async def _pumpe(lesen: asyncio.StreamReader, schreiben: asyncio.StreamWriter) -> None:
    """Kopiert eine Richtung des Tunnels; am Ende nur halb schließen, die Antwort darf noch kommen."""
    try:
        while daten := await lesen.read(65536):
            schreiben.write(daten)
            await schreiben.drain()
        if schreiben.can_write_eof():
            schreiben.write_eof()
    except OSError:
        pass


async def _tunnel(
    lesen: asyncio.StreamReader,
    schreiben: asyncio.StreamWriter,
    namen: frozenset[str],
    oeffne: Oeffne,
    frist: float,
) -> None:
    try:
        async with asyncio.timeout(frist):
            name = _ziel(await lesen.readuntil(b"\r\n\r\n"), namen)
            try:
                hin_lesen, hin_schreiben = await oeffne(name, 443)
            except OSError as fehler:
                raise Abgewiesen(502, "Bad Gateway", f"{name} nicht erreichbar: {fehler}") from fehler
    except Abgewiesen as abweisung:
        _log.warning("abgewiesen: %s", abweisung)
        schreiben.write(abweisung.antwort)
        await schreiben.drain()
        return
    except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, TimeoutError):
        return
    schreiben.write(b"HTTP/1.1 200 Connection established\r\n\r\n")
    await schreiben.drain()
    try:
        async with asyncio.timeout(frist):
            roh, handshake = await _lies_client_hello(lesen)
        sni = _sni(handshake).lower()
        if sni != name:
            raise Abgelehnt(f"SNI {sni} statt {name}")
    except (Abgelehnt, TimeoutError) as fehler:
        _log.warning("gekappt: %s: %s", name, str(fehler) or "ClientHello kam nicht")
        hin_schreiben.close()
        return
    _log.info("erlaubt: %s", name)
    hin_schreiben.write(roh)
    try:
        await asyncio.gather(_pumpe(lesen, hin_schreiben), _pumpe(hin_lesen, schreiben))
    finally:
        hin_schreiben.close()


async def starte(
    erlaubt: Iterable[str],
    host: str = "127.0.0.1",
    port: int = 3128,
    oeffne: Oeffne = _oeffne,
    frist: float = 10,
) -> asyncio.Server:
    """Startet den Proxy. Er lässt nur `CONNECT name:443` zu, wenn `name` erlaubt ist und der TLS-ClientHello
    im Tunnel denselben Namen (SNI) trägt."""
    namen = frozenset(n.lower() for n in erlaubt)

    async def bediene(lesen: asyncio.StreamReader, schreiben: asyncio.StreamWriter) -> None:
        try:
            await _tunnel(lesen, schreiben, namen, oeffne, frist)
        except OSError:
            pass
        finally:
            schreiben.close()

    return await asyncio.start_server(bediene, host, port)


async def _laufe(port: int, erlaubt: list[str]) -> None:
    server = await starte(erlaubt, port=port)
    _log.info("hört auf 127.0.0.1:%d, erlaubt: %s", port, " ".join(erlaubt))
    async with server:
        await server.serve_forever()


def main(argv: list[str]) -> int:
    match argv:
        case [port, *erlaubt] if port.isdigit() and erlaubt:
            logging.basicConfig(level=logging.INFO, format="proxy: %(message)s", stream=sys.stderr)
            asyncio.run(_laufe(int(port), erlaubt))
            return 0
        case _:
            sys.stderr.write("Aufruf: python -m devcontainer.proxy <port> <hostname>...\n")
            return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
