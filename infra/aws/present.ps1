<#
.SYNOPSIS
  Open an SSM Session Manager session on the demo host and run the Bestiary game in the console pod.
.DESCRIPTION
  Default: kubectl exec -it into Deployment console (namespace bestiary, container console) running `bestiary`.
  -Doctor : `bestiary doctor`            -Shell : bash inside the console pod
  -Host   : plain host shell (no document) -Logs  : follow /var/log/bestiary-bootstrap.log
  Needs session-manager-plugin on this laptop. Make the terminal at least 110 columns wide BEFORE starting
  (it cannot be forced from here). The --parameters JSON goes through a temp file (file://) because
  Windows PowerShell 5.1 mangles embedded double quotes in native-command arguments.
  -WhatIf prints the command and makes no session.
#>
param(
  [string]$InstanceId,
  [string]$StackName = 'bestiary-demo',
  [string]$Region = 'us-east-1',
  [string]$Profile = $(if ($env:AWS_PROFILE) { $env:AWS_PROFILE } else { 'cloud_native_lima' }),
  [switch]$Doctor,
  [switch]$Shell,
  [Alias('Host')][switch]$HostShell,   # -Host works; the variable cannot be named $Host (automatic variable)
  [switch]$Logs,
  [switch]$Battle,   # the Pokemon-style battle screens
  [ValidateSet('choose', 'auto')][string]$Pick,   # battle screens: you choose the creature (default) or the right one is already on the field
  [ValidateSet('es', 'en')][string]$Lang,         # language of the texts (default es)
  [switch]$WhatIf
)
$ErrorActionPreference = 'Continue'
function Say([string]$m, [string]$c = 'Gray') { Microsoft.PowerShell.Utility\Write-Host $m -ForegroundColor $c }

# Contract with the k8s manifests: namespace bestiary, Deployment console, container console, binary `bestiary` on PATH.
# k3s kubeconfig (/etc/rancher/k3s/k3s.yaml) is root-readable, so `sudo k3s kubectl` (ssm-user has passwordless sudo).
$exec = 'sudo k3s kubectl -n bestiary exec -it deploy/console -c console --'
if ($HostShell) { $mode = 'host' }
elseif ($Logs) { $mode = 'logs'; $remote = 'sudo tail -n 200 -F /var/log/bestiary-bootstrap.log' }
elseif ($Doctor) { $mode = 'doctor'; $remote = "$exec bestiary doctor" }
elseif ($Shell) { $mode = 'shell'; $remote = "$exec bash" }
else {
  $mode = 'game'
  $extra = ''
  if ($Pick) { $extra += " --pick $Pick" }
  if ($Lang) { $extra += " --lang $Lang" }
  $remote = if ($Battle) { "$exec bestiary play --ui battle$extra" } else { "$exec bestiary play$extra" }
}

if (-not (Get-Command aws -ErrorAction SilentlyContinue)) { Say 'aws CLI not found on PATH.' 'Red'; exit 1 }

# Resolve instance id
if (-not $InstanceId) {
  $InstanceId = (& aws cloudformation describe-stacks --stack-name $StackName --query "Stacks[0].Outputs[?OutputKey=='InstanceId'].OutputValue" --output text --profile $Profile --region $Region 2>$null | Out-String).Trim()
  if ($LASTEXITCODE -ne 0 -or -not $InstanceId -or $InstanceId -eq 'None') {
    Say "Could not resolve InstanceId from stack $StackName in $Region. Pass -InstanceId i-..." 'Red'
    if (-not $WhatIf) { exit 1 } else { $InstanceId = 'i-0000000000000000' }
  }
}
if ($InstanceId -notmatch '^i-[0-9a-f]{8,17}$') { Say "Invalid instance id: $InstanceId" 'Red'; exit 2 }

# session-manager-plugin check (the CLI would create the session first and only then notice it is missing)
$plugin = Get-Command session-manager-plugin -ErrorAction SilentlyContinue
if (-not $plugin) {
  $pf = Join-Path $env:ProgramFiles 'Amazon\SessionManagerPlugin\bin'
  if (Test-Path (Join-Path $pf 'session-manager-plugin.exe')) { $env:Path += ";$pf"; $plugin = $true }
}
if (-not $plugin) {
  Say 'session-manager-plugin is NOT installed on this laptop.' 'Red'
  Say @'
Install (needs Administrator):
  1. Download https://s3.amazonaws.com/session-manager-downloads/plugin/latest/windows/SessionManagerPluginSetup.exe
  2. Run it as Administrator, leave the install folder at its default.
  3. Open a NEW PowerShell window and check:  session-manager-plugin --version
Docs: https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html
'@ 'Yellow'
  if (-not $WhatIf) { exit 1 }
}

# Is the instance registered with SSM?
$ping = (& aws ssm describe-instance-information --filters "Key=InstanceIds,Values=$InstanceId" --query 'InstanceInformationList[0].PingStatus' --output text --profile $Profile --region $Region 2>$null | Out-String).Trim()
if ($ping -ne 'Online') { Say "WARNING: SSM status of $InstanceId is '$ping' (expected Online). Instance still booting, stopped, or agent not up yet." 'Yellow' }

# Terminal width advice
$w = 0; try { $w = $Host.UI.RawUI.WindowSize.Width } catch {}
if ($w -gt 0 -and $w -lt 110) { Say "Terminal is $w columns wide; widen it to at least 110 BEFORE continuing (the game UI needs it). Starting anyway in 5 s..." 'Yellow'; if (-not $WhatIf) { Start-Sleep -Seconds 5 } }
else { Say 'Tip: keep the terminal at least 110 columns wide; resizing later may garble the TUI.' }

$common = @('--target', $InstanceId, '--profile', $Profile, '--region', $Region)
if ($mode -eq 'host') {
  $cmdArgs = @('ssm', 'start-session') + $common
  Say "Mode: host shell" 'Cyan'
} else {
  $tmp = Join-Path ([IO.Path]::GetTempPath()) ('bestiary-ssm-' + [Guid]::NewGuid().ToString('N') + '.json')
  $json = '{"command":["' + $remote + '"]}'    # $remote contains no double quotes or backslashes
  if (-not $WhatIf) { [IO.File]::WriteAllText($tmp, $json, (New-Object Text.UTF8Encoding($false))) }
  $uri = 'file://' + ($tmp -replace '\\', '/')
  $cmdArgs = @('ssm', 'start-session', '--document-name', 'AWS-StartInteractiveCommand', '--parameters', $uri) + $common
  Say "Mode: $mode   remote command: $remote" 'Cyan'
}
Say ('aws ' + ($cmdArgs -join ' ')) 'DarkGray'
if ($WhatIf) { Say 'WhatIf: no session started.' 'Yellow'; if ($mode -ne 'host') { Say "WhatIf: parameters file would contain: $json" 'DarkGray' }; exit 0 }
if ($mode -eq 'game') { Say 'If the console pod is not Ready yet the session ends at once: use -Logs / -Doctor, retry in a minute.' }
try { & aws @cmdArgs; $rc = $LASTEXITCODE }
finally { if ($tmp -and (Test-Path $tmp)) { Remove-Item $tmp -Force -ErrorAction SilentlyContinue } }
exit $rc
