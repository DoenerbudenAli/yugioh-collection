#!/bin/bash
# Einstieg des Containers (ADR 0005, „Grenze“, „Netz“): als root die Firewall setzen und prüfen,
# dann endgültig zum User agent wechseln, ohne Capabilities. Scheitert die Firewall, endet der Container.
set -euo pipefail

[ "$(id -u)" = 0 ] || { echo "einstieg: muss als root starten" >&2; exit 1; }
/opt/harness/firewall.sh

exec setpriv --reuid=agent --regid=agent --init-groups --inh-caps=-all --bounding-set=-all --no-new-privs \
    env HOME=/home/agent USER=agent LOGNAME=agent /opt/harness/als-agent.sh
