#!/bin/bash
# Läuft als User agent: eigener Clone im Volume (ADR 0005, „Clone“), danach wartet der Container auf docker exec.
set -euo pipefail

ziel="/arbeit/${HARNESS_REPOSITORY#*/}"
if [ ! -d "$ziel/.git" ]; then
    rm -rf -- "$ziel.tmp"
    git clone "https://github.com/${HARNESS_REPOSITORY}.git" "$ziel.tmp"
    mv -- "$ziel.tmp" "$ziel"
fi
touch /run/harness/bereit
echo "bereit: $ziel"

trap 'exit 0' TERM INT
sleep infinity &
wait
