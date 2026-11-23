<#
.SYNOPSIS
  DELETE the Bestiary demo stack and audit that nothing billable is left.
.DESCRIPTION
  Shows what the stack contains, asks for a typed confirmation (unless -Yes), runs delete-stack,
  waits, then runs a read-only audit in us-east-1 and us-east-2. Exit code 0 = all PASS, 1 = any FAIL.
  The SSM parameter with the GitHub token is NOT part of the stack; pass -DeleteTokenParameter to remove it.
  -WhatIf: read-only only; skips delete-stack / delete-parameter.
#>
param(
  [string]$StackName = 'bestiary-demo',
  [string]$Region = 'us-east-1',
  [string]$Profile = $(if ($env:AWS_PROFILE) { $env:AWS_PROFILE } else { 'cloud_native_lima' }),
  [string]$TokenParameterName = '/bestiary/github-token',
  [switch]$DeleteTokenParameter,
  [switch]$Yes,
  [switch]$WhatIf
)

$ErrorActionPreference = 'Continue'
$AuditRegions = @($Region, 'us-east-1', 'us-east-2') | Select-Object -Unique
$script:Fails = 0; $script:Warns = 0; $script:Results = @()

function Say([string]$m, [string]$c = 'Gray') { Write-Host $m -ForegroundColor $c }
function Invoke-AwsCli {
  param([string[]]$A, [string]$R = $Region, [switch]$Quiet)
  $all = @($A) + @('--profile', $Profile, '--region', $R)
  if ($Quiet) { $o = & aws @all 2>$null } else { $o = & aws @all }
  $script:AwsExit = $LASTEXITCODE
  return ($o | Out-String).Trim()
}
function Test-Gone {
  # 'gone' only when AWS answers with the expected not-found error; 'error' for anything else (e.g. AccessDenied).
  param([string[]]$A, [string]$Pattern)
  $all = @($A) + @('--profile', $Profile, '--region', $Region)
  $o = (& aws @all 2>&1 | Out-String -Width 4096)
  if ($LASTEXITCODE -eq 0) { return 'exists' }
  if ($o -match $Pattern) { return 'gone' }
  return 'error'
}
function Add-Result([string]$status, [string]$name, [string]$detail = '') {
  $script:Results += ('{0,-5} {1}{2}' -f $status, $name, $(if ($detail) { " - $detail" } else { '' }))
  if ($status -eq 'FAIL') { $script:Fails++ } elseif ($status -eq 'WARN') { $script:Warns++ }
}

Say "=== Bestiary DEMO host: TEARDOWN (stack $StackName, $Region) ===" 'Cyan'
if ($WhatIf) { Say 'WhatIf: read-only only. Nothing will be deleted.' 'Yellow' }
if (-not (Get-Command aws -ErrorAction SilentlyContinue)) { Say 'aws CLI not found.' 'Red'; exit 1 }
$acct = Invoke-AwsCli @('sts', 'get-caller-identity', '--query', 'Account', '--output', 'text') -Quiet
if ($script:AwsExit -ne 0 -or -not $acct) { Say "Cannot call STS with profile '$Profile'." 'Red'; exit 1 }
Say "Profile $Profile / account $acct"

# 1. What will be deleted
$status = Invoke-AwsCli @('cloudformation', 'describe-stacks', '--stack-name', $StackName, '--query', 'Stacks[0].StackStatus', '--output', 'text') -Quiet
$stackExists = ($script:AwsExit -eq 0)
if ($stackExists) {
  Say "Stack status: $status. Resources that will be DELETED:" 'Yellow'
  Say (Invoke-AwsCli @('cloudformation', 'list-stack-resources', '--stack-name', $StackName, '--query', 'StackResourceSummaries[].[ResourceType,LogicalResourceId,PhysicalResourceId]', '--output', 'text'))
  Say 'This terminates the instance and deletes its EBS volume (all models and data on it are lost).' 'Yellow'
} else { Say "Stack $StackName not found in $Region (already deleted?). Running the audit only." 'Yellow' }

if ($DeleteTokenParameter) { Say "Will ALSO delete SSM parameter $TokenParameterName (the GitHub token)." 'Yellow' }
else { Say "NOT deleted: SSM parameter $TokenParameterName is outside the stack. It is free (Standard tier) but holds a SECRET: revoke the GitHub token and/or rerun with -DeleteTokenParameter." 'Yellow' }

