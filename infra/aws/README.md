# infra/aws - DEMO-ONLY GPU host for the Agentic Bestiary

> **THE HOST COSTS ~2.3 USD/HOUR (g6e.2xlarge) AND KEEPS BILLING UNTIL THE STACK IS DELETED.
> AUTO-STOP ONLY STOPS THE INSTANCE (EBS STILL BILLS). RUN `teardown` RIGHT AFTER THE TALK. CAP: 300 USD TOTAL.**

One EC2 GPU instance (Deep Learning Ubuntu 24.04 AMI) running k3s. No inbound ports; you reach it
only through SSM Session Manager. Budget alerts (50/80/100 % actual, 100 % forecast) go to your e-mail.

| File | What it does |
|---|---|
| `demo-host.yaml` | CloudFormation: instance, IAM role, no-ingress SG, auto-stop timer, account budget |
| `put-github-token.ps1/.sh` | One-off: stores the read-only GitHub token as an SSM SecureString (hidden prompt) |
| `deploy.ps1/.sh` | Preflight (identity, token, G/VT quota, AZ), cost estimate, typed confirm, `cloudformation deploy` |
| `present.ps1/.sh` | SSM session into the console pod (`-Doctor`, `-Shell`, `-Host`, `-Logs` modes) |
| `teardown.ps1/.sh` | Delete the stack, then audit that nothing billable is left (PASS/FAIL exit code) |
| `bootstrap.sh` | Runs on the host from user data: NVIDIA runtime, k3s, Helm, device plugin, images, OpenSandbox, `kubectl apply -k k8s/overlays/ec2`, model pull |
| `refresh.sh` | On the host: pull the latest commit, `--apply` re-runs bootstrap (about 1 minute) |
| `opensandbox-values.yaml` | Helm values for the OpenSandbox server (Kubernetes runtime) |

## Order of use
1. Install `session-manager-plugin` on the laptop (present script prints how). Terminal >= 110 columns.
2. `powershell infra\aws\put-github-token.ps1` (fine-grained PAT for this repo and your `farolito-demo` repo: Contents, Issues and Pull requests read/write; short expiry).
3. `powershell infra\aws\deploy.ps1 -BudgetEmail you@example.com -DemoIssue <N>` (`<N>` = issue number printed by `uv run bestiary github-setup <you>/farolito-demo`; without it, encounter 8 uses the local forge) (add `-WhatIf` to rehearse; read-only).
4. `powershell infra\aws\present.ps1 -Logs` until bootstrap finishes (20+ min), then `present.ps1` to play.
5. `powershell infra\aws\teardown.ps1 -DeleteTokenParameter` and revoke the token on GitHub.
Bash twins use long options: `bash infra/aws/deploy.sh --budget-email you@example.com --dry-run`.

## Good to know
- The G/VT vCPU quota (L-DB2E81BA) must be >= 8 (4 for g6e.xlarge); deploy stops if it is not.
- No `cfn-signal`: CREATE_COMPLETE only means "launched"; bootstrap output is in `/var/log/bestiary-bootstrap.log`.
- Auto-stop: systemd timer, `AutoStopHours` after every boot (default 8); starting a stopped host re-arms it.
- Budgets lag by hours and never stop anything. The token parameter is NOT removed by the stack.
- Keep `*.sh` files on LF line endings (set `eol=lf` in `.gitattributes`).
