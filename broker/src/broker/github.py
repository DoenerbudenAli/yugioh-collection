"""Holt Installation-Tokens bei GitHub, unterschrieben mit dem Private Key der App."""

import json
import urllib.request
from collections.abc import Callable
from typing import Any

import jwt

from broker.konfig import Konfig


class GitHubApp:
    def __init__(self, konfig: Konfig, private_key_pem: bytes, uhr: Callable[[], float]) -> None:
        self._konfig = konfig
        self._key = private_key_pem
        self._uhr = uhr

    def _app_jwt(self) -> str:
        jetzt = int(self._uhr())
        # GitHub erlaubt höchstens 10 Minuten; iat leicht zurück gegen Uhrenabweichung.
        claims = {"iat": jetzt - 60, "exp": jetzt + 540, "iss": str(self._konfig.app_id)}
        return jwt.encode(claims, self._key, algorithm="RS256")

    def installation_token(self, rechte: dict[str, str]) -> dict[str, Any]:
        """Token nur für das eine Repo und nur mit den übergebenen Rechten."""
        url = f"{self._konfig.github_api}/app/installations/{self._konfig.installation_id}/access_tokens"
        if not url.startswith(("https://", "http://")):
            raise ValueError(f"github_api muss eine http(s)-URL sein: {url}")
        koerper = {"repositories": [self._konfig.repository], "permissions": rechte}
        anfrage = urllib.request.Request(  # noqa: S310 (Schema oben geprüft)
            url,
            data=json.dumps(koerper).encode(),
            headers={
                "Authorization": f"Bearer {self._app_jwt()}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(anfrage, timeout=30) as antwort:  # noqa: S310
            daten: dict[str, Any] = json.loads(antwort.read())
        return {"token": daten["token"], "expires_at": daten["expires_at"]}
