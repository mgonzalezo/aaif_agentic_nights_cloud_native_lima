# Run the Bestiary on a GPU in AWS (k3s, demo only)

The whole game as pods on one EC2 GPU instance, so every step shows the cluster it runs in.
You can redeploy it from this page. It is for a **demo**: there is no public access, and you
delete it when you are done.

> **WARNING: THIS COSTS MONEY UNTIL YOU TEAR IT DOWN.**
> A g6e.2xlarge is about **2.24 USD per hour** (a CPU instance such as c7i.8xlarge, 1.43) (about 54 USD per day), plus about 0.05 USD per hour
> for the disk and the public IPv4 address. Auto-stop only *stops* the instance; the disk keeps
> billing. When you finish, run **teardown** (see the end) and check that it prints `PASS`.

> Status of this page: deployed and rehearsed on a CPU instance on 2026-11-23; the GPU path was
> not run. See "What was verified" at the end, and [TRY_IT.md](TRY_IT.md) to try it step by step.

## 1. What you need

| Need | Detail |
|---|---|
| AWS account, profile with admin-like rights | CloudFormation, EC2, IAM, SSM, Budgets. Examples use `--profile cloud_native_lima`. |
| **GPU quota** | Service Quotas, EC2, "Running On-Demand G and VT instances" (`L-DB2E81BA`). New accounts start at **0**. You need **8 vCPU** for a g6e.2xlarge. Request it first; approval can take from minutes to days. |
| AWS CLI v2 and the **Session Manager plugin** | https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html |
| A GitHub token (only for the real pull request in encounter 8) | Fine-grained token for **two repos**: this one (to clone it if private) and your own `farolito-demo` repo. Contents, Issues and Pull requests read/write. Short expiry. |
| A terminal at least 110 columns wide | The game is a terminal game. |

Request the quota (free):

```bash
aws service-quotas request-service-quota-increase --service-code ec2 \
  --quota-code L-DB2E81BA --desired-value 8 --region us-east-1
```

### Costs (us-east-1, On-Demand, Linux, from the AWS Pricing API on 2026-11-23)

| Instance | GPU | USD/hour | 8 h | 72 h |
|---|---|---|---|---|
| **g6e.2xlarge** (default) | 1x L40S 48 GB | 2.242 | 18 | 161 |
| g6e.xlarge | 1x L40S 48 GB, 32 GiB RAM | 1.861 | 15 | 134 |
| g5.2xlarge | 1x A10G 24 GB | 1.212 | 10 | 87 |
| g6.2xlarge | 1x L4 24 GB | 0.978 | 8 | 70 |

Add about 2 USD per 72 h for the 200 GB gp3 disk and the IPv4 address. The stack also creates an
AWS Budget that e-mails you at 50, 80 and 100 percent. Budgets lag by hours and **never stop
anything**.

### No GPU quota? Use a CPU instance

The GPU quota starts at 0 and approval can take days. The **Standard** on-demand vCPU quota
(`L-1216C47A`) is usually available at once, so the same stack also runs on a CPU instance:

```powershell
powershell infraws\deploy.ps1 -BudgetEmail you@example.com -InstanceType c7i.8xlarge
```

| CPU instance | vCPU / RAM | USD/hour | 72 h |
|---|---|---|---|
| **c7i.8xlarge** | 32 / 64 GiB | 1.428 | 103 |
| c7a.8xlarge | 32 / 64 GiB (AMD) | 1.642 | 118 |
| m7i.4xlarge | 16 / 64 GiB | 0.806 | 58 |
| m7a.4xlarge | 16 / 64 GiB (AMD) | 0.927 | 67 |

It uses plain Ubuntu 24.04 (no GPU driver), skips the NVIDIA steps, and applies
`k8s/overlays/ec2-cpu`: the same pods, with Ollama on the CPU. Bootstrap detects the accelerator
by itself (`nvidia-smi`), and the cards say `(CPU)` or `(GPU)`. **Expect slower, and measure:**
decode speed on a CPU is limited by memory bandwidth, so a mixture-of-experts model such as
`qwen3.5:35b` (about 3B active parameters) is the first candidate, then `9b`, then `4b`. Run
`bestiary gate` and keep only what passes; a step that does not pass is shown as REPLAY. Only
x86 types are offered: some images used here are not confirmed for arm64.

## 2. Architecture

