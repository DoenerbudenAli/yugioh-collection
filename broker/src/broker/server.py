"""HTTP-Schnittstelle des Brokers.

- `POST /schluessel` (Admin): `{"schluessel", "rolle", "ablauf"}` meldet einen Schlüssel an.
- `POST /schluessel/abmelden` (Admin): `{"schluessel"}` meldet ihn ab.
- `POST /token` (Schlüssel als Bearer): `{"rolle"}` liefert ein Installation-Token dieser Rolle.
"""

import hmac
import json
import logging
import threading
import urllib.error
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import TracebackType
from typing import Any, cast

from broker.github import GitHubApp
from broker.konfig import Konfig

_log = logging.getLogger(__name__)

# Schlüssel erzeugt das Startskript zufällig. Kurze oder leere werden abgelehnt, damit eine Anfrage
# ohne Authorization-Header nie zu einer Anmeldung passt.
MINDESTLAENGE_SCHLUESSEL = 16


class Ungueltig(Exception):
    pass


def _text(daten: dict[str, Any], feld: str) -> str:
    wert = daten.get(feld)
    if not isinstance(wert, str):
        raise Ungueltig(f"Feld {feld!r} fehlt oder ist kein Text")
    return wert


def _schluessel(daten: dict[str, Any]) -> str:
    wert = _text(daten, "schluessel")
    if len(wert) < MINDESTLAENGE_SCHLUESSEL:
        raise Ungueltig(f"Schlüssel kürzer als {MINDESTLAENGE_SCHLUESSEL} Zeichen")
    return wert


class BrokerServer:
    def __init__(
        self,
        konfig: Konfig,
        private_key_pem: bytes,
        admin_geheimnis: str,
        uhr: Callable[[], float],
        adresse: tuple[str, int],
    ) -> None:
        self._konfig = konfig
        self._github = GitHubApp(konfig, private_key_pem, uhr)
        self._admin_geheimnis = admin_geheimnis
        self._uhr = uhr
        self._anmeldungen: dict[str, tuple[str, float]] = {}
        self._sperre = threading.Lock()
        self._http = ThreadingHTTPServer(adresse, self._handler_klasse())

    @property
    def url(self) -> str:
        host, port = self._http.server_address[:2]
        return f"http://{host}:{port}"

    def __enter__(self) -> "BrokerServer":
        threading.Thread(target=self._http.serve_forever, daemon=True).start()
        return self

    def __exit__(
        self, typ: type[BaseException] | None, wert: BaseException | None, tb: TracebackType | None
    ) -> None:
        self._http.shutdown()
        self._http.server_close()

    def serve_forever(self) -> None:
        self._http.serve_forever()

    def _ist_admin(self, bearer: str) -> bool:
        return hmac.compare_digest(bearer.encode(), self._admin_geheimnis.encode())

    def _bearbeiten(self, pfad: str, bearer: str, roh: Any) -> tuple[int, dict[str, Any]]:
        daten: dict[str, Any] = cast(dict[str, Any], roh) if isinstance(roh, dict) else {}
        if not isinstance(roh, dict):
            status, antwort = 400, {"fehler": "Körper ist kein JSON-Objekt"}
        else:
            try:
                status, antwort = self._entscheiden(pfad, bearer, daten)
            except Ungueltig as fehler:
                status, antwort = 400, {"fehler": str(fehler)}
        # Ins Log kommen nie Schlüssel oder Tokens, nur was passiert ist.
        rolle = daten.get("rolle", "-")
        _log.info("%s rolle=%s -> %s %s", pfad, rolle, status, antwort.get("fehler", ""))
        return status, antwort

    def _entscheiden(self, pfad: str, bearer: str, daten: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        if pfad.startswith("/schluessel") and not self._ist_admin(bearer):
            return 403, {"fehler": "Admin-Geheimnis fehlt oder ist falsch"}
        if pfad == "/schluessel":
            schluessel, rolle, ablauf = _schluessel(daten), _text(daten, "rolle"), daten.get("ablauf")
            if rolle not in self._konfig.rollen:
                return 400, {"fehler": "unbekannte Rolle"}
            if not isinstance(ablauf, int | float) or isinstance(ablauf, bool):
                return 400, {"fehler": "Feld 'ablauf' fehlt oder ist keine Zahl"}
            with self._sperre:
                self._anmeldungen[schluessel] = (rolle, float(ablauf))
            return 204, {}
        if pfad == "/schluessel/abmelden":
            schluessel = _text(daten, "schluessel")
            with self._sperre:
                self._anmeldungen.pop(schluessel, None)
            return 204, {}
        if pfad == "/token":
            with self._sperre:
                anmeldung = self._anmeldungen.get(bearer)
                if anmeldung is None:
                    return 403, {"fehler": "Schlüssel nicht angemeldet"}
                rolle, ablauf = anmeldung
                if self._uhr() >= ablauf:
                    del self._anmeldungen[bearer]
                    return 403, {"fehler": "Schlüssel abgelaufen"}
            if daten.get("rolle") != rolle:
                return 403, {"fehler": "fremde Rolle"}
            try:
                return 200, self._github.installation_token(self._konfig.rollen[rolle])
            except (urllib.error.URLError, OSError) as fehler:
                return 502, {"fehler": f"GitHub hat kein Token ausgestellt: {fehler}"}
        return 404, {"fehler": "unbekannter Pfad"}

    def _handler_klasse(self) -> type[BaseHTTPRequestHandler]:
        broker = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                laenge = int(self.headers.get("Content-Length", "0"))
                try:
                    daten: Any = json.loads(self.rfile.read(laenge) or b"{}")
                except ValueError:
                    daten = None
                bearer = self.headers.get("Authorization", "").removeprefix("Bearer ")
                status, antwort = broker._bearbeiten(self.path, bearer, daten)
                inhalt = json.dumps(antwort).encode() if antwort else b""
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(inhalt)))
                self.end_headers()
                self.wfile.write(inhalt)

            def log_message(self, format: str, *args: Any) -> None:
                pass

        return Handler
