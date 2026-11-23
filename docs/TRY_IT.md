# Try it yourself (step by step)

State of the demo host on 2026-11-23 (the day it was built and tested). Everything below was run
for real unless it says "not tested".

> **COST WARNING.** The host is a **c7i.8xlarge (about 1.48 USD per hour, with disk and IPv4)**. It
> stops itself 6 hours after every boot (the OS powers off and EC2 *stops* it). A stopped host
> still bills for its 200 GB disk (about 0.02 USD per hour). Only `teardown` removes everything.
> When you are done: `powershell infra\aws\teardown.ps1 -DeleteTokenParameter` and check it says `PASS`.

| What | Value |
|---|---|
| Stack, region | `bestiary-demo`, `us-east-1` (AWS profile `cloud_native_lima`) |
| Instance | c7i.8xlarge (32 vCPU, 64 GiB, **no GPU**), Ubuntu 24.04, k3s v1.37.2. **Deleted on 2026-11-23 at the end of the day: redeploy it (section 2).** The GitHub token parameter `/bestiary/github-token` was kept |
| Models | `qwen3.5:35b` (main, thinking off) and `qwen3.5:4b` (failover) |
| Code on the host | branch `feat/aws-gpu-demo` |

## 1. One-time setup on your laptop

1. **AWS CLI v2** and the profile `cloud_native_lima` (already working on this laptop).
2. **Session Manager plugin** (needed to open a terminal in the instance; not installed on this
   laptop yet): https://s3.amazonaws.com/session-manager-downloads/plugin/latest/windows/SessionManagerPluginSetup.exe
   then close and reopen your terminal and check `session-manager-plugin --version`.
3. A terminal at least **110 columns** wide (Windows Terminal is fine), font 16 pt or more.
4. This repo, on branch `feat/aws-gpu-demo`: `git checkout feat/aws-gpu-demo`.

## 2. Redeploy the host (about 20 minutes, about 0.5 USD to get ready)

The host was deleted (`teardown`) after the first day of testing, so tomorrow starts with a deploy.
The GitHub token parameter is still in AWS, so you do not need to create it again.

```powershell
cd C:\Users\xmarc\Documents\Japan\Talks\AAFIF_Nights\aaif_agentic_nights_cloud_native_lima
git checkout feat/aws-gpu-demo
powershell -ExecutionPolicy Bypass -File .\infra\aws\deploy.ps1 -InstanceType c7i.8xlarge -AutoStopHours 6 -RepoRef feat/aws-gpu-demo -SkipBudget
```

It shows the cost estimate and asks you to type a confirmation. Add `-Yes` to skip the question, or
`-BudgetEmail <address>` instead of `-SkipBudget` if you want the alerts.

What happens by itself afterwards: the instance boots, clones the repo (with the stored token), builds the
four images, installs k3s, OpenSandbox and every workload, and downloads the two models. In the first day's
test this took about 20 minutes. **This will be the first deploy that runs the whole path from the user data
with no manual fixes** (on day one the bootstrap was fixed and re-run by hand several times), so watch it:

```powershell
powershell -ExecutionPolicy Bypass -File .\infra\aws\present.ps1 -Logs    # needs the Session Manager plugin
```

It is finished when the log says `READY` and shows `bestiary doctor` with every row `ok`. If it stops with
`FAILED`, send me the last 30 lines of `/var/log/bestiary-bootstrap.log` (or ask me to read it with
`aws ssm send-command`).

Then check from the laptop:

```powershell
powershell -ExecutionPolicy Bypass -File .\infra\aws\present.ps1 -Doctor
```

## 3. Warm up the models (important after every start)

A restart unloads the models from memory. The first request loads them from disk: measured for
`qwen3.5:4b` at **28 seconds**; the 22 GB `35b` takes longer (I did not capture the exact figure).
Warm both before you play, otherwise the first live step looks slow:

```powershell
powershell -ExecutionPolicy Bypass -File .\infra\aws\present.ps1 -Shell
```
then, inside the console pod:
```bash
for m in qwen3.5:4b qwen3.5:35b; do
  curl -s -o /dev/null -w "$m: %{time_total}s\n" http://ollama:11434/api/generate \
    -d "{\"model\":\"$m\",\"prompt\":\"ok\",\"stream\":false,\"think\":false}"
done
exit
```
When warm, each answers in 1 to 2 seconds.

## 4. Play

```powershell
powershell -ExecutionPolicy Bypass -File .\infra\aws\present.ps1
```

Before each step: **Enter** = run live, **r** = show the replay, **s** = skip. Each creature card
says where it runs (pod and node). Expected badges (measured in three full rehearsals):

