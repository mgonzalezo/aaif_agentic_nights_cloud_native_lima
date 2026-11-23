#!/usr/bin/env bash
# Deploy the DEMO-ONLY Bestiary GPU host (infra/aws/demo-host.yaml). Equivalent of deploy.ps1.
# --dry-run runs read-only checks and prints the planned write command; it never writes to AWS.
set -uo pipefail
export MSYS_NO_PATHCONV=1 AWS_PAGER=""

REGION=us-east-1
PROFILE="${AWS_PROFILE:-cloud_native_lima}"
INSTANCE_TYPE=g6e.2xlarge
MODEL_TAG="qwen3.5:35b"
FAILOVER_TAG="qwen3.5:4b"
DEMO_REPO="mgonzalezo/farolito-demo"
DEMO_ISSUE=""
AUTOSTOP=8
BUDGET_EMAIL=""
STACK=bestiary-demo
REPO_REF=main
REPO_URL=https://github.com/mgonzalezo/aaif_agentic_nights_cloud_native_lima
TOKEN_PARAM=/bestiary/github-token
SKIP_BUDGET=false
YES=false
DRY=false
EXPECTED_ACCOUNT=000000000000
QUOTA_CODE=L-DB2E81BA   # set per instance type below (GPU: G/VT, CPU: Standard)
QUOTA_NAME=G/VT

usage() {
  cat <<EOF
Usage: $0 --budget-email you@example.com [options]
  --region R (us-east-1|us-east-2)   --profile P   --instance-type T (g6e.2xlarge|g6e.xlarge|g5.2xlarge|g6.2xlarge|c7i.8xlarge|m7i.4xlarge|c7a.8xlarge|m7a.4xlarge)
  --model-tag T   --failover-model-tag T   --demo-repo OWNER/NAME   --demo-issue N   --auto-stop-hours N (1-72)   --stack-name N   --repo-ref R
  --repo-url U   --token-param NAME   --skip-budget   --yes (no typed confirmation)   --dry-run
EOF
}
while [ $# -gt 0 ]; do
  case "$1" in
    --region) REGION=$2; shift 2 ;;
    --profile) PROFILE=$2; shift 2 ;;
    --instance-type) INSTANCE_TYPE=$2; shift 2 ;;
    --model-tag) MODEL_TAG=$2; shift 2 ;;
    --failover-model-tag) FAILOVER_TAG=$2; shift 2 ;;
    --demo-repo) DEMO_REPO=$2; shift 2 ;;
    --demo-issue) DEMO_ISSUE=$2; shift 2 ;;
    --auto-stop-hours) AUTOSTOP=$2; shift 2 ;;
    --budget-email) BUDGET_EMAIL=$2; shift 2 ;;
    --stack-name) STACK=$2; shift 2 ;;
    --repo-ref) REPO_REF=$2; shift 2 ;;
    --repo-url) REPO_URL=$2; shift 2 ;;
    --token-param) TOKEN_PARAM=$2; shift 2 ;;
    --skip-budget) SKIP_BUDGET=true; shift ;;
    --yes) YES=true; shift ;;
    --dry-run|--whatif) DRY=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 2 ;;
  esac
done

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE="$HERE/demo-host.yaml"
TEMPLATE_ARG="$TEMPLATE"
# Git Bash: native aws.exe needs a Windows path (C:/...), not /c/...
command -v cygpath >/dev/null 2>&1 && TEMPLATE_ARG="$(cygpath -m "$TEMPLATE")"
WOULD_STOP=false

declare -A VCPU=( [g6e.xlarge]=4 [g6e.2xlarge]=8 [g5.2xlarge]=8 [g6.2xlarge]=8 [c7i.8xlarge]=32 [m7i.4xlarge]=16 [c7a.8xlarge]=32 [m7a.4xlarge]=16 )
declare -A PRICE=( [g6e.2xlarge]=2.242 [g6e.xlarge]=1.861 [g5.2xlarge]=1.212 [g6.2xlarge]=0.978 [c7i.8xlarge]=1.428 [m7i.4xlarge]=0.806 [c7a.8xlarge]=1.642 [m7a.4xlarge]=0.927 )  # us-east-1 USD/h, hard-coded
EXTRA=0.05

say() { printf '%s\n' "$*"; }
awsx() { aws "$@" --profile "$PROFILE" --region "$REGION"; }
stop_here() {
  say "STOP: $1"
  if $DRY; then say "  (dry-run: continuing so you can see the rest of the plan)"; WOULD_STOP=true; return 0; fi
  exit "${2:-1}"
}

