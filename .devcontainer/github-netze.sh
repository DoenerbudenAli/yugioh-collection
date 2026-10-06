#!/bin/bash
# Gibt die IPv4-Netze von GitHub für die übergebenen Schlüssel aus api.github.com/meta aus, eines je Zeile.
# Läuft beim Bauen des Images (nicht beim Start): Ein Containerstart braucht so keine GitHub-API-Abfrage,
# denn anonym gilt ein Limit von 60/h je IP. Die CI reicht ihr Token als Build-Secret github_token herein.
#   github-netze.sh web api git > /etc/harness/github-netze.txt
set -euo pipefail

fehler() { echo "github-netze: $*" >&2; exit 1; }
[ $# -gt 0 ] || fehler "keine Schlüssel angegeben"

url="${HARNESS_GITHUB_META_URL:-https://api.github.com/meta}"
auth=()
if [ -s /run/secrets/github_token ]; then
    auth=(-H "Authorization: Bearer $(cat /run/secrets/github_token)")
fi
kopf=$(mktemp)
koerper=$(mktemp)
status=$(curl -sS --max-time 30 "${auth[@]}" -D "$kopf" -o "$koerper" -w '%{http_code}' "$url" || true)
if [ "$status" != 200 ]; then
    if grep -qi '^x-ratelimit-remaining: *0' "$kopf"; then
        reset=$(awk -F': *' 'tolower($1) == "x-ratelimit-reset" {print $2+0}' "$kopf")
        fehler "GitHub-Abfragelimit erschöpft, wieder frei in $(( (reset - $(date +%s)) / 60 + 1 )) min ($(date -u -d "@$reset" +%H:%M) UTC)"
    fi
    fehler "$url nicht abrufbar (HTTP ${status:-keine Antwort})"
fi
for schluessel in "$@"; do
    netze=$(jq -r --arg s "$schluessel" '.[$s][]? | select(contains(":") | not)' "$koerper")
    [ -n "$netze" ] || fehler "Schlüssel „$schluessel“ liefert keine IPv4-Netze (github_meta in harness.toml prüfen)"
    printf '%s\n' "$netze"
done
