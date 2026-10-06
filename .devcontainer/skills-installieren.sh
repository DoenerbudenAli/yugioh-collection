#!/bin/bash
# Installiert die von skills-holen.sh geholten Sammlungen als Claude-Code-Plugins (Scope user). Läuft beim Bauen
# als User agent. Claude liest die Skills danach direkt aus <quelle>/<plugin>; das gehört root.
#   skills-installieren.sh /opt/harness/skills < skills.txt
set -euo pipefail

fehler() { echo "skills-installieren: $*" >&2; exit 1; }
[ $# -eq 1 ] || fehler "Aufruf: skills-installieren.sh <quelle> < skills.txt"
quelle=$1

while read -r plugin _; do
    [ -n "$plugin" ] || continue
    ordner="$quelle/$plugin"
    markt=$(jq -r '.name // empty' "$ordner/.claude-plugin/marketplace.json" 2>/dev/null || true)
    [ -n "$markt" ] || fehler "$plugin hat keine .claude-plugin/marketplace.json mit Namen"
    claude plugin marketplace add "$ordner"
    claude plugin install "$plugin@$markt"
done