```
 your laptop                          AWS (us-east-1)  one EC2 instance, no inbound ports
 +--------------------+  SSM session  +--------------------------------------------------------+
 | terminal           | ------------> | k3s (single node, NVIDIA runtime + device plugin)      |
 | present.ps1        |  (HTTPS out)  |                                                        |
 +--------------------+               |  pod: console                                          |
                                      |  +--------------------------------------------------+  |
                                      |  | container console: the game, goose, uv, kubectl  |  |
                                      |  | container forge:   MCP server (issues, PRs)      |  |
                                      |  | container agentgateway (sidecar) :3000           |  |
                                      |  | emptyDir /state  = ONE working copy for all three|  |
                                      |  +-----+--------------+----------------------+------+  |
                                      |        | /v1/responses| A2A                  | tools   |
                                      |  +-----v------+  +----v-------+      to GitHub (PR)    |
                                      |  | ollama     |  | reviewer   |                        |
                                      |  | GPU (L40S) |  | -a2a       |                        |
                                      |  | main+small |  +------------+                        |
                                      |  +-----^------+                                        |
                                      |        | priority 0: ollama-main                       |
                                      |  +-----+------+  priority 1: ollama-small (failover)    |
                                      |  | agent-     |                                        |
                                      |  | router     |   opensandbox-server (Helm, Kubernetes |
                                      |  +------------+   runtime) -> one pod per sandbox      |
                                      |  openenv-farolito: OpenEnv environment (reset/step)    |
                                      +--------------------------------------------------------+
```

Nothing listens on a public port. You reach the box only with SSM Session Manager (outbound
HTTPS from the instance). The GitHub token lives in SSM Parameter Store as a SecureString and
becomes a Kubernetes Secret at boot.

## 3. Deploy

```powershell
# 1. Store the GitHub token once (hidden prompt; it is never printed or logged)
powershell infra\aws\put-github-token.ps1

# 2. Preflight + cost estimate + typed confirmation, then CloudFormation
powershell infra\aws\deploy.ps1 -BudgetEmail you@example.com          # add -WhatIf to rehearse

# 3. Follow the bootstrap (20 to 40 minutes: images, 22 GB model pull)
powershell infra\aws\present.ps1 -Logs
```

Bash twins: `bash infra/aws/deploy.sh --budget-email you@example.com` (see `infra/aws/README.md`).
The scripts check your identity, the token parameter and the GPU quota before they create
anything, and ask you to type a confirmation.

Bootstrap is idempotent and logs to `/var/log/bestiary-bootstrap.log` on the host. It ends with
`READY`, `kubectl get nodes,pods -A`, the GPU allocation and `bestiary doctor`.

## 4. What bootstrap installs, and why

Host: NVIDIA driver check (`nvidia-smi`), NVIDIA container toolkit, Docker (to build images), uv,
Helm, **k3s** (pinned, NVIDIA runtime, Traefik off) and the NVIDIA device plugin (so the node
advertises `nvidia.com/gpu: 1`). Then it builds three images, imports them into k3s, installs
OpenSandbox with Helm and applies `k8s/overlays/ec2`.

One short section per project, as it is used here:

- **goose** (agent). The only creature with autonomy. Runs in the console container
  (`goose run --no-session --with-builtin developer`), with Ollama as provider, and edits the working copy.
- **Model Context Protocol (MCP)**. The forge container is an MCP server (`list_issues`,
  `read_issue`, `read_file`, `create_branch`, `create_pull_request`, `delete_branch`). The game calls it with no model in encounter 2.
- **Agent2Agent (A2A)**. The `reviewer-a2a` pod is "another team's" agent. The game reads its Agent Card and delegates the diff.
- **AGENTS.md**. A Markdown file in the toy project that tells any agent how to run the tests.
- **Agent Skills**. `.agents/skills/` in the toy project; the token meter compares loading all skills with progressive disclosure.
- **agentgateway** (gateway for tools). A sidecar in the console pod on `localhost:3000`. Its
  allow-list hides `delete_branch` from `tools/list` and rejects a direct call. Image `v1.7.0`.
- **Agent Router** (gateway for models; formerly Envoy AI Gateway). Standalone `aigw run` in its own
  pod. Encounter 9 sends a request for the main model, then simulates an outage of the main backend
  and shows the answer coming from the small model. It is a **simulated** outage: one GPU holds
  one Ollama pod, so the demo empties the `ollama-main` Service instead of crashing a server.
- **Open Responses** (API specification). Every model call is `POST /v1/responses` to Ollama (version 0.13.3 or later).
- **OpenSandbox** (sandbox). Server and controller from Helm (Kubernetes runtime). Encounter 6 runs `pytest` in a throwaway sandbox pod.
- **OpenEnv** (training environment). `envs/farolito_env` wraps farolito's tests: `POST /reset` returns the issue, `POST /step` applies a patch to a fresh copy and returns a reward of 1.0 or 0.0.

