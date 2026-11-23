<#
.SYNOPSIS
  Deploy the DEMO-ONLY Bestiary GPU host (infra/aws/demo-host.yaml).
.DESCRIPTION
  Read-only preflight (identity, GitHub token parameter, G/VT quota, subnet/AZ),
  cost estimate, typed confirmation, then `aws cloudformation deploy`.
  -WhatIf runs the read-only checks and prints the planned write command; it never writes to AWS.
.EXAMPLE
  powershell infra\aws\deploy.ps1 -BudgetEmail me@example.com
#>
param(
  [string]$Region = 'us-east-1',
  [string]$Profile = $(if ($env:AWS_PROFILE) { $env:AWS_PROFILE } else { 'cloud_native_lima' }),
  [ValidateSet('g6e.2xlarge', 'g6e.xlarge', 'g5.2xlarge', 'g6.2xlarge')]
  [string]$InstanceType = 'g6e.2xlarge',
  [string]$ModelTag = 'qwen3.5:35b',
  [string]$FailoverModelTag = 'qwen3.5:4b',
  [string]$DemoRepo = 'mgonzalezo/farolito-demo',   # repo that receives the real PR (encounter 8)
  [string]$DemoIssue = '',                          # its issue number (bestiary github-setup); empty = local forge
  [ValidateRange(1, 72)]
  [int]$AutoStopHours = 8,
  [string]$BudgetEmail,
  [string]$StackName = 'bestiary-demo',
  [string]$RepoRef = 'main',
  [string]$RepoUrl = 'https://github.com/mgonzalezo/aaif_agentic_nights_cloud_native_lima',
  [string]$TokenParameterName = '/bestiary/github-token',
  [switch]$SkipBudget,
  [switch]$Yes,
  [switch]$WhatIf
)

$ErrorActionPreference = 'Continue'
$ExpectedAccount = '000000000000'
$QuotaCode = 'L-DB2E81BA'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Template = Join-Path $Here 'demo-host.yaml'

# vCPUs per type, and us-east-1 on-demand USD/hour (hard-coded estimate, not a live price).
$VCpu = @{ 'g6e.xlarge' = 4; 'g6e.2xlarge' = 8; 'g5.2xlarge' = 8; 'g6.2xlarge' = 8 }
$Price = @{ 'g6e.2xlarge' = 2.242; 'g6e.xlarge' = 1.861; 'g5.2xlarge' = 1.212; 'g6.2xlarge' = 0.978 }
$ExtraPerHour = 0.05   # ~200 GB gp3 + public IPv4

function Say([string]$m, [string]$c = 'Gray') { Write-Host $m -ForegroundColor $c }
function Invoke-AwsCli {
  # Runs aws with profile/region; returns trimmed stdout text; exit code in $script:AwsExit.
  param([string[]]$A, [switch]$Quiet)
  $all = @($A) + @('--profile', $Profile, '--region', $Region)
  if ($Quiet) { $o = & aws @all 2>$null } else { $o = & aws @all }
  $script:AwsExit = $LASTEXITCODE
  return ($o | Out-String).Trim()
}
function Stop-Here([string]$msg, [int]$code = 1) {
  Say "STOP: $msg" 'Red'
  if ($WhatIf) { Say '  (WhatIf: continuing so you can see the rest of the plan)' 'Yellow'; $script:WouldStop = $true; return }
  exit $code
}
$script:WouldStop = $false

Say '=== Bestiary DEMO host: deploy (demo only - delete it after the talk) ===' 'Cyan'
if ($WhatIf) { Say 'WhatIf: read-only checks only, NO write calls to AWS.' 'Yellow' }
if (-not (Get-Command aws -ErrorAction SilentlyContinue)) { Stop-Here 'aws CLI not found on PATH.'; if (-not $WhatIf) { exit 1 } }
if (@('us-east-1', 'us-east-2') -notcontains $Region) { Stop-Here "Region must be us-east-1 or us-east-2 (got $Region)." }
if (-not $BudgetEmail -and -not $SkipBudget) { Stop-Here 'Pass -BudgetEmail you@example.com (AWS Budgets alerts), or -SkipBudget.' }
if (-not (Test-Path $Template)) { Stop-Here "Template not found: $Template" }

