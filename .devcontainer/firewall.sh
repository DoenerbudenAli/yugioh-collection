#!/bin/bash
# Netz-Allowlist (ADR 0005, „Netz“): Default DROP. Nach außen darf nur der Egress-Proxy (User egress, Port 443),
# dazu DNS und der Broker auf seinem Port. Welche Hostnamen hinaus dürfen, entscheidet der Proxy
# (/etc/harness/netz.env, DOMAINS). IPs allein reichen nicht: CDNs teilen sie mit fremden Seiten.
# Der Proxy muss schon laufen, sonst scheitert der Selbsttest.
set -euo pipefail

# shellcheck source=/dev/null
source /etc/harness/netz.env   # BROKER_PORT, DOMAINS

fehler() { echo "firewall: $*" >&2; exit 1; }

# 1. Tippfehler in der Allowlist früh melden, solange das Netz noch offen ist.
for domain in $DOMAINS; do
    # getent endet mit 2, wenn es den Namen nicht gibt; die Meldung kommt dann von fehler().
    [ -n "$(getent ahostsv4 "$domain" || true)" ] || fehler "Domain ohne IPv4-Adresse: $domain"
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
iptables -A OUTPUT -m owner --uid-owner egress -p tcp --dport 443 -j ACCEPT
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

# 3. Selbsttest: Die Firewall darf nie still offen oder ganz zu sein. curl nimmt den Proxy aus HTTPS_PROXY.
if curl -sS --max-time 5 -o /dev/null https://example.com 2>/dev/null; then
    fehler "Selbsttest fehlgeschlagen: example.com ist erreichbar"
fi
if curl -sS --max-time 5 --noproxy '*' -o /dev/null https://github.com 2>/dev/null; then
    fehler "Selbsttest fehlgeschlagen: github.com ist am Proxy vorbei erreichbar"
fi
# github.com statt der API: Jede HTTP-Antwort beweist die Verbindung und kostet kein Abfragelimit.
curl -sS --max-time 10 -o /dev/null https://github.com \
    || fehler "Selbsttest fehlgeschlagen: github.com ist über den Proxy nicht erreichbar"
echo "firewall: aktiv, nach außen nur der Proxy ($(wc -w <<<"$DOMAINS") Hostnamen), Broker $broker_ip:$BROKER_PORT"
