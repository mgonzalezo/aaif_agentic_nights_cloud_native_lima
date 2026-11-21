# Setup per operating system

Start at level 0 and stop wherever you like. `uv run bestiary doctor` tells you
what each installed piece unlocks.

## Level 0: the game (all systems)

| OS | Install uv |
|---|---|
| macOS / Linux | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Windows (PowerShell) | `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 \| iex"` |

```bash
git clone <this repo> && cd <this repo>
uv sync
uv run bestiary
```

Use a terminal at least 110 columns wide with a font that has block characters
(Windows Terminal, iTerm2, GNOME Terminal and VS Code all work).

## Level 0+: a model

**Option A: Ollama (local, offline).** Install from https://ollama.com, then:

```bash
ollama pull qwen3.5:9b        # 16 GB RAM or more
# 8 GB machines: ollama pull qwen3.5:4b and set BESTIARY_MODEL=qwen3.5:4b in .env
```

The game calls `/v1/responses` (Open Responses), which needs Ollama 0.13.3 or later.

**Option B: OpenAI.** In `.env`:

```
OPENAI_API_KEY=sk-...
OPENAI_MODEL=<a model your key can use with the Responses API and function calling>
```

With `BESTIARY_PROVIDER=auto` (default), Ollama is used when the model is pulled,
otherwise OpenAI.

## Level 1: goose and agentgateway

**goose:** follow https://goose-docs.ai (CLI install). The game sets
`GOOSE_PROVIDER`, `GOOSE_MODEL` and `OLLAMA_HOST` for you. If your goose version
uses different flags, set `BESTIARY_GOOSE_CMD` in `.env`, for example
`BESTIARY_GOOSE_CMD=goose run --with-builtin developer -t`.

**agentgateway:** install the binary from
https://agentgateway.dev/docs/standalone/latest/setup/install/binary/
(Windows: run it inside WSL2 until a stable Windows build is published). Then, in
two terminals:

```bash
uv run bestiary services                  # forge MCP on :8765
agentgateway -f gateway/agentgateway.yaml # gateway on :3000
```

and play in a third.

## Level 2: OpenSandbox (Docker)

```bash
docker build -t bestiary-sandbox:latest -f docker/sandbox.Dockerfile docker
uv sync --extra sandbox
uvx opensandbox-server        # check `uvx opensandbox-server --help` for config
```

The game expects the server at `localhost:8080` (`OPEN_SANDBOX_DOMAIN`).
Project: https://github.com/opensandbox-group/OpenSandbox

## Level 3: Kubernetes (kind)

Needs Docker, kind and kubectl.

```bash
uv run bestiary k8s up      # cluster + image + manifests
uv run bestiary play --only 11
uv run bestiary k8s down
```

The reviewer pod calls Ollama on your host:

- macOS and Windows (Docker Desktop): works as is through `host.docker.internal`.
- Linux: start Ollama with `OLLAMA_HOST=0.0.0.0 ollama serve` and change
  `OLLAMA_HOST` in `k8s/reviewer-a2a.yaml` to your docker bridge IP
  (often `http://172.17.0.1:11434`).

## Real pull requests on GitHub (encounter 8)

1. Create a fine-grained token with Contents, Issues and Pull requests
   read/write (plus Administration if the script should create the repo).
2. Put it in `.env` as `GITHUB_TOKEN=...`.
3. `uv run bestiary github-setup <you>/farolito-demo`
4. Add `BESTIARY_FORGE=github` and `BESTIARY_GITHUB_REPO=<you>/farolito-demo` to `.env`.
5. Protect `main` in the repo settings.

Each run opens a new branch and PR; close them after rehearsals.
