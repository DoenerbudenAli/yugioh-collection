#!/bin/bash
# Einstieg des Containers (ADR 0005, „Grenze“, „Netz“): als root den Egress-Proxy starten, die Firewall setzen
# und prüfen, dann endgültig zum User agent wechseln, ohne Capabilities. Scheitert etwas, endet der Container.
set -euo pipefail

[ "$(id -u)" = 0 ] || { echo "einstieg: muss als root starten" >&2; exit 1; }
# Das Bereit-Zeichen muss auf tmpfs liegen, sonst überlebt es einen Neustart und meldet „bereit“,
# bevor die Firewall wieder steht.
[ "$(stat -f -c %T /run/harness 2>/dev/null)" = tmpfs ] || { echo "einstieg: /run/harness ist kein tmpfs (docker run --tmpfs fehlt)" >&2; exit 1; }

# Egress-Proxy als eigener User egress: Nur er darf laut Firewall hinaus, agent kann ihn weder ändern noch beenden.
# cd / und -P: Python lädt so keinen Code aus /arbeit, dem Volume, in das agent schreibt.
# shellcheck source=/dev/null
source /etc/harness/netz.env   # DOMAINS
# shellcheck disable=SC2086  # DOMAINS ist eine Liste von Hostnamen
(cd / && exec setpriv --reuid=egress --regid=egress --init-groups --inh-caps=-all --bounding-set=-all --no-new-privs \
    env PYTHONPATH=/opt/harness/src python3 -P -m devcontainer.proxy "$HARNESS_PROXY_PORT" $DOMAINS) &
for _ in $(seq 50); do
    if (exec 3<>"/dev/tcp/127.0.0.1/$HARNESS_PROXY_PORT") 2>/dev/null; then break; fi
    kill -0 $! 2>/dev/null || { echo "einstieg: Proxy ist beim Start beendet" >&2; exit 1; }
    sleep 0.1
done
/opt/harness/firewall.sh

exec setpriv --reuid=agent --regid=agent --init-groups --inh-caps=-all --bounding-set=-all --no-new-privs \
    env HOME=/home/agent USER=agent LOGNAME=agent /opt/harness/als-agent.sh