# 1. Identity
$acct = Invoke-AwsCli @('sts', 'get-caller-identity', '--query', 'Account', '--output', 'text')
if ($script:AwsExit -ne 0 -or -not $acct) { Stop-Here "Cannot call STS with profile '$Profile'. Check credentials." }
$arn = Invoke-AwsCli @('sts', 'get-caller-identity', '--query', 'Arn', '--output', 'text') -Quiet
Say "Profile : $Profile`nRegion  : $Region`nAccount : $acct`nCaller  : $arn"
if ($acct -ne $ExpectedAccount) { Say "WARNING: expected account $ExpectedAccount, got $acct." 'Yellow' }

# 2. GitHub token parameter exists (existence only: no decryption, only the Type field is queried)
$ptype = Invoke-AwsCli @('ssm', 'get-parameter', '--name', $TokenParameterName, '--query', 'Parameter.Type', '--output', 'text') -Quiet
if ($script:AwsExit -ne 0) {
  Say "GitHub token parameter $TokenParameterName NOT found in $Region." 'Red'
  Say '  Create it once (prompts without echo):' 'Yellow'
  Say "    powershell infra\aws\put-github-token.ps1 -Region $Region -Profile $Profile" 'Yellow'
  Stop-Here 'token parameter missing.'
} elseif ($ptype -ne 'SecureString') {
  Stop-Here "Parameter $TokenParameterName exists but is type '$ptype', expected SecureString."
} else { Say "Token parameter: $TokenParameterName (SecureString) exists." 'Green' }

# 3. G/VT quota
$need = $VCpu[$InstanceType]
$quota = Invoke-AwsCli @('service-quotas', 'get-service-quota', '--service-code', 'ec2', '--quota-code', $QuotaCode, '--query', 'Quota.Value', '--output', 'text') -Quiet
$qv = 0.0
if ($script:AwsExit -ne 0 -or -not [double]::TryParse($quota, [Globalization.NumberStyles]::Float, [Globalization.CultureInfo]::InvariantCulture, [ref]$qv)) {
  Stop-Here "Could not read quota $QuotaCode (service-quotas:GetServiceQuota denied?)."
} else {
  Say "G/VT on-demand vCPU quota ($QuotaCode) in ${Region}: $qv ; $InstanceType needs $need."
  if ($qv -lt $need) {
    $hist = Invoke-AwsCli @('service-quotas', 'list-requested-service-quota-change-history-by-quota', '--service-code', 'ec2', '--quota-code', $QuotaCode, '--query', 'RequestedQuotas[].[Status,DesiredValue,Id]', '--output', 'text') -Quiet
    Say "Quota request history (Status Desired Id):`n$hist" 'Yellow'
    Stop-Here "quota too low ($qv < $need). Wait for the pending request (status CASE_OPENED/PENDING) or try the other region."
  }
}

# 4. Default VPC + subnet in an AZ that offers the type
$vpc = Invoke-AwsCli @('ec2', 'describe-vpcs', '--filters', 'Name=is-default,Values=true', '--query', 'Vpcs[0].VpcId', '--output', 'text') -Quiet
if (-not $vpc -or $vpc -eq 'None') { Stop-Here "No default VPC in $Region." }
$azs = (Invoke-AwsCli @('ec2', 'describe-instance-type-offerings', '--location-type', 'availability-zone', '--filters', "Name=instance-type,Values=$InstanceType", '--query', 'InstanceTypeOfferings[].Location', '--output', 'text') -Quiet) -split '\s+' | Where-Object { $_ }
$subs = (Invoke-AwsCli @('ec2', 'describe-subnets', '--filters', "Name=vpc-id,Values=$vpc", 'Name=default-for-az,Values=true', '--query', 'Subnets[].[AvailabilityZone,SubnetId]', '--output', 'text') -Quiet) -split "`n" | Where-Object { $_.Trim() }
$subnet = $null; $az = $null
foreach ($row in ($subs | Sort-Object)) {
  $p = $row.Trim() -split '\s+'
  if ($azs -contains $p[0]) { $az = $p[0]; $subnet = $p[1]; break }
}
if (-not $subnet) { Stop-Here "No default-VPC subnet in an AZ offering $InstanceType (offered in: $($azs -join ', '))." }
else { Say "VPC $vpc ; subnet $subnet in $az (offers $InstanceType)." 'Green' }

# Existing stack?
$st = Invoke-AwsCli @('cloudformation', 'describe-stacks', '--stack-name', $StackName, '--query', 'Stacks[0].StackStatus', '--output', 'text') -Quiet
if ($script:AwsExit -eq 0) {
  Say "Stack $StackName already exists (status $st)." 'Yellow'
  if ($st -match 'ROLLBACK_COMPLETE|CREATE_FAILED|DELETE_FAILED') { Stop-Here "Stack is in $st; run infra\aws\teardown.ps1 first." }
}

