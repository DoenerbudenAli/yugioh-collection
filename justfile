# Befehle für Owner und Agenten. Unter Windows laufen die Rezepte in PowerShell.
set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]

# Agenten-Session im Container starten oder fortsetzen (ADR 0005). Rollen stehen in harness.toml.
agent rolle name:
    python .devcontainer/agent.py start {{rolle}} {{name}}

# Container samt Volume wegwerfen und den Schlüssel beim Broker abmelden.
weg name:
    python .devcontainer/agent.py weg {{name}}