| # | Step | Badge | Measured |
|---|---|---|---|
| 0 | The lab | - | - |
| 1 | AGENTS.md | LIVE | instant |
| 2 | MCP with no model, then the agent loop | LIVE | 1 s, 3 s |
| 3 | agentgateway hides `delete_branch`, rejects a direct call | LIVE | error -32602 "unknown resource" |
| 4 | Agent Skills token meter | LIVE | instant |
| 5 | goose fixes the bug | LIVE or **REPLAY** | Live it must also pass the tests (since commit b945c2c): gate 14/20, and 1 of 3 attempts in the last recording. If it does not, the step falls back to a real recorded run and says so |
| 6 | pytest in OpenSandbox (one sandbox pod per run) | LIVE | 2 to 5 s, `2 passed` |
| 7 | A2A review over Open Responses | LIVE | about 4 s |
| 8 | PR through the gateway | LIVE (local forge) | instant. A real GitHub PR is optional, see section 6 |
| 9 | Agent Router failover (35b to 4b) | LIVE | about 15 s. The outage is **simulated** |
| 10 | OpenEnv reset/step, reward 1.0 | LIVE | 0.2 s |
| K8s | `kubectl get pods`, `tools/list` in-cluster | LIVE | instant |

A whole run takes 71 to 103 seconds of machine time without your pauses.

Reliability gate (what decides LIVE or REPLAY) on this host: agent loop 50/50 with p95 3.5 s,
reviewer 50/50 with p95 4.8 s (limit 20 s each); goose 14/20 with p95 75 s. Re-run it any time:
```bash
# inside the console pod (present.ps1 -Shell)
bestiary gate --runs 50            # agent loop + reviewer
bestiary gate --runs 20 --goose    # also goose (about 15 minutes)
```

## 5. Offline fallback on your laptop (no AWS, no GPU, no network)

```powershell
uv sync
uv run bestiary play --replay-only
```

The 12 recorded real runs are in `replays/` (recorded 2026-11-23 on this host with `qwen3.5:35b`).
Each is shown with a REPLAY badge, its date and its model. Steps without a recording are DIDACTIC and
say so.

## 6. Optional: a real GitHub pull request (encounter 8). Not tested yet

Needs a demo repo and a token that can write to it.

1. Create a fine-grained token for **this repo and `farolito-demo`**: Contents, Issues and Pull
   requests read/write. (The token stored for the host today only reads this repo.)
2. On your laptop: `uv run bestiary github-setup mgonzalezo/farolito-demo` (note the issue number).
3. Replace the token: `powershell infra\aws\put-github-token.ps1 -Overwrite` (check `-?` for the exact switch).
4. On the host, pass the repo and issue to bootstrap: edit `/etc/bestiary.env` (`BESTIARY_GITHUB_ISSUE=<n>`)
   and run `sudo bash /opt/bestiary/infra/aws/refresh.sh --apply` through a `-Host` session.
5. Close the PR and branch after each rehearsal.

## 7. If something breaks

| Symptom | Do this |
|---|---|
| A row of `bestiary doctor` is `missing` | `kubectl -n bestiary get pods` (in `-Shell`), then `kubectl -n bestiary logs deploy/<name>` |
| First live step is slow | The models were cold: section 3 |
| Code changed on GitHub | On the host: `sudo bash /opt/bestiary/infra/aws/refresh.sh --apply` (about 1 minute, idempotent) |
| Bootstrap log | `present.ps1 -Logs`, or on the host `/var/log/bestiary-bootstrap.log` |
| Agent Router evidence | In the console pod: `curl -s http://agent-router:1064/metrics \| grep request_duration_seconds_count` |
| Goose fails live | Expected (14/20). Press `r` for the real recorded run |

## 8. Stop paying

| Command | Effect |
|---|---|
| (nothing) | Auto-stop powers the host off 6 hours after boot. Disk still bills (about 0.02 USD/h) |
| `aws ec2 stop-instances --instance-ids <id from the deploy output> --region us-east-1 --profile cloud_native_lima` | Stop now (the stack and disk stay, so you can start it again) |
| `powershell infra\aws\teardown.ps1 -DeleteTokenParameter` | Delete everything and audit that nothing billable is left. Then revoke the GitHub token on GitHub |

## 9. GPU: does it make sense?

On this evidence, **not for the talk**. The CPU host passes the gate for the agent loop and the
reviewer with a large margin (p95 3.5 s and 4.8 s against 20 s) at about 1.43 USD per hour,
against 2.24 for a g6e.2xlarge. The step that fails the gate is goose (14/20). Its failures were a mix of
wrong edits ("tests still failing") and hitting the 75 s cap (I saw both in the first dozen runs
but did not keep the exact split: the log was lost when the pod restarted), so a GPU would only
fix the slow ones. A GPU is worth one test only if you want a faster goose or a larger model: deploy with
`-InstanceType g6e.2xlarge` (the G/VT quota is now 8 vCPU in both regions) and run the same gate.
