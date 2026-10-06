"""Befehle des Brokers. Siehe README.md für Einrichtung, Betrieb und Kill-Switch."""

import argparse
import base64
import hashlib
import logging
import secrets
import sys
import time
from pathlib import Path

from cryptography.hazmat.primitives import serialization

from broker.konfig import lade_konfig
from broker.server import BrokerServer
from broker.tresor import TresorFehler, entschluesseln, verschluesseln

KEY_DATEI = "app-key.dpapi"
ADMIN_DATEI = "admin-geheimnis"
LOG_DATEI = "broker.log"


def _fingerabdruck(pem: bytes) -> str:
    """SHA256 des öffentlichen Schlüssels, wie ihn GitHub in den App-Einstellungen anzeigt."""
    key = serialization.load_pem_private_key(pem, password=None)
    der = key.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return "SHA256:" + base64.b64encode(hashlib.sha256(der).digest()).decode()


def key_import(daten: Path) -> int:
    print(
        "PEM des Private Keys einfügen. Danach Enter, dann Strg+Z, dann noch einmal Enter:", file=sys.stderr
    )
    pem = sys.stdin.buffer.read().strip() + b"\n"
    try:
        fingerabdruck = _fingerabdruck(pem)
    except ValueError:
        print("Das ist kein lesbarer PEM-Private-Key. Nichts gespeichert.", file=sys.stderr)
        return 1
    daten.mkdir(parents=True, exist_ok=True)
    (daten / KEY_DATEI).write_bytes(verschluesseln(pem))
    print(f"Key importiert nach {daten / KEY_DATEI}")
    print(f"Fingerabdruck {fingerabdruck} (muss zum Key in den App-Einstellungen passen)")
    return 0


def key_pruefen(daten: Path) -> int:
    try:
        entschluesseln((daten / KEY_DATEI).read_bytes())
    except (OSError, TresorFehler) as fehler:
        print(f"Key NICHT lesbar: {fehler}")
        return 1
    print("Key lesbar")
    return 0


def start(konfig_pfad: Path, daten: Path) -> int:
    logging.basicConfig(
        filename=daten / LOG_DATEI,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    konfig = lade_konfig(konfig_pfad)
    pem = entschluesseln((daten / KEY_DATEI).read_bytes())
    # Neues Geheimnis bei jedem Start: Ein Neustart wirft alle Anmeldungen weg.
    admin_geheimnis = secrets.token_urlsafe(32)
    (daten / ADMIN_DATEI).write_text(admin_geheimnis, encoding="ascii")
    # Nur 127.0.0.1: Docker Desktop leitet host.docker.internal dorthin, das Heimnetz erreicht ihn nicht.
    server = BrokerServer(konfig, pem, admin_geheimnis, time.time, ("127.0.0.1", konfig.port))
    logging.info("Broker gestartet auf %s", server.url)
    server.serve_forever()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="broker", description=__doc__)
    befehle = parser.add_subparsers(dest="befehl", required=True)
    for name in ("key-import", "key-pruefen", "start"):
        befehl = befehle.add_parser(name)
        befehl.add_argument("--daten", type=Path, required=True, help="Ordner für Key, Admin-Geheimnis, Log")
        if name == "start":
            befehl.add_argument("--konfig", type=Path, required=True, help="Pfad zur harness.toml")
    args = parser.parse_args()
    if args.befehl == "key-import":
        sys.exit(key_import(args.daten))
    if args.befehl == "key-pruefen":
        sys.exit(key_pruefen(args.daten))
    sys.exit(start(args.konfig, args.daten))


if __name__ == "__main__":
    main()
