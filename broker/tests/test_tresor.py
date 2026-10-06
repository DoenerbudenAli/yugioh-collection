"""DPAPI-Tresor für den Private Key (ADR 0005, „Broker“). Nur unter Windows."""

import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="DPAPI gibt es nur unter Windows")


def test_verschluesselter_key_laesst_sich_unter_demselben_user_wieder_oeffnen() -> None:
    from broker.tresor import entschluesseln, verschluesseln

    geheim = b"-----BEGIN RSA PRIVATE KEY-----\nbeispiel\n-----END RSA PRIVATE KEY-----\n"

    blob = verschluesseln(geheim)

    assert geheim not in blob
    assert entschluesseln(blob) == geheim


def test_beschaedigter_blob_wird_abgewiesen() -> None:
    from broker.tresor import TresorFehler, entschluesseln, verschluesseln

    blob = bytearray(verschluesseln(b"geheim"))
    blob[-1] ^= 0xFF

    with pytest.raises(TresorFehler):
        entschluesseln(bytes(blob))
