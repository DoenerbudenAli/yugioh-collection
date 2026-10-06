#!/bin/bash
# Netz-Allowlist (ADR 0005, „Netz“): Default DROP, erlaubt sind GitHub (api.github.com/meta), die Domains
# aus /etc/harness/netz.env (nur HTTPS) und der Broker auf seinem Port. Die IPs werden beim Start aufgelöst.
set -euo pipefail

# shellcheck source=/dev/null
source /etc/harness/netz.env   # BROKER_PORT, GITHUB_META, DOMAINS

fehler() { echo "firewall: $*" >&2; exit 1; }

# 1. Erlaubte Adressen sammeln, solange das Netz noch offen ist.
ipset destroy erlaubt 2>/dev/null || true
ipset create erlaubt hash:net
# Die einzige GitHub-API-Abfrage je Start: anonym gilt ein Limit von 60/h je IP (alle Container zusammen).
meta_url="${HARNESS_GITHUB_META_URL:-https://api.github.com/meta}"
kopf=$(mktemp)
status=$(curl -sS --max-time 20 -D "$kopf" -o /tmp/github-meta.json -w '%{http_code}' "$meta_url" || true)
if [ "$status" != 200 ]; then
    if grep -qi '^x-ratelimit-remaining: *0' "$kopf"; then
        reset=$(awk -F': *' 'tolower($1) == "x-ratelimit-reset" {print $2+0}' "$kopf")
        fehler "GitHub-Abfragelimit erschöpft (anonym 60/h je IP), wieder frei in $(( (reset - $(date +%s)) / 60 + 1 )) min ($(date -u -d "@$reset" +%H:%M) UTC)"
    fi
    fehler "$meta_url nicht abrufbar (HTTP ${status:-keine Antwort})"
fi
meta=$(cat /tmp/github-meta.json)
for schluessel in $GITHUB_META; do
    for netz in $(jq -r --arg s "$schluessel" '.[$s][]? | select(contains(":") | not)' <<<"$meta"); do
        ipset add erlaubt "$netz" -exist
    done
done
for domain in $DOMAINS; do
    # getent endet mit 2, wenn es den Namen nicht gibt; die Meldung kommt dann von fehler().
    ips=$(getent ahostsv4 "$domain" | awk '{print $1}' | sort -u || true)
    [ -n "$ips" ] || fehler "Domain ohne IPv4-Adresse: $domain"
    for ip in $ips; do ipset add erlaubt "$ip" -exist; done
done
broker_ip=$(getent ahostsv4 host.docker.internal | awk 'NR==1 {print $1}' || true)
[ -n "$broker_ip" ] || fehler "host.docker.internal nicht auflösbar"

# 2. Regeln. Nur die filter-Tabelle: Die nat-Regeln von Dockers DNS bleiben stehen.
iptables -F
iptables -X
iptables -A INPUT -i lo -j ACCEPT
iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
iptables -A OUTPUT -o lo -j ACCEPT
iptables -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
for ns in $(awk '/^nameserver/ && $2 !~ /:/ {print $2}' /etc/resolv.conf); do
    iptables -A OUTPUT -d "$ns" -p udp --dport 53 -j ACCEPT
    iptables -A OUTPUT -d "$ns" -p tcp --dport 53 -j ACCEPT
done
iptables -A OUTPUT -d "$broker_ip" -p tcp --dport "$BROKER_PORT" -j ACCEPT
iptables -A OUTPUT -m set --match-set erlaubt dst -p tcp --dport 443 -j ACCEPT
iptables -A OUTPUT -j REJECT --reject-with icmp-admin-prohibited
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT DROP
if ip6tables -L -n >/dev/null 2>&1; then
    ip6tables -F
    ip6tables -A INPUT -i lo -j ACCEPT
    ip6tables -A OUTPUT -o lo -j ACCEPT
    ip6tables -P INPUT DROP
    ip6tables -P FORWARD DROP
    ip6tables -P OUTPUT DROP
fi

# 3. Selbsttest: Die Firewall darf nie still offen oder ganz zu sein.
if curl -sS --max-time 5 -o /dev/null https://example.com 2>/dev/null; then
    fehler "Selbsttest fehlgeschlagen: example.com ist erreichbar"
fi
# github.com statt der API: Jede HTTP-Antwort beweist die Verbindung und kostet kein Abfragelimit.
curl -sS --max-time 10 -o /dev/null https://github.com \
    || fehler "Selbsttest fehlgeschlagen: github.com ist nicht erreichbar"
echo "firewall: Allowlist aktiv ($(ipset list erlaubt | grep -c '^[0-9]') Netze, Broker $broker_ip:$BROKER_PORT)"