Why **Agent Router standalone** and not the controller: one Deployment instead of three Helm
releases and dozens of CRDs, with the same API objects and the same failover. The cost is no hot
reload (change the ConfigMap, restart the pod). Why OpenSandbox on the **Kubernetes runtime**:
traffic stays pod to pod and nothing exposes the Docker socket. If it misbehaves, the fallback is
the Docker runtime on the host (`uvx opensandbox-server`, see `docs/SETUP.md`).

## 5. How to play

```powershell
powershell infra\aws\present.ps1            # the game, in the console pod
powershell infra\aws\present.ps1 -Doctor    # bestiary doctor
powershell infra\aws\present.ps1 -Shell     # a shell in the console pod
```

Before each live step: **Enter** = run live, **r** = show the replay, **s** = skip. Every card
shows where its creature runs (pod and node). Badges: LIVE (a real call now), REPLAY (a real run
recorded earlier, with date and model), DIDACTIC (an explanation, labelled).

Record real runs as replays (they are your fallback if the instance fails):

```bash
kubectl -n bestiary exec deploy/console -c console -- bestiary record
kubectl -n bestiary cp bestiary/<console-pod>:/app/replays ./replays -c console
```

Gate a model before you trust it live (agent loop and reviewer: 48 of 50 and p95 of 20 s or less;
goose: 45 of 50 and p95 of 75 s or less):

```bash
kubectl -n bestiary exec deploy/console -c console -- bestiary gate --runs 50 --goose
```

## 6. Tear it down

```powershell
powershell infra\aws\teardown.ps1 -DeleteTokenParameter
```

It deletes the stack (instance, disk, security group, role, budget), then audits that nothing
billable is left and prints `PASS` or `FAIL`. Revoke the GitHub token on GitHub too. If you only
stop the instance, the disk keeps billing: tear down.

## 7. The same thing on a laptop with kind and no GPU (myth 3)

You do not need Kubernetes, a GPU or a cloud account to start. Level 0 is `uv run bestiary`. If you
want pods anyway, the **same manifests** run in kind, because the EC2 setup is a kustomize overlay
on a shared base (`k8s/base`):

```bash
uv run bestiary k8s up       # kind cluster, images, k8s/overlays/kind
uv run bestiary play --only 11
uv run bestiary k8s down
```

Differences: the model stays on your host (Ollama), the game runs on your laptop and reaches the
pods through NodePorts, and there is no console pod. See `docs/SETUP.md`.

## 8. What was verified

**Run on a real deployment (2026-11-23, c7i.8xlarge, CPU only, `qwen3.5:35b` with thinking off):**
bootstrap from user data and again by hand, all images built on the host, k3s with every pod Ready,
`bestiary doctor` all `ok`, a stop and start of the instance (the stack recovers by itself in about a
minute), the reliability gate (agent loop 50/50 p95 3.5 s, reviewer 50/50 p95 4.8 s, goose 14/20),
and three full rehearsals of the game with 12 recorded replays (see [TRY_IT.md](TRY_IT.md)).
Encounter 9 observed a real failover from the 35B model to the 4B model, and the game now refuses
to claim one it did not observe. Replays play back offline on a laptop.

**Verified from official docs or source, 2026-11-23 (pins):** k3s `v1.37.2+k3s1`, Helm `v3.22.1`,
Ollama `0.40.16`, Agent Router `v1.3.0`, agentgateway `v1.7.0`, OpenSandbox `release-1.2.1`, goose
`v1.60.1`, OpenEnv `0.14.0`, NVIDIA device plugin chart `0.20.2`, qwen3.5 tags and sizes.

**Not verified:** the GPU path (the NVIDIA steps and the `ec2` overlay were never run: this
deployment was CPU only), a real GitHub pull request (encounter 8 used the local forge),
`present.ps1` (the Session Manager plugin is not installed on the build laptop, so the host was
driven with `aws ssm send-command`), and Graviton (arm64). `ollama ps` showed a small "GPU" share
on this CPU-only host; I did not investigate it and did not rely on it.

**Bugs found only by running it** (all fixed on this branch): `kubectl wait` before the node
registered, a missing buildx on the Ubuntu `docker.io` package, the OpenSandbox chart creating
namespaces and a duplicate `[ingress]` table, the loopback-only forge failing a pod-IP probe, the
router reusing its connection so the simulated outage did nothing (and the game claiming a
failover anyway), and the gateway's rejection arriving as an exception group.
