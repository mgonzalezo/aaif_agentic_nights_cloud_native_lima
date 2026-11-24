#!/usr/bin/env bash
# Schedule the DELETION of the demo stack for a fixed date and time (one-time EventBridge Scheduler task).
# At --run-at, AWS itself calls CloudFormation DeleteStack on the demo stack (instance, disk, security group, role,
# instance profile). Half an hour later a second schedule terminates the instance directly (safety net).
# It does not need your laptop to be on. The scheduler costs nothing; a stopped instance still bills for its disk
# until the stack is deleted. Equivalent of schedule-teardown.ps1.
#
#   bash infra/aws/schedule-teardown.sh --run-at 2026-11-27T12:00:00 --time-zone UTC
#   bash infra/aws/schedule-teardown.sh --status
#   bash infra/aws/schedule-teardown.sh --cancel
set -uo pipefail
export MSYS_NO_PATHCONV=1 AWS_PAGER=""

STACK=bestiary-demo
SCHEDULE_STACK=bestiary-teardown-schedule
REGION=us-east-1
PROFILE="${AWS_PROFILE:-cloud_native_lima}"
RUN_AT=""
TZ_NAME=UTC
MODE=schedule
YES=false
DRY=false
HERE="$(cd "$(dirname "$0")" && pwd)"
TEMPLATE="$HERE/teardown-schedule.yaml"

while [ $# -gt 0 ]; do
  case "$1" in
    --run-at) RUN_AT=$2; shift 2 ;;
    --time-zone) TZ_NAME=$2; shift 2 ;;
    --stack-name) STACK=$2; shift 2 ;;
    --schedule-stack-name) SCHEDULE_STACK=$2; shift 2 ;;
    --region) REGION=$2; shift 2 ;;
    --profile) PROFILE=$2; shift 2 ;;
    --status) MODE=status; shift ;;
    --cancel) MODE=cancel; shift ;;
    --yes) YES=true; shift ;;
    --dry-run|--whatif) DRY=true; shift ;;
    -h|--help) sed -n 2,11p "$0"; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

say() { printf '%s\n' "$*"; }
awsx() { aws "$@" --profile "$PROFILE" --region "$REGION"; }
command -v aws >/dev/null || { say "aws CLI not found."; exit 1; }
ACCT="$(awsx sts get-caller-identity --query Account --output text 2>/dev/null)" || { say "Cannot call STS with profile '$PROFILE'. Log in first."; exit 1; }
say "Profile $PROFILE, account $ACCT, region $REGION"

if [ "$MODE" = status ]; then
  say "Schedule stack '$SCHEDULE_STACK':"
  awsx cloudformation describe-stacks --stack-name "$SCHEDULE_STACK" --query 'Stacks[0].[StackStatus,Outputs[0].OutputValue]' --output text 2>&1
  for s in delete-stack terminate-instance; do
    r="$(awsx scheduler get-schedule --name "$SCHEDULE_STACK-$s" --query '[State,ScheduleExpression,ScheduleExpressionTimezone]' --output text 2>/dev/null)" && say "  $s : $r"
  done
  say "Demo stack '$STACK':"
  awsx cloudformation describe-stacks --stack-name "$STACK" --query 'Stacks[0].StackStatus' --output text 2>&1
  exit 0
fi

if [ "$MODE" = cancel ]; then
  say "This deletes the schedule stack '$SCHEDULE_STACK' (the scheduled teardown will NOT run)."
  $DRY && { say "dry-run: nothing deleted."; exit 0; }
  awsx cloudformation delete-stack --stack-name "$SCHEDULE_STACK" && awsx cloudformation wait stack-delete-complete --stack-name "$SCHEDULE_STACK" && say "Schedule removed."
  exit $?
fi

[ -n "$RUN_AT" ] || { say "Pass --run-at, for example --run-at 2026-11-27T12:00:00 --time-zone UTC"; exit 2; }
printf '%s' "$RUN_AT" | grep -Eq '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}$' || { say "--run-at must look like 2026-11-27T12:00:00 (got '$RUN_AT')."; exit 2; }
if [ "$TZ_NAME" = UTC ]; then
  NOW="$(date -u +%Y-%m-%dT%H:%M:%S)"
  [[ "$RUN_AT" > "$NOW" ]] || { say "--run-at $RUN_AT UTC is in the past (now $NOW)."; exit 2; }
fi
# +30 minutes on the same clock (GNU date or BSD date)
BACKUP="$(date -u -d "${RUN_AT/T/ } UTC + 30 minutes" +%Y-%m-%dT%H:%M:%S 2>/dev/null || date -u -j -v+30M -f %Y-%m-%dT%H:%M:%S "$RUN_AT" +%Y-%m-%dT%H:%M:%S 2>/dev/null)"
[ -n "$BACKUP" ] || { say "Cannot compute the safety-net time."; exit 1; }

ST="$(awsx cloudformation describe-stacks --stack-name "$STACK" --query 'Stacks[0].StackStatus' --output text 2>&1)" || { say "Stack '$STACK' not found in $REGION: nothing to schedule. ($ST)"; exit 1; }
INSTANCE="$(awsx cloudformation describe-stacks --stack-name "$STACK" --query "Stacks[0].Outputs[?OutputKey=='InstanceId'].OutputValue" --output text 2>/dev/null)"
printf '%s' "$INSTANCE" | grep -Eq '^i-[0-9a-f]{8,17}$' || { INSTANCE=""; say "No instance id in the stack outputs: the safety net is skipped."; }

say ""
say "=== Scheduled TEARDOWN of '$STACK' ($ST) ==="
say "Deleted by AWS at : $RUN_AT ($TZ_NAME)"
say "Safety net        : $BACKUP ($TZ_NAME) terminates ${INSTANCE:-(none)}"
say "What the delete removes:"
awsx cloudformation list-stack-resources --stack-name "$STACK" --query 'StackResourceSummaries[].[ResourceType,LogicalResourceId,PhysicalResourceId]' --output text
say "The instance disk (all models and data on it) is deleted with it. Not removed: the GitHub token parameter in SSM (free) and this schedule stack (free)."
say "Cancel any time:  bash infra/aws/schedule-teardown.sh --cancel"

CMD=(cloudformation deploy --stack-name "$SCHEDULE_STACK" --template-file "$TEMPLATE" --capabilities CAPABILITY_IAM --no-fail-on-empty-changeset
  --parameter-overrides "StackName=$STACK" "RunAt=$RUN_AT" "BackupRunAt=$BACKUP" "TimeZone=$TZ_NAME" "InstanceId=$INSTANCE" --tags Project=bestiary-demo)
if $DRY; then say ""; say "dry-run: would run: aws ${CMD[*]} --profile $PROFILE --region $REGION"; exit 0; fi
if ! $YES; then
  read -r -p $'\nType DESTROY to schedule the deletion: ' A
  [ "$A" = DESTROY ] || { say "Not confirmed. Nothing scheduled."; exit 1; }
fi
awsx "${CMD[@]}" || { say "Deploy failed."; exit 1; }
say ""
say "Scheduled. Check it with:  bash infra/aws/schedule-teardown.sh --status"
