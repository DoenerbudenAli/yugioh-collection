r"""Startpunkt für `just agent` und `just weg` auf dem Host, mit dem System-Python und ohne venv.

Das Paket `devcontainer` braucht nur die Standardbibliothek. Aufruf aus dem Repo-Root:
`python .devcontainer/agent.py start <rolle> <name>` (bzw. `weg <name>`, `abmelden <name>`).
"""

import sys
from pathlib import Path

basis = Path(__file__).resolve().parent
sys.path.insert(0, str(basis / "src"))

from devcontainer.agent import main  # noqa: E402

sys.exit(main(sys.argv[1:], basis.parent / "harness.toml"))
