#!/usr/bin/env bash
# Open an SSM Session Manager session on the demo host and run the Bestiary game in the console pod.
# Equivalent of present.ps1. Modes: (default) game | --doctor | --shell | --host | --logs ; --dry-run prints only.
# Needs session-manager-plugin. Make the terminal >= 110 columns BEFORE starting (cannot be forced).
# Git Bash/mintty has no real console for the plugin: use WSL2 or Windows Terminal + present.ps1 on Windows.
set -uo pipefail
export MSYS_NO_PATHCONV=1 AWS_PAGER=""

INSTANCE_ID=""; STACK=bestiary-demo; REGION=us-east-1; PROFILE="${AWS_PROFILE:-cloud_native_lima}"; MODE=game; DRY=false
while [ $# -gt 0 ]; do
  case "$1" in
    --instance-id) INSTANCE_ID=$2; shift 2 ;;
    --stack-name) STACK=$2; shift 2 ;;
    --region) REGION=$2; shift 2 ;;
    --profile) PROFILE=$2; shift 2 ;;
    --doctor) MODE=doctor; shift ;;
    --shell) MODE=shell; shift ;;
    --host) MODE=host; shift ;;
    --logs) MODE=logs; shift ;;
    --battle) BATTLE=true; shift ;;
    --pick) PICK=$2; shift 2 ;;     # choose (you pick the creature, default) | auto (the right one is on the field)
    --lang) LANG_OPT=$2; shift 2 ;;  # es (default) | en
    --dry-run|--whatif) DRY=true; shift ;;
    -h|--help) echo "Usage: $0 [--instance-id i-..] [--stack-name N] [--region R] [--profile P] [--doctor|--shell|--host|--logs] [--battle] [--pick choose|auto] [--lang es|en] [--dry-run]"; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done
command -v aws >/dev/null || { echo "aws CLI not found." >&2; exit 1; }

# Contract with the k8s manifests: namespace bestiary, Deployment console, container console, `bestiary` on PATH.
# /etc/rancher/k3s/k3s.yaml is root-readable, so use `sudo k3s kubectl` (ssm-user has passwordless sudo).
EXEC='sudo k3s kubectl -n bestiary exec -it deploy/console -c console --'
case "$MODE" in
  game)
    EXTRA=""
    [ -n "${PICK:-}" ] && EXTRA="$EXTRA --pick $PICK"
    [ -n "${LANG_OPT:-}" ] && EXTRA="$EXTRA --lang $LANG_OPT"
    if [ "${BATTLE:-false}" = true ]; then REMOTE="$EXEC bestiary play --ui battle$EXTRA"; else REMOTE="$EXEC bestiary play$EXTRA"; fi ;;
  doctor) REMOTE="$EXEC bestiary doctor" ;;
  shell) REMOTE="$EXEC bash" ;;
  logs) REMOTE='sudo tail -n 200 -F /var/log/bestiary-bootstrap.log' ;;
  host) REMOTE="" ;;
esac

if [ -z "$INSTANCE_ID" ]; then
  INSTANCE_ID="$(aws cloudformation describe-stacks --stack-name "$STACK" --query "Stacks[0].Outputs[?OutputKey=='InstanceId'].OutputValue" --output text --profile "$PROFILE" --region "$REGION" 2>/dev/null)"
  if [ -z "$INSTANCE_ID" ] || [ "$INSTANCE_ID" = None ]; then
    echo "Could not resolve InstanceId from stack $STACK in $REGION. Pass --instance-id i-..." >&2
    $DRY && INSTANCE_ID=i-0000000000000000 || exit 1
  fi
fi
printf '%s' "$INSTANCE_ID" | grep -Eq '^i-[0-9a-f]{8,17}$' || { echo "Invalid instance id: $INSTANCE_ID" >&2; exit 2; }

if ! command -v session-manager-plugin >/dev/null 2>&1 && ! [ -x "/c/Program Files/Amazon/SessionManagerPlugin/bin/session-manager-plugin.exe" ]; then
  cat >&2 <<'EOF'
session-manager-plugin is NOT installed.
  Windows (admin): download https://s3.amazonaws.com/session-manager-downloads/plugin/latest/windows/SessionManagerPluginSetup.exe , run it, open a NEW terminal.
  Ubuntu/WSL2   : curl "https://s3.amazonaws.com/session-manager-downloads/plugin/latest/ubuntu_64bit/session-manager-plugin.deb" -o smp.deb && sudo dpkg -i smp.deb
  macOS         : brew install --cask session-manager-plugin
  Verify        : session-manager-plugin --version
  Docs          : https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html
EOF
  $DRY || exit 1
fi
[ -x "/c/Program Files/Amazon/SessionManagerPlugin/bin/session-manager-plugin.exe" ] && PATH="$PATH:/c/Program Files/Amazon/SessionManagerPlugin/bin"

PING="$(aws ssm describe-instance-information --filters "Key=InstanceIds,Values=$INSTANCE_ID" --query 'InstanceInformationList[0].PingStatus' --output text --profile "$PROFILE" --region "$REGION" 2>/dev/null)"
[ "$PING" = Online ] || echo "WARNING: SSM status of $INSTANCE_ID is '${PING:-unknown}' (expected Online). Booting, stopped, or agent not up yet." >&2

COLS="$(tput cols 2>/dev/null || echo 0)"
if [ "${COLS:-0}" -gt 0 ] && [ "$COLS" -lt 110 ]; then echo "Terminal is $COLS columns wide; widen it to at least 110 BEFORE continuing (the game UI needs it)." >&2
else echo "Tip: keep the terminal at least 110 columns wide; resizing later may garble the TUI."; fi

TMP=""; trap '[ -n "$TMP" ] && rm -f "$TMP"' EXIT
if [ "$MODE" = host ]; then
  CMD=(aws ssm start-session --target "$INSTANCE_ID" --profile "$PROFILE" --region "$REGION")
else
  echo "Mode: $MODE   remote command: $REMOTE"
  TMP="$(mktemp "${TMPDIR:-/tmp}/bestiary-ssm-XXXXXXXX.json")"
  printf '{"command":["%s"]}' "$REMOTE" >"$TMP"        # REMOTE has no double quotes or backslashes
  TMP_ARG="$TMP"; command -v cygpath >/dev/null 2>&1 && TMP_ARG="$(cygpath -m "$TMP")"
  CMD=(aws ssm start-session --document-name AWS-StartInteractiveCommand --parameters "file://$TMP_ARG" --target "$INSTANCE_ID" --profile "$PROFILE" --region "$REGION")
fi
echo "${CMD[*]}"
if $DRY; then echo "dry-run: no session started."; exit 0; fi
[ "$MODE" = game ] && echo "If the console pod is not Ready yet the session ends at once: use --logs / --doctor, retry in a minute."
"${CMD[@]}"