say "=== Bestiary DEMO host: deploy (demo only - delete it after the talk) ==="
$DRY && say "dry-run: read-only checks only, NO write calls to AWS."
command -v aws >/dev/null || { say "aws CLI not found on PATH."; exit 1; }
[ -n "${VCPU[$INSTANCE_TYPE]:-}" ] || { say "Unsupported instance type $INSTANCE_TYPE"; exit 2; }
case "$INSTANCE_TYPE" in g*) ;; *) QUOTA_CODE=L-1216C47A; QUOTA_NAME=Standard ;; esac
case "$REGION" in us-east-1|us-east-2) ;; *) stop_here "Region must be us-east-1 or us-east-2 (got $REGION)." ;; esac
case "$AUTOSTOP" in ''|*[!0-9]*) stop_here "auto-stop-hours must be 1-72." ;; *) { [ "$AUTOSTOP" -ge 1 ] && [ "$AUTOSTOP" -le 72 ]; } || stop_here "auto-stop-hours must be 1-72." ;; esac
if [ -z "$BUDGET_EMAIL" ] && ! $SKIP_BUDGET; then stop_here "Pass --budget-email you@example.com (AWS Budgets alerts), or --skip-budget."; fi
[ -f "$TEMPLATE" ] || stop_here "Template not found: $TEMPLATE"

# 1. Identity
ACCT="$(awsx sts get-caller-identity --query Account --output text 2>/dev/null)" || ACCT=""
[ -n "$ACCT" ] || stop_here "Cannot call STS with profile '$PROFILE'. Check credentials."
ARN="$(awsx sts get-caller-identity --query Arn --output text 2>/dev/null)"
say "Profile : $PROFILE"; say "Region  : $REGION"; say "Account : $ACCT"; say "Caller  : $ARN"
[ "$ACCT" = "$EXPECTED_ACCOUNT" ] || say "WARNING: expected account $EXPECTED_ACCOUNT, got $ACCT."

# 2. GitHub token parameter exists (existence only: no --with-decryption, only Type is queried)
if PTYPE="$(awsx ssm get-parameter --name "$TOKEN_PARAM" --query Parameter.Type --output text 2>/dev/null)"; then
  if [ "$PTYPE" = SecureString ]; then say "Token parameter: $TOKEN_PARAM (SecureString) exists."
  else stop_here "Parameter $TOKEN_PARAM exists but is type '$PTYPE', expected SecureString."; fi
else
  say "GitHub token parameter $TOKEN_PARAM NOT found in $REGION."
  say "  Create it once (prompts without echo):"
  say "    bash infra/aws/put-github-token.sh --region $REGION --profile $PROFILE"
  stop_here "token parameter missing."
fi

# 3. G/VT quota
NEED="${VCPU[$INSTANCE_TYPE]}"
if QUOTA="$(awsx service-quotas get-service-quota --service-code ec2 --quota-code "$QUOTA_CODE" --query Quota.Value --output text 2>/dev/null)"; then
  say "$QUOTA_NAME on-demand vCPU quota ($QUOTA_CODE) in $REGION: $QUOTA ; $INSTANCE_TYPE needs $NEED."
  if awk -v q="$QUOTA" -v n="$NEED" 'BEGIN{exit !(q+0 < n+0)}'; then
    say "Quota request history (Status Desired Id):"
    awsx service-quotas list-requested-service-quota-change-history-by-quota --service-code ec2 --quota-code "$QUOTA_CODE" \
      --query 'RequestedQuotas[].[Status,DesiredValue,Id]' --output text 2>/dev/null
    stop_here "quota too low ($QUOTA < $NEED). Wait for the pending request (CASE_OPENED/PENDING) or try the other region."
  fi
else
  stop_here "Could not read quota $QUOTA_CODE (service-quotas:GetServiceQuota denied?)."
fi

# 4. Default VPC + subnet in an AZ that offers the type
VPC="$(awsx ec2 describe-vpcs --filters Name=is-default,Values=true --query 'Vpcs[0].VpcId' --output text 2>/dev/null)"
{ [ -n "$VPC" ] && [ "$VPC" != None ]; } || stop_here "No default VPC in $REGION."
AZS="$(awsx ec2 describe-instance-type-offerings --location-type availability-zone --filters "Name=instance-type,Values=$INSTANCE_TYPE" --query 'InstanceTypeOfferings[].Location' --output text 2>/dev/null)"
SUBNET=""; AZ=""
while read -r az sid; do
  [ -n "$az" ] || continue
  case " $(echo $AZS) " in *" $az "*) AZ=$az; SUBNET=$sid; break ;; esac
