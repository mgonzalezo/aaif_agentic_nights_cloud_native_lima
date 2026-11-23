<#
.SYNOPSIS
  Create the SSM SecureString that holds the READ-ONLY GitHub token the demo host uses to clone the private repo.
.DESCRIPTION
  Prompts for the token without echo, writes it to a private temp file ONLY so that
  `aws ssm put-parameter --cli-input-json file://...` can read it (the token is never on a command line),
  then overwrites and deletes that file. The token is never printed or logged.
  Use a fine-grained PAT: only this repo, permission Contents = Read-only, short expiry (for example 7 days).
  Without -Overwrite an existing parameter is left untouched.
  -WhatIf makes no AWS call and does not prompt.
#>
param(
  [string]$Region = 'us-east-1',
  [string]$Profile = $(if ($env:AWS_PROFILE) { $env:AWS_PROFILE } else { 'cloud_native_lima' }),
  [string]$ParameterName = '/bestiary/github-token',
  [switch]$Overwrite,
  [switch]$WhatIf
)
$ErrorActionPreference = 'Continue'

if ($ParameterName -notmatch '^/[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)*$') { Write-Host "Invalid parameter name: $ParameterName" -ForegroundColor Red; exit 2 }
$plan = "aws ssm put-parameter --cli-input-json file://<private temp file> --profile $Profile --region $Region   (Name=$ParameterName, Type=SecureString, Overwrite=$([bool]$Overwrite.IsPresent))"
if ($WhatIf) { Write-Host "WhatIf: would run: $plan"; Write-Host 'WhatIf: no AWS call, no prompt.'; exit 0 }
if (-not (Get-Command aws -ErrorAction SilentlyContinue)) { Write-Host 'aws CLI not found.' -ForegroundColor Red; exit 1 }

# Existing parameter? (type only; value is never fetched or shown)
$etype = (& aws ssm get-parameter --name $ParameterName --query Parameter.Type --output text --profile $Profile --region $Region 2>$null | Out-String).Trim()
if ($LASTEXITCODE -eq 0 -and -not $Overwrite) {
  Write-Host "Parameter $ParameterName already exists ($etype) in $Region. Rerun with -Overwrite to replace it." -ForegroundColor Yellow
  exit 1
}

Write-Host "Paste the GitHub fine-grained token (input hidden). Scope: this repo only, Contents: Read-only, short expiry." -ForegroundColor Cyan
$secure = Read-Host -Prompt 'GitHub token' -AsSecureString
$bstr = [IntPtr]::Zero; $plain = $null; $tmp = $null
try {
  $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
  $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
  if (-not $plain -or $plain -notmatch '^[A-Za-z0-9_-]{20,255}$') {
    Write-Host 'Token is empty or has unexpected characters/length (expected github_pat_... or ghp_...). Nothing stored.' -ForegroundColor Red
    exit 1
  }
  if ($plain -notmatch '^(github_pat_|ghp_)') { Write-Host 'Note: token does not start with github_pat_ / ghp_ (continuing).' -ForegroundColor Yellow }

  $tmp = Join-Path ([IO.Path]::GetTempPath()) ('bestiary-' + [Guid]::NewGuid().ToString('N') + '.json')
  [IO.File]::WriteAllText($tmp, '', (New-Object Text.UTF8Encoding($false)))          # create empty, then lock down BEFORE writing the secret
  & icacls $tmp /inheritance:r /grant:r "$($env:USERNAME):(F)" | Out-Null
  $ow = if ($Overwrite) { 'true' } else { 'false' }
  $json = '{"Name":"' + $ParameterName + '","Description":"Bestiary demo GitHub read-only token (delete after the talk)","Value":"' + $plain + '","Type":"SecureString","Tier":"Standard","Overwrite":' + $ow + '}'
  [IO.File]::WriteAllText($tmp, $json, (New-Object Text.UTF8Encoding($false)))
  $json = $null

  $uri = 'file://' + ($tmp -replace '\\', '/')
  $ver = (& aws ssm put-parameter --cli-input-json $uri --query Version --output text --profile $Profile --region $Region | Out-String).Trim()
  if ($LASTEXITCODE -ne 0) { Write-Host 'put-parameter failed (see AWS message above; value was not printed).' -ForegroundColor Red; exit 1 }
  Write-Host "Stored $ParameterName (SecureString, aws/ssm key, version $ver) in $Region." -ForegroundColor Green
  Write-Host 'Remember: delete it after the talk (teardown.ps1 -DeleteTokenParameter) and revoke the token on GitHub.'
}
finally {
  if ($tmp -and (Test-Path $tmp)) {
    try { $len = (Get-Item $tmp).Length; [IO.File]::WriteAllBytes($tmp, (New-Object byte[] $len)) } catch {}   # best-effort overwrite (not guaranteed on SSD/journaled FS)
    Remove-Item $tmp -Force -ErrorAction SilentlyContinue
  }
  if ($bstr -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
  $plain = $null; $secure = $null
}