# 2. Confirm + delete
if ($stackExists) {
  Say "`nPlanned: aws cloudformation delete-stack --stack-name $StackName --region $Region ; aws cloudformation wait stack-delete-complete ..."
  if ($WhatIf) { Say 'WhatIf: delete-stack skipped.' 'Yellow' }
  else {
    if (-not $Yes) {
      $ans = Read-Host "Type the stack name '$StackName' to DELETE it"
      if ($ans -ne $StackName) { Say 'Aborted.' 'Yellow'; exit 1 }
    }
    [void](Invoke-AwsCli @('cloudformation', 'delete-stack', '--stack-name', $StackName))
    if ($script:AwsExit -ne 0) { Say 'delete-stack call failed.' 'Red'; Add-Result 'FAIL' 'delete-stack' 'API call failed' }
    else {
      Say 'Waiting for deletion (instance termination can take a few minutes)...'
      [void](Invoke-AwsCli @('cloudformation', 'wait', 'stack-delete-complete', '--stack-name', $StackName))
      if ($script:AwsExit -ne 0) {
        Say 'Stack did not reach DELETE_COMPLETE. Failed events:' 'Red'
        Say (Invoke-AwsCli @('cloudformation', 'describe-stack-events', '--stack-name', $StackName, '--max-items', '15', '--query', 'StackEvents[?contains(ResourceStatus,''FAILED'')].[LogicalResourceId,ResourceStatusReason]', '--output', 'text') -Quiet)
      }
    }
  }
}
if ($DeleteTokenParameter) {
  if ($WhatIf) { Say "WhatIf: delete-parameter $TokenParameterName skipped." 'Yellow' }
  else {
    [void](Invoke-AwsCli @('ssm', 'delete-parameter', '--name', $TokenParameterName) -Quiet)
    if ($script:AwsExit -eq 0) { Say "Deleted parameter $TokenParameterName." 'Green' } else { Say "Parameter $TokenParameterName not deleted (missing or denied)." 'Yellow' }
  }
}

