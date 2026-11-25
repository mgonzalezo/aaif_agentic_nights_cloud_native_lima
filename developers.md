# Developers: deploy it, run it, change it

For people who want to run the whole Bestiary the way it ran in the talk: every component as a pod on one cloud
host, with nothing but a terminal on your laptop. Just want to play? That is [instructions.md](instructions.md).

> Unofficial personal project. Not endorsed by the AAIF or the Linux Foundation. Demo-only infrastructure: no public
> access, no high availability, delete it when you are done.

> **THIS COSTS MONEY UNTIL YOU DELETE IT.** A `c7i.8xlarge` is about **1.43 USD/hour**, plus about 0.05 USD/hour for the
> 200 GB disk and the public IPv4 address. A *stopped* instance still bills for its disk until the stack is deleted.
> Read [section 6](#6-stop-paying) before you start, and schedule the teardown on day one.

## Develop locally (no cloud, no cost)

You can change and test almost everything on your own computer. The cloud is only needed to see the pods.
Windows, macOS and Linux all work (the commands below are the same; install uv and git as in
[instructions.md](instructions.md#1-install-and-run)).

```bash
git clone https://github.com/mgonzalezo/aaif_agentic_nights_cloud_native_lima.git
cd aaif_agentic_nights_cloud_native_lima
uv sync --all-extras           # Python 3.11 or newer (uv installs it), the game, the test tools and the optional extras
uv run pytest -q               # about 90 seconds, no network, no model: the tests use tests/fake_model.py
uv run bestiary doctor         # what you have, and what each missing piece would unlock
uv run bestiary play --only 3  # one encounter by index (0 the lab, 1 to 10 the encounters, 11 the Kubernetes region)
```

| While you work on... | Run |
|---|---|
| Any code | `uv run pytest -q`, or one file: `uv run pytest tests/test_battle.py -q` |
| An encounter | `uv run bestiary play --only 5`. Add `--auto` for no key presses, or `--replay-only` to never run anything live |
| The battle screens | `uv run bestiary play --ui battle --only 5` in a terminal of at least 110 columns and 40 rows |
| A creature or an obstacle (YAML) | The tests check every entry (fields present, screens fit in 110 columns). Look at it with `uv run bestiary sprites` or the battle screens |
| The steps that use a model | Install Ollama or set `OPENAI_API_KEY` ([instructions.md](instructions.md#4-make-more-of-it-real-all-optional-one-piece-at-a-time)); `uv run bestiary doctor` confirms it |
| The services | `uv run bestiary services` starts the forge MCP server on :8765 and the A2A reviewer on :9999. The game starts them itself when nothing listens there |
| The recorded replays | `uv run bestiary record` runs every encounter live and saves `replays/` (only real runs are saved). Commit them on purpose |
| How reliable a model step is | `uv run bestiary gate --runs 20` (needs a model; `--goose` adds goose and takes a long time) |
| A real Kubernetes cluster, on your laptop | `uv run bestiary k8s up` (needs Docker, kind and kubectl), then `uv run bestiary play --only 11`, then `uv run bestiary k8s down` |

Settings live in `.env` (copy [.env.example](.env.example); everything is optional). The default profile is `laptop`:
everything on `127.0.0.1`. The `cloud` profile (in-cluster service URLs) is for the console pod. On Windows the `.sh`
scripts need bash (Git Bash or WSL2); the `.ps1` twins do the same in PowerShell. Before you open a pull request, read
[CONTRIBUTING.md](CONTRIBUTING.md) (sign off your commits with `git commit -s`).

## 1. Pick a path

| Path | You need | Cost | Guide |
|---|---|---|---|
| **Laptop, no cloud** | Just uv and git; add Docker, [kind](https://kind.sigs.k8s.io) and kubectl for a local cluster | 0 | [Develop locally](#develop-locally-no-cloud-no-cost) above, and [docs/SETUP.md](docs/SETUP.md) levels 2 and 3 |
| **AWS, CPU instance** (tested) | An AWS account, AWS CLI v2, Session Manager plugin | about 1.5 USD/hour | this page |
| **AWS, GPU instance** (written, never run) | The same, plus a G/VT vCPU quota of 8 (new accounts start at 0) | about 2.3 USD/hour | [docs/AWS_DEPLOY.md](docs/AWS_DEPLOY.md) |

The CPU path runs `qwen3.5:35b` (a mixture of experts with about 3B active parameters) with thinking off, and
`qwen3.5:4b` as the fail-over model. Measured on a `c7i.8xlarge`: all 12 steps LIVE in three full rehearsals, a whole
run in 97 to 275 seconds; goose is the slow and the least reliable step (16 of 20 within 120 s in the reliability gate,
and the game retries it once, live). Details and numbers: [docs/TRY_IT.md](docs/TRY_IT.md).

## 2. What you need on your computer

| Need | Windows | Fedora / Linux | macOS |
|---|---|---|---|
| Git and uv | `winget install Git.Git`, then `irm https://astral.sh/uv/install.ps1 \| iex` | `sudo dnf install -y git curl` and `curl -LsSf https://astral.sh/uv/install.sh \| sh` | `brew install git uv` |
| AWS CLI v2 | [MSI installer](https://awscli.amazonaws.com/AWSCLIV2.msi) | [zip installer](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) | `brew install awscli` |
| **Session Manager plugin** (how you open a terminal in the instance) | [SessionManagerPluginSetup.exe](https://s3.amazonaws.com/session-manager-downloads/plugin/latest/windows/SessionManagerPluginSetup.exe), as Administrator | `sudo dnf install -y https://s3.amazonaws.com/session-manager-downloads/plugin/latest/linux_64bit/session-manager-plugin.rpm` | `brew install --cask session-manager-plugin` |
| A shell for the scripts | PowerShell (`.ps1` scripts) | bash (`.sh` twins) | bash or zsh (`.sh` twins) |

Check them with `git --version`, `uv --version`, `aws --version` and `session-manager-plugin --version`.
Use a terminal of at least **110 columns and 40 rows** to play.

Credentials: an AWS profile that can use CloudFormation, EC2, IAM, SSM and EventBridge Scheduler in `us-east-1`
(an admin-like profile is simplest for a throwaway account). Tell the scripts which one with `AWS_PROFILE`:

```bash
export AWS_PROFILE=my-profile            # PowerShell:  $env:AWS_PROFILE = 'my-profile'
aws sts get-caller-identity              # must print your account
```

**vCPU quota.** CPU types use "Running On-Demand Standard (A, C, D, H, I, M, R, T, Z) instances" (`L-1216C47A`), which is
usually 32 or more at once. A `c7i.8xlarge` needs 32 vCPU. The deploy script checks the quota before it creates anything.

## 3. Deploy

Clone the repo and run the scripts from its root. The host clones the repo itself, using a GitHub token it reads from
AWS Systems Manager (the token never appears in the template, the user data, the logs or the repo).

**3.1. A token for the host.** Create a GitHub *fine-grained* token with the shortest expiry that suits you. The host only
needs to read this repository: use *Public repositories (read-only)* if you deploy the public repo, or give it
`Contents: read` on your fork if it is private. Then store it once (hidden prompt, stored as an encrypted SSM parameter):

```powershell
# Windows
powershell -ExecutionPolicy Bypass -File infra\aws\put-github-token.ps1
```
```bash
# Fedora / Linux / macOS
bash infra/aws/put-github-token.sh
```

**3.2. Rehearse, then deploy.** `-WhatIf` / `--dry-run` runs the read-only checks (identity, token, quota, subnet) and
prints what it would do, without writing anything.

```powershell
# Windows
powershell -ExecutionPolicy Bypass -File infra\aws\deploy.ps1 -InstanceType c7i.8xlarge -AutoStopHours 6 -SkipBudget -WhatIf
powershell -ExecutionPolicy Bypass -File infra\aws\deploy.ps1 -InstanceType c7i.8xlarge -AutoStopHours 6 -SkipBudget
```
```bash
# Fedora / Linux / macOS
bash infra/aws/deploy.sh --instance-type c7i.8xlarge --auto-stop-hours 6 --skip-budget --dry-run
bash infra/aws/deploy.sh --instance-type c7i.8xlarge --auto-stop-hours 6 --skip-budget
```

It shows the cost estimate and asks you to type a confirmation (`-Yes` / `--yes` skips it). Useful options:

| Option (PowerShell / bash) | Default | What it does |
|---|---|---|
| `-InstanceType` / `--instance-type` | `g6e.2xlarge` | `c7i.8xlarge`, `c7a.8xlarge`, `m7i.4xlarge`, `m7a.4xlarge` (CPU) or `g6e.2xlarge`, `g6e.xlarge`, `g5.2xlarge`, `g6.2xlarge` (GPU) |
| `-AutoStopHours` / `--auto-stop-hours` | 8 | The host powers itself off this many hours after every boot (EC2 *stops* it). 1 to 72 |
| `-BudgetEmail` / `--budget-email`, or `-SkipBudget` / `--skip-budget` | one is required | An AWS Budgets alert at 50, 80 and 100 percent. Budgets lag by hours and **never stop anything** |
| `-RepoRef` / `--repo-ref` | `main` | Branch or tag the host clones |
| `-RepoUrl` / `--repo-url` | this repo | Use your fork |
| `-ModelTag`, `-FailoverModelTag` / `--model-tag`, `--failover-model-tag` | `qwen3.5:35b`, `qwen3.5:4b` | The Ollama models |
| `-StackName` / `--stack-name` | `bestiary-demo` | CloudFormation stack |

No inbound port is opened: the security group has no ingress rules and you reach the host only through SSM Session
Manager. The instance enforces IMDSv2 with a hop limit of 1, and its role can read exactly one SSM parameter.

**3.3. Wait for the bootstrap** (about 10 minutes on the CPU path; it builds four images, installs k3s, OpenSandbox and
every workload, and pulls the models). `CREATE_COMPLETE` only means "launched". Follow the log until it says `READY`:

```powershell
powershell -ExecutionPolicy Bypass -File infra\aws\present.ps1 -Logs       # Windows
```
```bash
bash infra/aws/present.sh --logs                                           # Fedora / Linux / macOS
```

It ends with `bestiary doctor`: every row should say `ok`. Check it again at any time with `present.ps1 -Doctor`
(`present.sh --doctor`).

**3.4. Warm the models and play.** After every start the models are unloaded; the first request loads them from disk.
Warm both (open a shell in the pod with `present.ps1 -Shell` / `present.sh --shell`):

```bash
for m in qwen3.5:4b qwen3.5:35b; do
  curl -s -o /dev/null -w "$m: %{time_total}s\n" http://ollama:11434/api/generate \
    -d "{\"model\":\"$m\",\"prompt\":\"ok\",\"stream\":false,\"think\":false}"
done
```

Then play (keys and screens: [instructions.md](instructions.md)):

```powershell
powershell -ExecutionPolicy Bypass -File infra\aws\present.ps1            # classic screens
powershell -ExecutionPolicy Bypass -File infra\aws\present.ps1 -Battle    # Pokémon-style screens
```
```bash
bash infra/aws/present.sh            # classic screens
bash infra/aws/present.sh --battle   # Pokémon-style screens
```

Each creature card says **where it runs** (pod and node): that is the point of the demo.

## 4. How it fits together

```
your terminal --SSM Session Manager--> 1 EC2 instance (k3s, no inbound ports)
                                         pod "console":  the game + goose + the forge MCP server + agentgateway (sidecar),
                                                          sharing one volume with the working copy of the code
                                         pods:           Ollama (the model), the A2A reviewer, Agent Router (aigw),
                                                          OpenSandbox (server + a sandbox pod per run), OpenEnv
```

| Piece | Where |
|---|---|
| CloudFormation: instance, role, security group, auto-stop timer, optional budget | [infra/aws/demo-host.yaml](infra/aws/demo-host.yaml) |
| What runs on the host at first boot (and again with `refresh.sh`) | [infra/aws/bootstrap.sh](infra/aws/bootstrap.sh) |
| Kubernetes manifests (kustomize: `base`, `overlays/kind`, `overlays/ec2`, `overlays/ec2-cpu`) | [k8s/](k8s) |
| The game | [bestiary/](bestiary) (engine, encounters, battle screens, sprites, model client) |
| The services the game talks to | [bestiary/services/](bestiary/services), [envs/farolito_env/](envs/farolito_env), [gateway/](gateway), [agent-router/](agent-router) |
| Longer explanation and what was verified | [docs/AWS_DEPLOY.md](docs/AWS_DEPLOY.md), [docs/TRY_IT.md](docs/TRY_IT.md) |

The game has two profiles: `laptop` (default, everything on `127.0.0.1`) and `cloud` (in-cluster service URLs, set by
the console pod with `BESTIARY_PROFILE=cloud`). Every URL can be overridden: see [.env.example](.env.example).

## 5. Operate it

| I want to... | Do this |
|---|---|
| Get a shell in the console pod | `present.ps1 -Shell` / `present.sh --shell` |
| Get a shell on the host | `present.ps1 -Host` / `present.sh --host` |
| Run another branch on the host | On the host (`-Host`): `sudo sed -i 's#^REPO_REF=.*#REPO_REF=<branch>#' /etc/bestiary.env && sudo bash /opt/bestiary/infra/aws/refresh.sh --apply` (about a minute; the console pod restarts) |
| Check which steps are reliable | In the pod: `bestiary gate --runs 50` (agent loop and reviewer). Add `--goose` for goose (about 25 minutes for 20 runs); `--only goose` runs goose alone |
| Record fresh replays | In the pod: `bestiary record` runs every encounter live and saves `replays/` (only real runs are saved) |
| Start a stopped host | `aws ec2 start-instances --instance-ids <id>`; it re-arms the auto-stop timer. Warm the models again (3.4) |
| Run the tests | `uv sync && uv run pytest -q` (about 90 seconds, no network) |

## 6. Stop paying

Pick one, or both:

**Delete it now**

```powershell
powershell -ExecutionPolicy Bypass -File infra\aws\teardown.ps1 -DeleteTokenParameter     # Windows
```
```bash
bash infra/aws/teardown.sh --delete-token-parameter                                       # Fedora / Linux / macOS
```

It deletes the stack (instance, its disk, security group, role, instance profile and budget), then audits that nothing
billable is left and prints `PASS` or `FAIL`. Revoke the GitHub token on GitHub as well.

**Schedule the deletion** (AWS does it for you, even if your laptop is off). EventBridge Scheduler calls CloudFormation
`DeleteStack` at the time you give; half an hour later a second schedule terminates the instance directly, in case the
first call did not get that far. The scheduler and its IAM role cost nothing.

```powershell
powershell -ExecutionPolicy Bypass -File infra\aws\schedule-teardown.ps1 -RunAt 2026-12-01T12:00:00 -TimeZone UTC
powershell -ExecutionPolicy Bypass -File infra\aws\schedule-teardown.ps1 -Status
powershell -ExecutionPolicy Bypass -File infra\aws\schedule-teardown.ps1 -Cancel
```
```bash
bash infra/aws/schedule-teardown.sh --run-at 2026-12-01T12:00:00 --time-zone UTC
bash infra/aws/schedule-teardown.sh --status
bash infra/aws/schedule-teardown.sh --cancel
```

It shows what will be deleted and asks you to type `DESTROY`. What stays afterwards, all free: the SSM parameter with the
token (`teardown ... -DeleteTokenParameter` removes it) and the small `bestiary-teardown-schedule` stack with the IAM role
(`aws cloudformation delete-stack --stack-name bestiary-teardown-schedule`).

Also check, in the console, that no `bestiary-demo` instance, volume or Elastic IP is left in `us-east-1`.

## 7. Extend it

| To add... | Edit |
|---|---|
| A creature (name, stats, skills, and its Pokédex text) | [bestiary/data/creatures.yaml](bestiary/data/creatures.yaml) and a sprite in [bestiary/sprites.py](bestiary/sprites.py) |
| An obstacle and its description for the battle screens | [bestiary/data/obstacles.yaml](bestiary/data/obstacles.yaml) and [bestiary/opponents.py](bestiary/opponents.py) |
| An encounter | [bestiary/encounters.py](bestiary/encounters.py): a function with a live step, then `ctx.attempt(...)`; add it to `ORDER` |
| The AGENTS.md rules goose follows | [upstream/farolito/AGENTS.md](upstream/farolito/AGENTS.md) (a test checks it, see `tests/test_agents_md.py`) |

Rules that keep the demo honest: a step is **LIVE** only when the real call happened and passed; a replay must come from a
real run; anything simulated is labelled **DIDACTIC**. Run `uv run pytest -q` before you open a pull request, and see
[CONTRIBUTING.md](CONTRIBUTING.md).

## 8. What is verified, and what is not

- Verified: the CPU deployment from CloudFormation to `READY` (about 10 minutes), the whole game LIVE in the cluster, the
  battle screens through a real pseudo-terminal, 125 tests.
- Not verified: the GPU instance path (written, never run), a real GitHub pull request in encounter 8 (the demo uses a local
  forge by default), the scripts on macOS and Fedora (they use standard tools; tell us if one breaks).
- Known limit: the deploy scripts need the GitHub token parameter even for a public repository.