done < <(awsx ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC" Name=default-for-az,Values=true --query 'Subnets[].[AvailabilityZone,SubnetId]' --output text 2>/dev/null | sort)
if [ -z "$SUBNET" ]; then stop_here "No default-VPC subnet in an AZ offering $INSTANCE_TYPE (offered in: $AZS)."
else say "VPC $VPC ; subnet $SUBNET in $AZ (offers $INSTANCE_TYPE)."; fi

# Existing stack?
if ST="$(awsx cloudformation describe-stacks --stack-name "$STACK" --query 'Stacks[0].StackStatus' --output text 2>/dev/null)"; then
  say "Stack $STACK already exists (status $ST)."
  case "$ST" in *ROLLBACK_COMPLETE*|CREATE_FAILED|DELETE_FAILED) stop_here "Stack is in $ST; run infra/aws/teardown.sh first." ;; esac
fi

# 5. Cost estimate
RATE="$(awk -v p="${PRICE[$INSTANCE_TYPE]}" -v e="$EXTRA" 'BEGIN{printf "%.3f", p+e}')"
say ""
say "--- Cost estimate (hard-coded us-east-1 on-demand list prices; other regions may differ) ---"
say "  $INSTANCE_TYPE : ${PRICE[$INSTANCE_TYPE]} USD/h compute + $EXTRA USD/h EBS/IPv4 = $RATE USD/h"
awk -v r="$RATE" -v h="$AUTOSTOP" 'BEGIN{printf "  AutoStopHours %3d h : ~%7.2f USD  (auto-stop is OS poweroff = STOP; EBS keeps billing until teardown)\n", h, r*h}'
awk -v r="$RATE" 'BEGIN{printf "  Left running 72 h    : ~%7.2f USD\n", r*72}'
awk -v r="$RATE" 'BEGIN{printf "  300 USD credits cap  : reached after ~%d h of running time\n", int(300/r)}'
say "  Stopped instance: only the 200 GB gp3 volume bills (~0.02 USD/h) until you run teardown."
say "  Budgets alerts lag by hours and are NOT a hard cap: tear down yourself."

# 6. Plan + confirmation
if $SKIP_BUDGET; then CB=false; else CB=true; fi
DEPLOY=(cloudformation deploy --template-file "$TEMPLATE_ARG" --stack-name "$STACK"
  --capabilities CAPABILITY_IAM --no-fail-on-empty-changeset --tags Project=bestiary-demo
  --parameter-overrides "InstanceType=$INSTANCE_TYPE" "AutoStopHours=$AUTOSTOP" "ModelTag=$MODEL_TAG"
  "FailoverModelTag=$FAILOVER_TAG" "GitHubDemoRepo=$DEMO_REPO" "GitHubDemoIssue=$DEMO_ISSUE" "RepoUrl=$REPO_URL" "RepoRef=$REPO_REF" "GitHubTokenParameterName=$TOKEN_PARAM"
  "VpcId=$VPC" "SubnetId=$SUBNET" "BudgetEmail=${BUDGET_EMAIL:-none@example.com}" "CreateBudget=$CB"
  --profile "$PROFILE" --region "$REGION")
say ""; say "Planned command:"; say "  aws ${DEPLOY[*]}"
if $DRY; then
  $WOULD_STOP && say "" && say "dry-run: a real run would have STOPPED at a check above."
  say "dry-run: nothing was created."; exit 0
fi
if ! $YES; then
  read -r -p "Type the stack name '$STACK' to create billable GPU resources (anything else aborts): " ANS
  [ "$ANS" = "$STACK" ] || { say "Aborted."; exit 1; }
fi

# 7. Deploy (waits for CREATE_COMPLETE; IAM role is unnamed so CAPABILITY_IAM is enough)
say ""; say "Deploying (takes a few minutes; this does NOT wait for the 20+ min bootstrap)..."
if ! aws "${DEPLOY[@]}"; then
  say "Deploy FAILED. Recent failed stack events:"
  awsx cloudformation describe-stack-events --stack-name "$STACK" --max-items 12 \
    --query "StackEvents[?contains(ResourceStatus,'FAILED')].[LogicalResourceId,ResourceStatusReason]" --output text
  say "Clean up with: bash infra/aws/teardown.sh --stack-name $STACK --region $REGION"
  exit 1
fi

# 8. Outputs
say ""; say "=== Stack outputs ==="
awsx cloudformation describe-stacks --stack-name "$STACK" --query 'Stacks[0].Outputs[].[OutputKey,OutputValue]' --output text
cat <<EOF

Next:
  1. Watch bootstrap (20+ min; k3s + model pull):
       bash infra/aws/present.sh --stack-name $STACK --region $REGION --logs
  2. When the console pod is Ready:  bash infra/aws/present.sh --stack-name $STACK --region $REGION
     (needs session-manager-plugin; terminal at least 110 columns wide; prefer WSL or Windows Terminal PowerShell over mintty)
  3. AFTER THE TALK:  bash infra/aws/teardown.sh --stack-name $STACK --region $REGION
EOF