# 3. Audit (read-only)
Say "`n=== Nothing-billable-left audit (read-only) ===" 'Cyan'
$g = Test-Gone @('cloudformation', 'describe-stacks', '--stack-name', $StackName) 'does\s+not\s+exist'
if ($g -eq 'gone') { Add-Result 'PASS' "stack $StackName gone in $Region" }
elseif ($g -eq 'error') { Add-Result 'WARN' "stack $StackName state unknown" 'describe-stacks failed for another reason (permissions?)' }
else {
  $s2 = Invoke-AwsCli @('cloudformation', 'describe-stacks', '--stack-name', $StackName, '--query', 'Stacks[0].StackStatus', '--output', 'text') -Quiet
  if ($s2 -eq 'DELETE_COMPLETE') { Add-Result 'PASS' "stack $StackName gone in $Region" } else { Add-Result 'FAIL' "stack $StackName still exists" $s2 }
}
foreach ($r in $AuditRegions) {
  $states = 'pending,running,stopping,stopped,shutting-down'
  $i1 = Invoke-AwsCli @('ec2', 'describe-instances', '--filters', 'Name=tag:Project,Values=bestiary-demo', "Name=instance-state-name,Values=$states", '--query', 'Reservations[].Instances[].InstanceId', '--output', 'text') -R $r -Quiet
  if ($script:AwsExit -ne 0) { Add-Result 'WARN' "instances in $r" 'describe-instances failed (permissions?)' }
  elseif ($i1) { Add-Result 'FAIL' "non-terminated instance(s) tagged Project=bestiary-demo in $r" $i1 } else { Add-Result 'PASS' "no non-terminated instances tagged Project=bestiary-demo in $r" }
  $i2 = Invoke-AwsCli @('ec2', 'describe-instances', '--filters', "Name=tag:aws:cloudformation:stack-name,Values=$StackName", "Name=instance-state-name,Values=$states", '--query', 'Reservations[].Instances[].InstanceId', '--output', 'text') -R $r -Quiet
  if ($i2) { Add-Result 'FAIL' "non-terminated instance(s) of stack $StackName in $r" $i2 }
  $v1 = Invoke-AwsCli @('ec2', 'describe-volumes', '--filters', 'Name=tag:Project,Values=bestiary-demo', '--query', 'Volumes[].[VolumeId,State]', '--output', 'text') -R $r -Quiet
  $v1x = $script:AwsExit
  $v2 = Invoke-AwsCli @('ec2', 'describe-volumes', '--filters', "Name=tag:aws:cloudformation:stack-name,Values=$StackName", '--query', 'Volumes[].[VolumeId,State]', '--output', 'text') -R $r -Quiet
  $vv = (($v1 + "`n" + $v2) -split "`n" | Where-Object { $_.Trim() -and $_ -notmatch 'deleting|deleted' } | Select-Object -Unique) -join '; '
  if ($vv) { Add-Result 'FAIL' "EBS volume(s) with Project tag / stack tag in $r" $vv } elseif ($v1x -ne 0 -or $script:AwsExit -ne 0) { Add-Result 'WARN' "EBS volumes in $r" 'describe-volumes failed (permissions?)' } else { Add-Result 'PASS' "no EBS volumes tagged Project=bestiary-demo in $r" }
  $va = Invoke-AwsCli @('ec2', 'describe-volumes', '--filters', 'Name=status,Values=available', '--query', 'Volumes[].VolumeId', '--output', 'text') -R $r -Quiet
  if ($va) { Add-Result 'WARN' "unattached (available) EBS volumes in $r (untagged, maybe not ours; they bill)" $va }
  $ea = Invoke-AwsCli @('ec2', 'describe-addresses', '--query', 'Addresses[].[PublicIp,AllocationId,AssociationId]', '--output', 'text') -R $r -Quiet
  $eax = $script:AwsExit
  $free = ($ea -split "`n" | Where-Object { $_.Trim() -and ($_ -match '\tNone\s*$' -or $_ -match '\tNone\t') }) -join '; '
  if ($free) { Add-Result 'FAIL' "unassociated Elastic IP(s) in $r (billed)" $free } elseif ($eax -ne 0) { Add-Result 'WARN' "Elastic IPs in $r" 'describe-addresses failed (permissions?)' } else { Add-Result 'PASS' "no unassociated Elastic IPs in $r" }
}
$bn = "$StackName-credits-cap"
$g = Test-Gone @('budgets', 'describe-budget', '--account-id', $acct, '--budget-name', $bn) 'NotFound'
if ($g -eq 'gone') { Add-Result 'PASS' "budget $bn not present" }
elseif ($g -eq 'exists') { Add-Result 'FAIL' "budget $bn still exists" }
else { Add-Result 'WARN' "budget $bn state unknown" 'describe-budget failed for another reason (permissions?)' }
$tp = Invoke-AwsCli @('ssm', 'get-parameter', '--name', $TokenParameterName, '--query', 'Parameter.Type', '--output', 'text') -Quiet
if ($script:AwsExit -eq 0) { Add-Result 'WARN' "SSM parameter $TokenParameterName still exists ($Region)" 'holds a secret; revoke the GitHub token or use -DeleteTokenParameter' }
else { Add-Result 'PASS' "SSM parameter $TokenParameterName not present in $Region" }

$script:Results | ForEach-Object {
  $c = 'Green'; if ($_ -like 'FAIL*') { $c = 'Red' } elseif ($_ -like 'WARN*') { $c = 'Yellow' }
  Say $_ $c
}
Say ''
if ($script:Fails -eq 0) { Say "RESULT: PASS ($($script:Warns) warning(s))" 'Green' } else { Say "RESULT: FAIL ($($script:Fails) failure(s), $($script:Warns) warning(s)) - fix manually in the console." 'Red' }
Say @'

AWS Budgets note: the stack's budget is deleted with the stack. Budget and billing data lag by up to ~24 h,
so look at Billing > Cost Explorer the next day to confirm the final spend. Budgets only alert; they never stop anything.
This audit only checks us-east-1 and us-east-2 (the allowed regions).
'@ 'Cyan'
if ($WhatIf) { Say 'WhatIf: audit ran read-only; nothing was deleted.' 'Yellow' }
if ($script:Fails -gt 0) { exit 1 } else { exit 0 }
