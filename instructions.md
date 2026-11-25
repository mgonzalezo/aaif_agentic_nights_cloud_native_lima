# Play the Agentic Bestiary

A terminal game in which ten creatures, one per project of the Agentic AI Foundation (AAIF), fix a real bug
in a toy project. Each step is a real call to a real component, and the game tells you which ones are not.

> Unofficial personal project. Not endorsed by the AAIF or the Linux Foundation. See [NOTICE](NOTICE).

You need about **five minutes** and nothing else than a terminal. No model, no GPU, no cloud account, no Docker.
Want to run it in the cloud as pods, like in the talk? That is [developers.md](developers.md).

## 1. Install and run

Pick your system. All of them end in the same two commands: `uv sync` and `uv run bestiary`.
[uv](https://docs.astral.sh/uv/) installs the right Python for you (the game needs 3.11 or newer), so you do not.

### Fedora (and other Linux)

```bash
sudo dnf install -y git curl                 # Debian/Ubuntu: sudo apt install -y git curl
curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"                # or open a new terminal

git clone https://github.com/mgonzalezo/aaif_agentic_nights_cloud_native_lima.git
cd aaif_agentic_nights_cloud_native_lima
uv sync
uv run bestiary doctor                       # what you have, and what each missing piece would unlock
uv run bestiary                              # play
```

### macOS

```bash
brew install git uv                          # or: curl -LsSf https://astral.sh/uv/install.sh | sh
git clone https://github.com/mgonzalezo/aaif_agentic_nights_cloud_native_lima.git
cd aaif_agentic_nights_cloud_native_lima
uv sync
uv run bestiary doctor
uv run bestiary
```

### Windows

Use **Windows Terminal** (or PowerShell 7). The old console window cannot draw the creatures.

```powershell
winget install --id Git.Git -e
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
# open a NEW terminal so that git and uv are on the PATH, then:
git clone https://github.com/mgonzalezo/aaif_agentic_nights_cloud_native_lima.git
cd aaif_agentic_nights_cloud_native_lima
uv sync
uv run bestiary doctor
uv run bestiary
```

If you see `UnicodeEncodeError`, run `$env:PYTHONUTF8 = "1"` first.

### Make the terminal big enough

The screens need **110 columns and 40 rows** or more, and a font with block characters (every default terminal
font on Fedora, macOS and Windows Terminal has them). Check with `tput cols; tput lines` (Linux, macOS) or
`$Host.UI.RawUI.WindowSize` (PowerShell). Below 100 columns the battle screens switch themselves off and you
get the classic ones.

## 2. Choose your interface

| | Command | Keys |
|---|---|---|
| **Classic** (default) | `uv run bestiary` | **Enter** runs the step live, **r** shows a recorded replay, **s** skips |
| **Battle screens** (Pokémon style) | `uv run bestiary play --ui battle` | **← ↑ ↓ →** move, **Enter** chooses |

In the battle screens every encounter is a fight between one of your creatures and an obstacle of the story:

```
  ▶ POKÉDEX      FIGHT
    REPLAY       RUN
```

- **POKÉDEX**: what the project is, what it is good for and its weakness. With a team, **← →** flips between the creatures.
- **FIGHT**: runs the step for real (badge **LIVE**).
- **REPLAY**: shows a real recording of the step, with its date (badge **REPLAY**).
- **RUN**: skips the step.

The obstacle box tells you **what it is** and **why it is a problem**, and the creature carries the real name of its
project (`CHAMBERO  goose`). Between screens, **Enter** or **→** continues. If your terminal does not send arrows the
game understands, **W A S D** or **H J K L** move, **1 2 3 4** jump to a choice and **Tab** goes to the next one;
the menu names a key it did not recognise, and `uv run bestiary keytest` shows what each key sends.
More in [docs/BATTLE_UI.md](docs/BATTLE_UI.md).

## 3. What the badges mean

| Badge | Meaning |
|---|---|
| **LIVE** | A real call, happening now. You see the raw JSON. |
| **REPLAY** | A real run recorded earlier (date and model are shown). It is used when a piece is missing on your machine. |
| **DIDACTIC** | An explanation, not a real run. It says so. |

With nothing installed (checked on a laptop with no model, no goose and no gateway) encounters 1, 2 (part A), 4 and 8 are
LIVE, and the others show their recorded REPLAY. The game never calls a recording "live".

## 4. Make more of it real (all optional, one piece at a time)

`uv run bestiary doctor` shows what each piece unlocks. Steps in the order that pays off most:

| You add | What becomes live |
|---|---|
| **A model** (below) | The agent loop (encounter 2), the Open Responses call, the A2A reviewer (7) |
| **goose** | Encounter 5: a real agent edits the code |
| **agentgateway** | Encounters 3 and 8: the gateway hides `delete_branch` |
| **Docker + OpenSandbox** | Encounter 6: the tests run in a sandbox |
| **kind + kubectl** | The Kubernetes region |

### A local model with Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh      # Linux. macOS and Windows: the installer at https://ollama.com
ollama --version                                   # 0.13.3 or newer (the game calls /v1/responses)
ollama pull qwen3.5:9b                             # 16 GB of RAM or more
# 8 GB machines:  ollama pull qwen3.5:4b   and put BESTIARY_MODEL=qwen3.5:4b in .env
uv run bestiary doctor                             # it should now list the model
```

On Fedora, if the installer complains about a missing tool, `sudo dnf install -y zstd` and run it again.
No Ollama? Copy `.env.example` to `.env` and set `OPENAI_API_KEY` and `OPENAI_MODEL` (a model that supports the
Responses API and function calling).

### goose, agentgateway, OpenSandbox, kind

Step by step for every system in [docs/SETUP.md](docs/SETUP.md). Two things to know: agentgateway on Windows runs
inside WSL2, and on Linux the kind cluster reaches Ollama through your Docker bridge (SETUP explains it).

## 5. If something does not work

| What you see | What to do |
|---|---|
| `uv: command not found` | Open a new terminal, or run `source "$HOME/.local/bin/env"` (Linux, macOS). |
| The screens are garbled or cut | Make the window wider and taller (section 1). `uv run bestiary play --ui classic` is more forgiving. |
| The arrows do nothing | Use **W A S D**, or run `uv run bestiary keytest`, press an arrow and open an issue with the `raw:` line. |
| A port is busy | The game starts a forge on port 8765 and a reviewer on 9999. Set `BESTIARY_FORGE_PORT` and `BESTIARY_REVIEWER_PORT` to free ports. |
| A step says `live step not available: ...` | That piece is missing. The reason is printed, and the replay (or the explanation) follows. |
| Start again from a step | `uv run bestiary play --start 5` (from encounter 5) or `--only 5` (just that one). `--replay-only` never runs anything live. |
| Check everything | `uv run pytest -q` runs the tests (about 90 seconds, no network). |

## 6. Where to go next

- The story, step by step: [README.md](README.md).
- Run all of it as pods in the cloud (costs money until you delete it): [developers.md](developers.md).
- Change the code, add a creature or an encounter: [Develop locally](developers.md#develop-locally-no-cloud-no-cost) and "Extend it" in [developers.md](developers.md), then [CONTRIBUTING.md](CONTRIBUTING.md).

Tested on Windows 11 with Windows Terminal, and inside a Linux container (the cloud demo's console pod). The Fedora and
macOS commands use the official installers of uv, Ollama and Homebrew and are the same as on Linux: tell us if one breaks.
