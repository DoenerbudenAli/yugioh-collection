"""Test-Helfer: ein Fake-Broker mit derselben Schnittstelle wie `broker/` und eine stellbare Uhr."""

import json
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest

START = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)


class Uhr:
    def __init__(self) -> None:
        self.jetzt = START

    def __call__(self) -> datetime:
        return self.jetzt

    def vorstellen(self, sekunden: float) -> None:
        self.jetzt += timedelta(seconds=sekunden)


@dataclass
class FakeBroker:
    """Antwortet wie der echte Broker; Status und Ablauf der Tokens sind stellbar."""

    url: str = ""
    status: dict[str, int] = field(default_factory=dict[str, int])
    token_gueltig: timedelta = timedelta(hours=1)
    uhr: Uhr = field(default_factory=Uhr)
    aufrufe: list[tuple[str, str, dict[str, Any]]] = field(
        default_factory=list[tuple[str, str, dict[str, Any]]]
    )

    def antwort(self, pfad: str, bearer: str, koerper: dict[str, Any]) -> tuple[int, dict[str, Any] | None]:
        self.aufrufe.append((pfad, bearer, koerper))
        if pfad == "/token":
            status = self.status.get(pfad, 200)
            if status != 200:
                return status, {"fehler": "abgelehnt"}
            ablauf = (self.uhr() + self.token_gueltig).strftime("%Y-%m-%dT%H:%M:%SZ")
            nummer = sum(1 for p, _, _ in self.aufrufe if p == "/token")
            return 200, {"token": f"tok-{nummer}", "expires_at": ablauf}
        status = self.status.get(pfad, 204)
        return status, None if status == 204 else {"fehler": "abgelehnt"}


@pytest.fixture
def uhr() -> Uhr:
    return Uhr()


@pytest.fixture
def broker(uhr: Uhr) -> Iterator[FakeBroker]:
    fake = FakeBroker(uhr=uhr)

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            laenge = int(self.headers.get("Content-Length", "0"))
            koerper = json.loads(self.rfile.read(laenge) or b"{}")
            bearer = self.headers.get("Authorization", "").removeprefix("Bearer ")
            status, antwort = fake.antwort(self.path, bearer, koerper)
            self.send_response(status)
            if antwort is None:
                self.end_headers()
                return
            daten = json.dumps(antwort).encode()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(daten)))
            self.end_headers()
            self.wfile.write(daten)

        def log_message(self, format: str, *args: Any) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    fake.url = f"http://127.0.0.1:{server.server_address[1]}"
    faden = threading.Thread(target=server.serve_forever, daemon=True)
    faden.start()
    yield fake
    server.shutdown()
    server.server_close()
