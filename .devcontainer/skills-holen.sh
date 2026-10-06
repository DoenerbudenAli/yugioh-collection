#!/bin/bash
# Holt die Skill-Sammlungen aus harness.toml beim Bauen des Images (ADR 0005, „Selbstschutz“), nur von GitHub.
# Liest je Zeile „plugin github version commit“ (python -m devcontainer.konfig skills-liste) und legt jede
# Sammlung unter <ziel>/<plugin> ab. Zeigt der Tag nicht auf den Commit aus harness.toml, bricht der Bau ab.
#   skills-holen.sh /opt/harness/skills < skills.txt
set -euo pipefail
export GIT_TERMINAL_PROMPT=0

fehler() { echo "skills-holen: $*" >&2; exit 1; }
[ $# -eq 1 ] || fehler "Aufruf: skills-holen.sh <ziel> < skills.txt"
ziel=$1

while read -r plugin github version commit; do
    [ -n "$plugin" ] || continue
    url="https://github.com/$github.git"
    refs=$(git ls-remote "$url" "refs/tags/$version" "refs/tags/$version^{}") \
        || fehler "$url nicht abrufbar (Sammlung $plugin)"
    [ -n "$refs" ] || fehler "Version $version gibt es in $github nicht (harness.toml, Sammlung $plugin)"
    # Ein annotierter Tag hat eine zweite Zeile „…^{}“ mit seinem Commit, ein einfacher Tag nur eine.
    ist=$(awk '{print $1}' <<<"$refs" | tail -n 1)
    [ "$ist" = "$commit" ] \
        || fehler "$github $version zeigt auf $ist, harness.toml erwartet $commit (Sammlung $plugin)"

    ordner="$ziel/$plugin"
    rm -rf -- "$ordner"
    git init -q "$ordner"
    git -C "$ordner" fetch -q --depth 1 "$url" "$commit"
    git -C "$ordner" -c advice.detachedHead=false checkout -q FETCH_HEAD
    rm -rf -- "$ordner/.git"
    echo "skills-holen: $plugin $version ($commit) aus $github"
done