# 5. Cost estimate
$rate = $Price[$InstanceType] + $ExtraPerHour
$capHours = [math]::Floor(300 / $rate)
Say "`n--- Cost estimate (hard-coded us-east-1 on-demand list prices; other regions may differ) ---" 'Cyan'
Say ('  {0} : {1:N3} USD/h compute + {2:N2} USD/h EBS/IPv4 = {3:N3} USD/h' -f $InstanceType, $Price[$InstanceType], $ExtraPerHour, $rate)
Say ('  AutoStopHours {0,3} h : ~{1,7:N2} USD  (auto-stop is OS poweroff = STOP; EBS keeps billing until teardown)' -f $AutoStopHours, ($rate * $AutoStopHours))
Say ('  Left running 72 h    : ~{0,7:N2} USD' -f ($rate * 72))
Say ('  300 USD credits cap  : reached after ~{0} h of running time' -f $capHours)
Say '  Stopped instance: only the 200 GB gp3 volume bills (~0.02 USD/h) until you run teardown.' 'Yellow'
Say '  Budgets alerts lag by hours and are NOT a hard cap: tear down yourself.' 'Yellow'

# 6. Plan + confirmation
$paramOverrides = @(
  "InstanceType=$InstanceType", "AutoStopHours=$AutoStopHours", "ModelTag=$ModelTag",
  "FailoverModelTag=$FailoverModelTag", "GitHubDemoRepo=$DemoRepo", "GitHubDemoIssue=$DemoIssue", "RepoUrl=$RepoUrl", "RepoRef=$RepoRef",
  "GitHubTokenParameterName=$TokenParameterName", "VpcId=$vpc", "SubnetId=$subnet",
  "BudgetEmail=$(if ($BudgetEmail) { $BudgetEmail } else { 'none@example.com' })",
  "CreateBudget=$(if ($SkipBudget) { 'false' } else { 'true' })"
)
$deployArgs = @('cloudformation', 'deploy', '--template-file', $Template, '--stack-name', $StackName,
  '--capabilities', 'CAPABILITY_IAM', '--no-fail-on-empty-changeset',
  '--tags', 'Project=bestiary-demo', '--parameter-overrides') + $paramOverrides + @('--profile', $Profile, '--region', $Region)
Say "`nPlanned command:" 'Cyan'
Say ('  aws ' + ($deployArgs -join ' '))
if ($WhatIf) {
  if ($script:WouldStop) { Say "`nWhatIf: a real run would have STOPPED at a check above." 'Yellow' }
  Say 'WhatIf: nothing was created.' 'Yellow'; exit 0
}
if (-not $Yes) {
  $ans = Read-Host "Type the stack name '$StackName' to create billable GPU resources (anything else aborts)"
  if ($ans -ne $StackName) { Say 'Aborted.' 'Yellow'; exit 1 }
}

# 7. Deploy (deploy waits for CREATE_COMPLETE / UPDATE_COMPLETE; creates IAM -> CAPABILITY_IAM, role is unnamed)
Say "`nDeploying (takes a few minutes; this does NOT wait for the 20+ min bootstrap)..." 'Cyan'
& aws @deployArgs
if ($LASTEXITCODE -ne 0) {
  Say 'Deploy FAILED. Recent stack events:' 'Red'
  & aws cloudformation describe-stack-events --stack-name $StackName --profile $Profile --region $Region --max-items 12 --query 'StackEvents[?contains(ResourceStatus,''FAILED'')].[LogicalResourceId,ResourceStatusReason]' --output text
  Say "Clean up with: powershell infra\aws\teardown.ps1 -StackName $StackName -Region $Region" 'Yellow'
  exit 1
}

# 8. Outputs
Say "`n=== Stack outputs ===" 'Green'
& aws cloudformation describe-stacks --stack-name $StackName --profile $Profile --region $Region --query 'Stacks[0].Outputs[].[OutputKey,OutputValue]' --output text
Say @"

Next:
  1. Watch bootstrap (20+ min; k3s + model pull). Use the LogTailCommand output above, or:
       powershell infra\aws\present.ps1 -StackName $StackName -Region $Region -Logs
  2. When the console pod is Ready:  powershell infra\aws\present.ps1 -StackName $StackName -Region $Region
     (needs session-manager-plugin on this laptop; terminal at least 110 columns wide)
  3. AFTER THE TALK:  powershell infra\aws\teardown.ps1 -StackName $StackName -Region $Region
"@ 'Cyan'
exit 0
