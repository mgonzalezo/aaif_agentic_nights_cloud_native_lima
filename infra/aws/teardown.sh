#!/usr/bin/env bash
# DELETE the Bestiary demo stack and audit that nothing billable is left. Equivalent of teardown.ps1.
# Exit 0 = all PASS, 1 = any FAIL. --dry-run: read-only only (no delete-stack / delete-parameter).
set -uo pipefail
export MSYS_NO_PATHCONV=1 AWS_PAGER=""

STACK=bestiary-demo
REGION=us-east-1
PROFILE="${AWS_PROFILE:-cloud_native_lima}"
TOKEN_PARAM=/bestiary/github-token
DEL_PARAM=false
YES=false
DRY=false

while [ $# -gt 0 ]; do
  case "$1" in
    --stack-name) STACK=$2; shift 2 ;;
    --region) REGION=$2; shift 2 ;;
    --profile) PROFILE=$2; shift 2 ;;
    --token-param) TOKEN_PARAM=$2; shift 2 ;;
    --delete-token-parameter) DEL_PARAM=true; shift ;;
    --yes) YES=true; shift ;;
    --dry-run|--whatif) DRY=true; shift ;;
    -h|--help) echo "Usage: $0 [--stack-name N] [--region R] [--profile P] [--delete-token-parameter] [--yes] [--dry-run]"; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

FAILS=0; WARNS=0; RESULTS=()
say() { printf '%s\n' "$*"; }
awsr() { local r=$1; shift; aws "$@" --profile "$PROFILE" --region "$r"; }   # awsr REGION args...
awsx() { awsr "$REGION" "$@"; }
result() {  # result STATUS NAME [DETAIL]
  RESULTS+=("$(printf '%-5s %s%s' "$1" "$2" "${3:+ - $3}")")
  case "$1" in FAIL) FAILS=$((FAILS+1)) ;; WARN) WARNS=$((WARNS+1)) ;; esac
}
# gone|exists|error : 'gone' only if AWS answers with the expected not-found text
test_gone() {  # test_gone PATTERN aws-args...
  local pat=$1 out rc; shift
  out="$(awsx "$@" 2>&1)"; rc=$?
  if [ $rc -eq 0 ]; then echo exists; elif printf '%s' "$out" | grep -Eq "$pat"; then echo gone; else echo error; fi
}

say "=== Bestiary DEMO host: TEARDOWN (stack $STACK, $REGION) ==="
$DRY && say "dry-run: read-only only. Nothing will be deleted."
command -v aws >/dev/null || { say "aws CLI not found."; exit 1; }
ACCT="$(awsx sts get-caller-identity --query Account --output text 2>/dev/null)" || { say "Cannot call STS with profile '$PROFILE'."; exit 1; }
say "Profile $PROFILE / account $ACCT"

# 1. What will be deleted
if STATUS="$(awsx cloudformation describe-stacks --stack-name "$STACK" --query 'Stacks[0].StackStatus' --output text 2>/dev/null)"; then
  EXISTS=true
  say "Stack status: $STATUS. Resources that will be DELETED:"
  awsx cloudformation list-stack-resources --stack-name "$STACK" --query 'StackResourceSummaries[].[ResourceType,LogicalResourceId,PhysicalResourceId]' --output text
  say "This terminates the instance and deletes its EBS volume (all models and data on it are lost)."
else
  EXISTS=false
  say "Stack $STACK not found in $REGION (already deleted?). Running the audit only."
fi
if $DEL_PARAM; then say "Will ALSO delete SSM parameter $TOKEN_PARAM (the GitHub token)."
else say "NOT deleted: SSM parameter $TOKEN_PARAM is outside the stack. It is free (Standard tier) but holds a SECRET: revoke the GitHub token and/or rerun with --delete-token-parameter."; fi

# 2. Confirm + delete
if $EXISTS; then
  say ""; say "Planned: aws cloudformation delete-stack --stack-name $STACK --region $REGION ; aws cloudformation wait stack-delete-complete ..."
  if $DRY; then say "dry-run: delete-stack skipped."
  else
    if ! $YES; then
      read -r -p "Type the stack name '$STACK' to DELETE it: " ANS
      [ "$ANS" = "$STACK" ] || { say "Aborted."; exit 1; }
    fi
    if awsx cloudformation delete-stack --stack-name "$STACK"; then
      say "Waiting for deletion (instance termination can take a few minutes)..."
      if ! awsx cloudformation wait stack-delete-complete --stack-name "$STACK"; then
        say "Stack did not reach DELETE_COMPLETE. Failed events:"
        awsx cloudformation describe-stack-events --stack-name "$STACK" --max-items 15 \
          --query "StackEvents[?contains(ResourceStatus,'FAILED')].[LogicalResourceId,ResourceStatusReason]" --output text 2>/dev/null
      fi
    else
      say "delete-stack call failed."; result FAIL "delete-stack" "API call failed"
    fi
  fi
fi
if $DEL_PARAM; then
  if $DRY; then say "dry-run: delete-parameter $TOKEN_PARAM skipped."
  elif awsx ssm delete-parameter --name "$TOKEN_PARAM" 2>/dev/null; then say "Deleted parameter $TOKEN_PARAM."
  else say "Parameter $TOKEN_PARAM not deleted (missing or denied)."; fi
fi

