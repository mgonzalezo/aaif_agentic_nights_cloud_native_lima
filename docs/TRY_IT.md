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
| Instance | `i-0123456789abcdef0`, c7i.8xlarge (32 vCPU, 64 GiB, **no GPU**), Ubuntu 24.04, k3s v1.37.2 |
| Models | `qwen3.5:35b` (main, thinking off) and `qwen3.5:4b` (failover) |
| Code on the host | branch `feat/aws-gpu-demo` |

## 1. One-time setup on your laptop

1. **AWS CLI v2** and the profile `cloud_native_lima` (already working on this laptop).
2. **Session Manager plugin** (needed to open a terminal in the instance; not installed on this
   laptop yet): https://s3.amazonaws.com/session-manager-downloads/plugin/latest/windows/SessionManagerPluginSetup.exe
   then close and reopen your terminal and check `session-manager-plugin --version`.
3. A terminal at least **110 columns** wide (Windows Terminal is fine), font 16 pt or more.
4. This repo, on branch `feat/aws-gpu-demo`: `git checkout feat/aws-gpu-demo`.

## 2. Wake the host up

The host stops by itself (auto-stop) and is `stopped` when you come back. Start it:

```powershell
aws ec2 start-instances --instance-ids i-0123456789abcdef0 --region us-east-1 --profile cloud_native_lima
aws ec2 wait instance-running --instance-ids i-0123456789abcdef0 --region us-east-1 --profile cloud_native_lima
```

Tested: after a stop and start, k3s and every pod came back **on their own in about one minute**, and
the 6-hour auto-stop timer was re-armed. The public IP changes; nothing depends on it (SSM only).

Check from the laptop that everything is Ready (needs the plugin):

```powershell
cd C:\Users\xmarc\Documents\Japan\Talks\AAFIF_Nights\aaif_agentic_nights_cloud_native_lima
powershell -ExecutionPolicy Bypass -File .\infra\aws\present.ps1 -InstanceId i-0123456789abcdef0 -Doctor
```

Every row of `bestiary doctor` should say `ok`.

## 3. Warm up the models (important after every start)

A restart unloads the models from memory. The first request loads them from disk: measured for
`qwen3.5:4b` at **28 seconds**; the 22 GB `35b` takes longer (I did not capture the exact figure).
Warm both before you play, otherwise the first live step looks slow:

```powershell
powershell -ExecutionPolicy Bypass -File .\infra\aws\present.ps1 -InstanceId i-0123456789abcdef0 -Shell
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
powershell -ExecutionPolicy Bypass -File .\infra\aws\present.ps1 -InstanceId i-0123456789abcdef0
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
| 5 | goose fixes the bug | **REPLAY** | gate 14/20 (need 18). Live it passed in 1 of 3 rehearsals (44 s) and hit the 75 s cap in 2; the recorded run is a real one |
| 6 | pytest in OpenSandbox (one sandbox pod per run) | LIVE | 2 to 5 s |
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
| `aws ec2 stop-instances --instance-ids i-0123456789abcdef0 --region us-east-1 --profile cloud_native_lima` | Stop now |
| `powershell infra\aws\teardown.ps1 -DeleteTokenParameter` | Delete everything and audit that nothing billable is left. Then revoke the GitHub token on GitHub |

## 9. GPU: does it make sense?

On this evidence, **not for the talk**. The CPU host passes the gate for the agent loop and the
reviewer with a large margin (p95 3.5 s and 4.8 s against 20 s) at about 1.43 USD per hour,
against 2.24 for a g6e.2xlarge. The step that fails the gate is goose (14/20). Its failures were a mix of
wrong edits ("tests still failing") and hitting the 75 s cap (I saw both in the first dozen runs
but did not keep the exact split: the log was lost when the pod restarted), so a GPU would only
fix the slow ones. A GPU is worth one test only if you want a faster goose or a larger model: deploy with
`-InstanceType g6e.2xlarge` (the G/VT quota is now 8 vCPU in both regions) and run the same gate.
