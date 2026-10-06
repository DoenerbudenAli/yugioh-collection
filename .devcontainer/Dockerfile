# syntax=docker/dockerfile:1
# Image der Agenten-Container (ADR 0005, „Grenze“, „Netz“, „Selbstschutz“). Gebaut wird es nur vom Workflow
# devcontainer aus main; Agenten bauen nie Images. Build-Kontext ist der Repo-Root:
#   docker build -f .devcontainer/Dockerfile .
FROM ghcr.io/astral-sh/uv:0.12.23 AS uv

FROM node:24-trixie-slim@sha256:173f125896c3b47ddf056734c7ea789d04595a6a08769a8f78e0df642781fb66

ARG PNPM_VERSION=12.9.1
ARG CLAUDE_CODE_VERSION=2.1.291

# Kein sudo: Das Image hat keinen Weg vom User agent zu root.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash ca-certificates curl git ipset iptables jq just less procps python3 \
    && install -d -m 0755 /etc/apt/keyrings \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
        -o /etc/apt/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
        > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /uvx /usr/local/bin/
RUN npm install -g "pnpm@${PNPM_VERSION}" "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" \
    && npm cache clean --force

RUN userdel --remove node \
    && useradd --create-home --uid 1000 --shell /bin/bash agent \
    && install -d -o agent -g agent /arbeit

COPY .devcontainer/src /opt/harness/src
# Wrapper in /usr/local/bin: Das steht auch in Login-Shells vor /usr/bin.
COPY --chmod=0755 .devcontainer/bin/ /usr/local/bin/
COPY --chmod=0755 .devcontainer/einstieg.sh .devcontainer/firewall.sh .devcontainer/als-agent.sh \
    .devcontainer/github-netze.sh /opt/harness/
COPY harness.toml /opt/harness/harness.toml

# Die Allowlist kommt aus dem harness.toml dieses Builds (main), nicht aus dem Clone im Volume.
RUN install -d /etc/harness \
    && PYTHONPATH=/opt/harness/src python3 -m devcontainer.konfig netz-env /opt/harness/harness.toml \
        > /etc/harness/netz.env \
    && git config --system credential.helper broker

# GitHub-Netze einmal beim Bauen holen, damit kein Start die GitHub-API braucht (anonym 60/h je IP).
# Die CI reicht ihr Token als Secret herein (höheres Limit); es landet in keiner Schicht des Images.
RUN --mount=type=secret,id=github_token,required=false \
    . /etc/harness/netz.env \
    && /opt/harness/github-netze.sh $GITHUB_META > /etc/harness/github-netze.txt

COPY --chown=agent:agent .devcontainer/claude-settings.json /home/agent/.claude/settings.json
COPY --chown=agent:agent .devcontainer/claude.json /home/agent/.claude.json

ENV GIT_TERMINAL_PROMPT=0 \
    CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 \
    DISABLE_AUTOUPDATER=1 \
    UV_PYTHON_PREFERENCE=only-system \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /arbeit
ENTRYPOINT ["/opt/harness/einstieg.sh"]
