"""Test-Helfer: ein Fake-GitHub, eine stellbare Uhr und ein HTTP-Client für den Broker."""

import dataclasses
import json
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from broker.konfig import lade_konfig
from broker.server import BrokerServer

APP_ID = 4711
INSTALLATION_ID = 815
ADMIN_GEHEIMNIS = "admin-geheimnis-fuer-tests"

KONFIG_TOML = f"""
[github_app]
slug = "beispiel-app"
app_id = {APP_ID}
installation_id = {INSTALLATION_ID}

[broker]
repository = "beispiel-repo"
port = 8790

[broker.rollen.planung]
issues = "write"
contents = "read"

[broker.rollen.bau]
contents = "write"
pull_requests = "write"
issues = "read"
"""


class Uhr:
    """Eine Uhr, die der Test vorstellen kann.

    Startet bei der echten Zeit, damit die JWT-Prüfung des Fake-GitHub passt.
    """

    def __init__(self) -> None:
        self.jetzt = time.time()

    def __call__(self) -> float:
        return self.jetzt

    def vorstellen(self, sekunden: float) -> None:
        self.jetzt += sekunden


@dataclass
class FakeGitHub:
    """Nachbau des Endpunkts für Installation-Tokens.

    Prüft die JWT-Unterschrift und merkt sich jede Anfrage.
    """

    public_key: Any
    anfragen: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])
    url: str = ""
    gesperrt: bool = False  # wie nach dem Kill-Switch „Installation sperren“

    def starten(self) -> ThreadingHTTPServer:
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                if fake.gesperrt:
                    self.send_response(403)
                    self.end_headers()
                    return
                erwartet = f"/app/installations/{INSTALLATION_ID}/access_tokens"
                auth = self.headers.get("Authorization", "")
                try:
                    claims = jwt.decode(auth.removeprefix("Bearer "), fake.public_key, algorithms=["RS256"])
                except jwt.InvalidTokenError:
                    self.send_response(401)
                    self.end_headers()
                    return
                if self.path != erwartet or claims.get("iss") != str(APP_ID):
                    self.send_response(404)
                    self.end_headers()
                    return
                laenge = int(self.headers.get("Content-Length", "0"))
                koerper = json.loads(self.rfile.read(laenge) or b"{}")
                fake.anfragen.append(koerper)
                antwort = json.dumps(
                    {"token": f"ghs_fake_{len(fake.anfragen)}", "expires_at": "2099-01-01T00:00:00Z"}
                ).encode()
                self.send_response(201)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(antwort)

            def log_message(self, format: str, *args: Any) -> None:
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{server.server_address[1]}"
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return server


@dataclass
class Antwort:
    status: int
    daten: dict[str, Any]


class BrokerClient:
    """Spricht den Broker so an, wie es das Startskript und der Container später tun."""

    def __init__(self, url: str) -> None:
        self.url = url

    def _senden(self, pfad: str, daten: dict[str, Any], bearer: str) -> Antwort:
        anfrage = urllib.request.Request(
            self.url + pfad,
            data=json.dumps(daten).encode(),
            headers={"Authorization": f"Bearer {bearer}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(anfrage) as r:
                inhalt = r.read()
                return Antwort(r.status, json.loads(inhalt) if inhalt else {})
        except urllib.error.HTTPError as fehler:
            inhalt = fehler.read()
            return Antwort(fehler.code, json.loads(inhalt) if inhalt else {})

    def anmelden(self, schluessel: str, rolle: str, ablauf: float, admin: str = ADMIN_GEHEIMNIS) -> Antwort:
        return self._senden(
            "/schluessel", {"schluessel": schluessel, "rolle": rolle, "ablauf": ablauf}, admin
        )

    def abmelden(self, schluessel: str, admin: str = ADMIN_GEHEIMNIS) -> Antwort:
        return self._senden("/schluessel/abmelden", {"schluessel": schluessel}, admin)

    def token(self, schluessel: str, rolle: str) -> Antwort:
        return self._senden("/token", {"rolle": rolle}, schluessel)


@pytest.fixture(scope="session")
def app_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def github(app_key: rsa.RSAPrivateKey) -> Iterator[FakeGitHub]:
    fake = FakeGitHub(public_key=app_key.public_key())
    server = fake.starten()
    yield fake
    server.shutdown()


@pytest.fixture
def uhr() -> Uhr:
    return Uhr()


@pytest.fixture
def broker(
    app_key: rsa.RSAPrivateKey, github: FakeGitHub, uhr: Uhr, tmp_path: Path
) -> Iterator[BrokerClient]:
    pfad = tmp_path / "harness.toml"
    pfad.write_text(KONFIG_TOML, encoding="utf-8")
    konfig = dataclasses.replace(lade_konfig(pfad), github_api=github.url)
    pem = app_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )
    with BrokerServer(konfig, pem, ADMIN_GEHEIMNIS, uhr, ("127.0.0.1", 0)) as server:
        yield BrokerClient(server.url)
