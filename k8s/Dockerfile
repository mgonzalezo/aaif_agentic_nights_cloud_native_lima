# Two images from one file. Build context: the repo root.
#   services  forge MCP server and the A2A reviewer (kind overlay, reviewer pod)
#               docker build --target services -t bestiary-services:dev -f k8s/Dockerfile .
#   console   the game plus goose, uv and kubectl (ec2 overlay: the console pod, also runs forge)
#               docker build --target console -t bestiary-console:dev -f k8s/Dockerfile .
# "services" is the LAST stage, so a plain `docker build` still produces it.

FROM python:3.12-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY bestiary ./bestiary
COPY upstream ./upstream
COPY minimal_agent.py ./
RUN uv sync --frozen --no-dev --extra sandbox
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8765 9999

FROM base AS console
ARG GOOSE_VERSION=v1.60.1
ARG KUBECTL_VERSION=v1.37.2
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl bzip2 ca-certificates git libgomp1 libxcb1 \
    && rm -rf /var/lib/apt/lists/*
# goose: pinned release, headless install (CONFIGURE=false skips the interactive setup)
RUN curl -fsSL https://github.com/aaif-goose/goose/releases/download/stable/download_cli.sh \
    | GOOSE_VERSION="${GOOSE_VERSION}" CONFIGURE=false GOOSE_BIN_DIR=/usr/local/bin bash \
    && goose --version
# kubectl: same minor as the k3s server
RUN curl -fsSL -o /usr/local/bin/kubectl "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl" \
    && chmod +x /usr/local/bin/kubectl
COPY replays ./replays
COPY agent-router ./agent-router
COPY goose ./goose
COPY gateway ./gateway
COPY k8s ./k8s
RUN useradd -m -u 1000 bestiary && mkdir -p /state && chown -R 1000:1000 /state /app/replays
USER 1000
ENV HOME=/home/bestiary BESTIARY_PROFILE=cloud BESTIARY_STATE_DIR=/state
CMD ["bestiary"]

FROM base AS services
CMD ["python", "-m", "bestiary.services.forge_mcp", "--host", "0.0.0.0"]