# 3. Audit (read-only)
say ""; say "=== Nothing-billable-left audit (read-only) ==="
case "$(test_gone 'does[[:space:]]+not[[:space:]]+exist' cloudformation describe-stacks --stack-name "$STACK")" in
  gone) result PASS "stack $STACK gone in $REGION" ;;
  error) result WARN "stack $STACK state unknown" "describe-stacks failed for another reason (permissions?)" ;;
  *) S2="$(awsx cloudformation describe-stacks --stack-name "$STACK" --query 'Stacks[0].StackStatus' --output text 2>/dev/null)"
     if [ "$S2" = DELETE_COMPLETE ]; then result PASS "stack $STACK gone in $REGION"; else result FAIL "stack $STACK still exists" "$S2"; fi ;;
esac
REGIONS="$(printf '%s\n' "$REGION" us-east-1 us-east-2 | awk '!s[$0]++')"
STATES=pending,running,stopping,stopped,shutting-down
for R in $REGIONS; do
  if I1="$(awsr "$R" ec2 describe-instances --filters Name=tag:Project,Values=bestiary-demo "Name=instance-state-name,Values=$STATES" --query 'Reservations[].Instances[].InstanceId' --output text 2>/dev/null)"; then
    if [ -n "$I1" ]; then result FAIL "non-terminated instance(s) tagged Project=bestiary-demo in $R" "$I1"
    else result PASS "no non-terminated instances tagged Project=bestiary-demo in $R"; fi
  else result WARN "instances in $R" "describe-instances failed (permissions?)"; fi
  I2="$(awsr "$R" ec2 describe-instances --filters "Name=tag:aws:cloudformation:stack-name,Values=$STACK" "Name=instance-state-name,Values=$STATES" --query 'Reservations[].Instances[].InstanceId' --output text 2>/dev/null)"
  [ -n "$I2" ] && result FAIL "non-terminated instance(s) of stack $STACK in $R" "$I2"
  VOK=true
  V1="$(awsr "$R" ec2 describe-volumes --filters Name=tag:Project,Values=bestiary-demo --query 'Volumes[].[VolumeId,State]' --output text 2>/dev/null)" || VOK=false
  V2="$(awsr "$R" ec2 describe-volumes --filters "Name=tag:aws:cloudformation:stack-name,Values=$STACK" --query 'Volumes[].[VolumeId,State]' --output text 2>/dev/null)" || VOK=false
  VV="$(printf '%s\n%s\n' "$V1" "$V2" | grep -Ev 'deleting|deleted|^[[:space:]]*$' | sort -u | tr '\n' ';')"
  if [ -n "$VV" ]; then result FAIL "EBS volume(s) with Project tag / stack tag in $R" "$VV"
  elif ! $VOK; then result WARN "EBS volumes in $R" "describe-volumes failed (permissions?)"
  else result PASS "no EBS volumes tagged Project=bestiary-demo in $R"; fi
  VA="$(awsr "$R" ec2 describe-volumes --filters Name=status,Values=available --query 'Volumes[].VolumeId' --output text 2>/dev/null)"
  [ -n "$VA" ] && result WARN "unattached (available) EBS volumes in $R (untagged, maybe not ours; they bill)" "$VA"
  if EA="$(awsr "$R" ec2 describe-addresses --query 'Addresses[].[PublicIp,AllocationId,AssociationId]' --output text 2>/dev/null)"; then
    FREE="$(printf '%s\n' "$EA" | awk -F'\t' 'NF>=3 && $3=="None"{printf "%s ", $1}')"
    if [ -n "$FREE" ]; then result FAIL "unassociated Elastic IP(s) in $R (billed)" "$FREE"
    else result PASS "no unassociated Elastic IPs in $R"; fi
  else result WARN "Elastic IPs in $R" "describe-addresses failed (permissions?)"; fi
done
BN="$STACK-credits-cap"
case "$(test_gone 'NotFound' budgets describe-budget --account-id "$ACCT" --budget-name "$BN")" in
  gone) result PASS "budget $BN not present" ;;
  exists) result FAIL "budget $BN still exists" ;;
  *) result WARN "budget $BN state unknown" "describe-budget failed for another reason (permissions?)" ;;
esac
if awsx ssm get-parameter --name "$TOKEN_PARAM" --query Parameter.Type --output text >/dev/null 2>&1; then
  result WARN "SSM parameter $TOKEN_PARAM still exists ($REGION)" "holds a secret; revoke the GitHub token or use --delete-token-parameter"
else result PASS "SSM parameter $TOKEN_PARAM not present in $REGION"; fi

for line in "${RESULTS[@]}"; do say "$line"; done
say ""
if [ $FAILS -eq 0 ]; then say "RESULT: PASS ($WARNS warning(s))"
else say "RESULT: FAIL ($FAILS failure(s), $WARNS warning(s)) - fix manually in the console."; fi
cat <<'EOF'

AWS Budgets note: the stack's budget is deleted with the stack. Budget and billing data lag by up to ~24 h,
so look at Billing > Cost Explorer the next day to confirm the final spend. Budgets only alert; they never stop anything.
This audit only checks us-east-1 and us-east-2 (the allowed regions).
EOF
$DRY && say "dry-run: audit ran read-only; nothing was deleted."
[ $FAILS -gt 0 ] && exit 1
exit 0
