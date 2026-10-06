"""DPAPI des angemeldeten Windows-Users, per ctypes ohne Zusatzpaket.

Ein Blob lässt sich nur unter dem User wieder öffnen, der ihn verschlüsselt hat. Läuft der Broker unter
einem eigenen Dienstkonto, kann der Owner-User (und jeder Agent unter dessen Login) den Key nicht lesen.
"""

import ctypes
import sys
from ctypes import wintypes

# Keine Rückfrage-Dialoge: Der Broker läuft ohne Desktop.
_CRYPTPROTECT_UI_FORBIDDEN = 0x01


class TresorFehler(Exception):
    pass


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _dll(name: str) -> ctypes.WinDLL:
    return ctypes.WinDLL(name, use_last_error=True)


def _blob_aus(daten: bytes) -> tuple[_Blob, ctypes.Array[ctypes.c_char]]:
    puffer = ctypes.create_string_buffer(daten, len(daten))
    return _Blob(len(daten), ctypes.cast(puffer, ctypes.POINTER(ctypes.c_char))), puffer


def _bytes_aus(blob: _Blob) -> bytes:
    try:
        return ctypes.string_at(blob.pbData, blob.cbData)
    finally:
        _dll("kernel32").LocalFree(blob.pbData)


def verschluesseln(daten: bytes) -> bytes:
    if sys.platform != "win32":
        raise TresorFehler("DPAPI gibt es nur unter Windows")
    eingabe, _puffer = _blob_aus(daten)
    ausgabe = _Blob()
    ok = _dll("crypt32").CryptProtectData(
        ctypes.byref(eingabe), None, None, None, None, _CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(ausgabe)
    )
    if not ok:
        raise TresorFehler(f"CryptProtectData fehlgeschlagen (Windows-Fehler {ctypes.get_last_error()})")
    return _bytes_aus(ausgabe)


def entschluesseln(blob: bytes) -> bytes:
    if sys.platform != "win32":
        raise TresorFehler("DPAPI gibt es nur unter Windows")
    eingabe, _puffer = _blob_aus(blob)
    ausgabe = _Blob()
    ok = _dll("crypt32").CryptUnprotectData(
        ctypes.byref(eingabe), None, None, None, None, _CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(ausgabe)
    )
    if not ok:
        raise TresorFehler(
            f"CryptUnprotectData fehlgeschlagen (Windows-Fehler {ctypes.get_last_error()}). "
            "Läuft das hier unter einem anderen User als dem, der den Key importiert hat?"
        )
    return _bytes_aus(ausgabe)
