r"""Startpunkt für den Betrieb auf dem Host, ohne venv.

Der Broker läuft mit dem Python aus `C:\Program Files\Python313` direkt, nicht über den venv-Launcher.
Der startet einen Unterprozess, und den beendet „Aufgabe stoppen“ nicht mit (Kill-Switch). Die
Abhängigkeiten liegen per `pip install --target lib` neben dieser Datei.
"""

import site
import sys
from pathlib import Path

basis = Path(__file__).resolve().parent
site.addsitedir(str(basis / "lib"))
sys.path.insert(0, str(basis / "src"))

from broker.__main__ import main  # noqa: E402

main()
