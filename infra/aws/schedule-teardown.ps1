<#
.SYNOPSIS
  Schedule the DELETION of the demo stack for a fixed date and time (one-time EventBridge Scheduler task).
.DESCRIPTION
  At -RunAt, AWS itself calls CloudFormation DeleteStack on the demo stack: the instance, its disk, the
  security group, the role and the instance profile. Half an hour later a second schedule terminates the
  instance directly (safety net). It does not need your laptop or this session to be on.
  The scheduler costs nothing. A stopped instance still bills for its disk until the stack is deleted.
  -Status shows the schedules, -Cancel removes them. -WhatIf shows the plan and writes nothing.
.EXAMPLE
  powershell infra\aws\schedule-teardown.ps1 -RunAt 2026-11-27T12:00:00 -TimeZone UTC
  powershell infra\aws\schedule-teardown.ps1 -Status
  powershell infra\aws\schedule-teardown.ps1 -Cancel
#>
param(
  [string]$RunAt,                                   # local time of -TimeZone, like 2026-11-27T12:00:00
  [string]$TimeZone = 'UTC',                        # IANA name: UTC, America/Lima, Asia/Tokyo ...
  [string]$StackName = 'bestiary-demo',
  [string]$ScheduleStackName = 'bestiary-teardown-schedule',
  [string]$Region = 'us-east-1',
  [string]$Profile = $(if ($env:AWS_PROFILE) { $env:AWS_PROFILE } else { 'cloud_native_lima' }),
  [switch]$Status,
  [switch]$Cancel,
  [switch]$Yes,
  [switch]$WhatIf
)
$ErrorActionPreference = 'Continue'
function Say([string]$m, [string]$c = 'Gray') { Write-Host $m -ForegroundColor $c }
function Aws-Cli([string[]]$A) { $o = & aws @($A + @('--profile', $Profile, '--region', $Region)) 2>&1; $script:Rc = $LASTEXITCODE; return ($o | Out-String).Trim() }
$Template = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) 'teardown-schedule.yaml'

if (-not (Get-Command aws -ErrorAction SilentlyContinue)) { Say 'aws CLI not found on PATH.' 'Red'; exit 1 }
$acct = Aws-Cli @('sts', 'get-caller-identity', '--query', 'Account', '--output', 'text')
if ($Rc -ne 0) { Say "Cannot call STS with profile '$Profile'. Log in first." 'Red'; exit 1 }
Say "Profile $Profile, account $acct, region $Region"

if ($Status) {
  Say "Schedule stack '$ScheduleStackName':" 'Cyan'
  Say (Aws-Cli @('cloudformation', 'describe-stacks', '--stack-name', $ScheduleStackName, '--query', 'Stacks[0].[StackStatus,Outputs[0].OutputValue]', '--output', 'text'))
  Say (Aws-Cli @('scheduler', 'list-schedules', '--name-prefix', $ScheduleStackName, '--query', 'Schedules[].[Name,State]', '--output', 'text'))
  foreach ($s in 'delete-stack', 'terminate-instance') {
    $r = Aws-Cli @('scheduler', 'get-schedule', '--name', "$ScheduleStackName-$s", '--query', '[ScheduleExpression,ScheduleExpressionTimezone]', '--output', 'text')
    if ($Rc -eq 0) { Say "  $s : $r" }
  }
  Say "Demo stack '$StackName':" 'Cyan'
  Say (Aws-Cli @('cloudformation', 'describe-stacks', '--stack-name', $StackName, '--query', 'Stacks[0].StackStatus', '--output', 'text'))
  exit 0
}

if ($Cancel) {
  Say "This deletes the schedule stack '$ScheduleStackName' (the scheduled teardown will NOT run)." 'Yellow'
  if ($WhatIf) { Say 'WhatIf: nothing deleted.' 'Yellow'; exit 0 }
  Say (Aws-Cli @('cloudformation', 'delete-stack', '--stack-name', $ScheduleStackName))
  Say (Aws-Cli @('cloudformation', 'wait', 'stack-delete-complete', '--stack-name', $ScheduleStackName))
  Say 'Schedule removed.' 'Green'
  exit 0
}

if (-not $RunAt) { Say 'Pass -RunAt, for example -RunAt 2026-11-27T12:00:00 -TimeZone UTC' 'Red'; exit 2 }
$when = [DateTime]::MinValue
if (-not [DateTime]::TryParseExact($RunAt, 'yyyy-MM-ddTHH:mm:ss', [Globalization.CultureInfo]::InvariantCulture, 'None', [ref]$when)) { Say "-RunAt must look like 2026-11-27T12:00:00 (got '$RunAt')." 'Red'; exit 2 }
if ($TimeZone -eq 'UTC' -and $when -le [DateTime]::UtcNow) { Say "-RunAt $RunAt UTC is in the past." 'Red'; exit 2 }
$backup = $when.AddMinutes(30).ToString('yyyy-MM-ddTHH:mm:ss')

$st = Aws-Cli @('cloudformation', 'describe-stacks', '--stack-name', $StackName, '--query', 'Stacks[0].StackStatus', '--output', 'text')
if ($Rc -ne 0) { Say "Stack '$StackName' not found in ${Region}: nothing to schedule. ($st)" 'Red'; exit 1 }
$instance = Aws-Cli @('cloudformation', 'describe-stacks', '--stack-name', $StackName, '--query', "Stacks[0].Outputs[?OutputKey=='InstanceId'].OutputValue", '--output', 'text')
if ($instance -notmatch '^i-[0-9a-f]{8,17}$') { $instance = ''; Say 'No instance id in the stack outputs: the safety net is skipped.' 'Yellow' }

Say "`n=== Scheduled TEARDOWN of '$StackName' ($st) ===" 'Cyan'
Say "Deleted by AWS at : $RunAt ($TimeZone)"
Say "Safety net        : $backup ($TimeZone) terminates $(if ($instance) { $instance } else { '(none)' })"
Say 'What the delete removes:'
Say (Aws-Cli @('cloudformation', 'list-stack-resources', '--stack-name', $StackName, '--query', 'StackResourceSummaries[].[ResourceType,LogicalResourceId,PhysicalResourceId]', '--output', 'text'))
Say 'The instance disk (all models and data on it) is deleted with it. Not removed: the GitHub token parameter in SSM (free) and this schedule stack (free).' 'Yellow'
Say "Cancel any time:  powershell infra\aws\schedule-teardown.ps1 -Cancel"

$deployArgs = @('cloudformation', 'deploy', '--stack-name', $ScheduleStackName, '--template-file', $Template, '--capabilities', 'CAPABILITY_IAM',
  '--no-fail-on-empty-changeset', '--parameter-overrides', "StackName=$StackName", "RunAt=$RunAt", "BackupRunAt=$backup", "TimeZone=$TimeZone", "InstanceId=$instance",
  '--tags', 'Project=bestiary-demo')
if ($WhatIf) { Say "`nWhatIf: would run: aws $($deployArgs -join ' ') --profile $Profile --region $Region" 'Yellow'; exit 0 }
if (-not $Yes) {
  $a = Read-Host "`nType DESTROY to schedule the deletion"
  if ($a -ne 'DESTROY') { Say 'Not confirmed. Nothing scheduled.' 'Yellow'; exit 1 }
}
Say (Aws-Cli $deployArgs)
if ($Rc -ne 0) { Say 'Deploy failed.' 'Red'; exit 1 }
Say "`nScheduled. Check it with:  powershell infra\aws\schedule-teardown.ps1 -Status" 'Green'
