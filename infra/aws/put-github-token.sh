#!/usr/bin/env bash
# Create the SSM SecureString holding the READ-ONLY GitHub token for the demo host. Equivalent of put-github-token.ps1.
# Prompts without echo; the token goes to AWS via `--cli-input-json file://<private temp file>` (never on a command line),
# and the file is overwritten and removed on exit. Never prints the token. --dry-run: no AWS call, no prompt.
set -uo pipefail
export MSYS_NO_PATHCONV=1 AWS_PAGER=""

REGION=us-east-1
PROFILE="${AWS_PROFILE:-cloud_native_lima}"
NAME=/bestiary/github-token
OVERWRITE=false
DRY=false
while [ $# -gt 0 ]; do
  case "$1" in
    --region) REGION=$2; shift 2 ;;
    --profile) PROFILE=$2; shift 2 ;;
    --name) NAME=$2; shift 2 ;;
    --overwrite) OVERWRITE=true; shift ;;
    --dry-run|--whatif) DRY=true; shift ;;
    -h|--help) echo "Usage: $0 [--region R] [--profile P] [--name /path] [--overwrite] [--dry-run]"; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done
printf '%s' "$NAME" | grep -Eq '^/[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)*$' || { echo "Invalid parameter name: $NAME" >&2; exit 2; }

if $DRY; then
  echo "dry-run: would run: aws ssm put-parameter --cli-input-json file://<private temp file> --profile $PROFILE --region $REGION   (Name=$NAME, Type=SecureString, Overwrite=$OVERWRITE)"
  echo "dry-run: no AWS call, no prompt."; exit 0
fi
command -v aws >/dev/null || { echo "aws CLI not found." >&2; exit 1; }

if ETYPE="$(aws ssm get-parameter --name "$NAME" --query Parameter.Type --output text --profile "$PROFILE" --region "$REGION" 2>/dev/null)" && ! $OVERWRITE; then
  echo "Parameter $NAME already exists ($ETYPE) in $REGION. Rerun with --overwrite to replace it." >&2; exit 1
fi

TMP=""
cleanup() {
  if [ -n "$TMP" ] && [ -f "$TMP" ]; then
    if command -v shred >/dev/null 2>&1; then shred -u "$TMP" 2>/dev/null || rm -f "$TMP"
    else : >"$TMP"; rm -f "$TMP"; fi    # best effort: not guaranteed on SSD / journaled / copy-on-write filesystems
  fi
  unset TOKEN
}
trap cleanup EXIT INT TERM

echo "Paste the GitHub fine-grained token (input hidden). Scope: this repo only, Contents: Read-only, short expiry." >&2
read -rs -p "GitHub token: " TOKEN; echo >&2
printf '%s' "$TOKEN" | grep -Eq '^[A-Za-z0-9_-]{20,255}$' || { echo "Token is empty or has unexpected characters/length (expected github_pat_... or ghp_...). Nothing stored." >&2; exit 1; }
case "$TOKEN" in github_pat_*|ghp_*) ;; *) echo "Note: token does not start with github_pat_ / ghp_ (continuing)." >&2 ;; esac

umask 077
TMP="$(mktemp "${TMPDIR:-/tmp}/bestiary-XXXXXXXX.json")" || exit 1
printf '{"Name":"%s","Description":"Bestiary demo GitHub read-only token (delete after the talk)","Value":"%s","Type":"SecureString","Tier":"Standard","Overwrite":%s}' "$NAME" "$TOKEN" "$OVERWRITE" >"$TMP"
TMP_ARG="$TMP"; command -v cygpath >/dev/null 2>&1 && TMP_ARG="$(cygpath -m "$TMP")"   # Git Bash: aws.exe needs C:/...

if VER="$(aws ssm put-parameter --cli-input-json "file://$TMP_ARG" --query Version --output text --profile "$PROFILE" --region "$REGION")"; then
  echo "Stored $NAME (SecureString, aws/ssm key, version $VER) in $REGION."
  echo "Remember: delete it after the talk (teardown.sh --delete-token-parameter) and revoke the token on GitHub."
else
  echo "put-parameter failed (see AWS message above; value was not printed)." >&2; exit 1
fi
