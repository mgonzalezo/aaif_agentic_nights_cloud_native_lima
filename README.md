# Agentic Bestiary

A small turn-based terminal game that maps the ten projects of the Agentic AI
Foundation (AAIF) onto one developer-assistant story. Built for the talk
**"AAIF y cloud native: un mapa para empezar con los agentes de IA"**
(Agentic Nights, Lima, November 2026).

Ten original creatures, one per project, help a dev team fix issue #7 in a toy
upstream project called `farolito`: read the issue, stay safe from a prompt
injection, follow the upstream rules, fix the bug, test it in a sandbox, get a
review from another team's agent, and open the pull request.

Every step shows a badge:

| Badge | Meaning |
|---|---|
| **LIVE** | A real call, happening now. The raw JSON is shown. |
| **REPLAY** | A real run recorded earlier (date and model shown). |
| **DIDACTIC** | An explanation, not a real run. It says so. |

> Unofficial personal project. Not endorsed by the AAIF or the Linux Foundation.
> No project logos are used. See [NOTICE](NOTICE).

**Start here:** [instructions.md](instructions.md) to play it (Windows, macOS, Fedora and other Linux),
[developers.md](developers.md) to deploy it in the cloud or change it.

## Quick start (5 minutes)

You need [uv](https://docs.astral.sh/uv/). It installs Python for you.

```bash
git clone <this repo>
cd <this repo>
uv sync
uv run bestiary
```

That already runs MCP, A2A, AGENTS.md and Agent Skills for real. Steps that need
a model, goose, a gateway, Docker or Kubernetes fall back to REPLAY or DIDACTIC.

Check what you have and what each piece unlocks:

```bash
uv run bestiary doctor
```

## Add pieces as you go

| Level | Install | What becomes real |
|---|---|---|
| 0 | uv | MCP, A2A protocol, AGENTS.md, Agent Skills |
| 0+ | [Ollama](https://ollama.com) and `ollama pull qwen3.5:9b` (or an OpenAI key) | The agent loop, Open Responses, the A2A reviewer |
| 1 | [goose](https://goose-docs.ai) CLI | Encounter 5: a real agent edits the code |
| 1 | [agentgateway](https://agentgateway.dev) (Windows: use WSL2) | Encounters 3 and 8: tool filtering |
| 2 | Docker and the OpenSandbox server | Encounter 6: tests in a sandbox |
| 3 | kind and kubectl | The Kubernetes region |
| Cloud | An AWS account (CPU instance, no GPU quota needed) | Everything as pods on one EC2 host, nothing on your laptop: [docs/AWS_DEPLOY.md](docs/AWS_DEPLOY.md). Step by step with measured results: [docs/TRY_IT.md](docs/TRY_IT.md) |

Step-by-step instructions per OS: [docs/SETUP.md](docs/SETUP.md).

No model? Set `OPENAI_API_KEY` and `OPENAI_MODEL` in `.env` (copy
`.env.example`). The game uses Ollama first when the model is pulled.

## The map

| Category | Rule in the game | Projects |
|---|---|---|
| AGENT | Takes turns and chooses moves | goose |
| PROTOCOL | Gives the agent moves; no turn of its own | MCP, A2A |
| INSTRUCTION FORMAT | A passive aura loaded from a file | AGENTS.md, Agent Skills |
| GATEWAY | A field effect: filters, routes, records | agentgateway, Agent Router |
| API SPECIFICATION | The language spoken in the arena | Open Responses |
| SANDBOX | Run moves take no Risk damage | OpenSandbox |
| TRAINING ENVIRONMENT | A dojo between chapters | OpenEnv |

## The encounters

| # | Challenge | Workflow step | What really happens |
|---|---|---|---|
| 0 | The lab | Meet the team | Only the agent has Autonomy above 0 |
| 1 | "How do I run the tests?" | Consult information | Reads `AGENTS.md` (a Markdown file) |
| 2 | The issue in the fog | Read the issue | `tools/list` and `read_issue` over MCP with **no model**; then [`minimal_agent.py`](minimal_agent.py) does it with a model |
| 3 | Injection | Stay safe | The issue hides "delete the main branch". agentgateway removes `delete_branch` from `tools/list` and rejects direct calls |
| 4 | The upstream ritual | How we contribute | Token meter: all skills vs progressive disclosure |
| 5 | The bug | Propose a change | goose edits `farolito/cli.py` (150 s cap, one live retry, then the known-good fix) |
| 6 | The flaky test | Test safely | `pytest` inside OpenSandbox |
| 7 | Second opinion | Review by another team | A2A Agent Card, task delegation, Open Responses items |
| 8 | The PR | Open the pull request | `create_pull_request` through the gateway (local forge or real GitHub) |
| 9 | Detour | Many models | Agent Router vs agentgateway. In the cloud profile: a request to the main model, then a simulated outage and the failover to a small model (LIVE). On a laptop: replay or DIDACTIC |
| 10 | The dojo | Improve the model later | Tests as a reward signal. With an OpenEnv server (`envs/farolito_env`): `reset` and `step` over HTTP (LIVE). Otherwise DIDACTIC |
| K8s | Kubernetes region | Share it with many teams | The same services as pods in kind, or (cloud profile) the pod the game itself runs in |

## Commands

```bash
uv run bestiary                 # play (Enter = live, r = replay, s = skip)
uv run bestiary play --ui battle # Pokemon-style battle screens (docs/BATTLE_UI.md)
uv run bestiary play --only 3   # one encounter (index)
uv run bestiary play --replay-only
uv run bestiary doctor
uv run bestiary services        # forge MCP on :8765, reviewer A2A on :9999
uv run bestiary record          # run everything live and save replays/
uv run bestiary sprites         # show the creatures
uv run bestiary sprites --out assets/sprites   # PNGs for slides
uv run bestiary github-setup <owner>/<repo>    # demo repo for a real PR
uv run bestiary k8s up | down       # kind cluster (laptop, no GPU)
BESTIARY_PROFILE=cloud uv run bestiary   # in-cluster service URLs (used inside the console pod)
uv run python minimal_agent.py "Read issue 7"
uv run pytest -q
```

## Repository layout

```
bestiary/            the game (engine, encounters, sprites, model client)
bestiary/services/   forge_mcp.py (MCP server), reviewer_a2a.py (A2A agent)
minimal_agent.py     a whole agent in about 100 lines (shown on screen)
upstream/farolito/   the toy upstream project, with AGENTS.md and .agents/skills
gateway/             agentgateway config (allow-list policy)
goose/               goose recipe for rehearsing encounter 5 by hand
k8s/                 Dockerfile and kustomize: base/ shared, overlays/kind (laptop), overlays/ec2 (GPU)
envs/farolito_env/   OpenEnv environment for encounter 10
infra/aws/           CloudFormation, deploy/teardown/present/schedule-teardown scripts, bootstrap.sh (the demo host)
agent-router/        how to record the Agent Router replay
docker/              sandbox image for OpenSandbox
replays/             recorded real runs
docs/                setup per OS, AWS deploy, battle screens, stage runbook and the presenter script
```

## Licence

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
Contributions welcome: [CONTRIBUTING.md](CONTRIBUTING.md).
