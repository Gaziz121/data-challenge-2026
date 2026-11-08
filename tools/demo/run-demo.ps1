<#
.SYNOPSIS
  Demo launcher for the CQA app on Windows (PowerShell 5.1+). Double-click tools\demo\demo-start.cmd or run this file.

.DESCRIPTION
  Activates .venv, sets PYTHONUTF8=1, PYTHONPATH=src and CQA_REVIEWER_KEY=demo-reviewer-key, starts
  `python -m cqa.web` with --live-call-limit 0 (no paid OpenAI calls) and opens the browser.
  Stop the server with Ctrl+C in this window.

.PARAMETER Checklist
  Default checklist for the server (file under src\cqa\checklists). Default: official-v7.json (README).
  Use official-v3.json if Mock should give a scored result on the very first click.

.PARAMETER WithApprovals
  Also pass --authorization-manifest restricted\demo-approvals.json (three FICTIONAL demo conversations, DEMO.md 4b).
  Without it, evaluating a pasted conversation is refused with 403 (the "no approval" demo).

.PARAMETER Reset
  Stop the CQA server on the port and delete outputs\app (saved evaluations, appeals, saved checklist versions)
  after showing what is there and asking for confirmation. restricted\ is never touched.

.PARAMETER Live
  REAL OpenAI evaluation (paid, about USD 0.013-0.023 per evaluation). Needs -EnvFile: an ignored local file with
  OPENAI_API_KEY=... (the server reads only OPENAI_API_KEY and CQA_MODEL from it). Adds --env-file, --model,
  --allow-external-synthetic (the 60 synthetic DEV chats) and --live-call-limit <LiveCalls>. With -WithApprovals also
  --allow-external-authorized (the approval file must then be created with --external openai).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\tools\demo\run-demo.ps1
  powershell -ExecutionPolicy Bypass -File .\tools\demo\run-demo.ps1 -Reset
  powershell -ExecutionPolicy Bypass -File .\tools\demo\run-demo.ps1 -Checklist official-v3.json -WithApprovals
  powershell -ExecutionPolicy Bypass -File .\tools\demo\run-demo.ps1 -Live -EnvFile C:\secure\cqa.env -LiveCalls 10
#>
[CmdletBinding()]
param(
  [int]$Port = 8765,
  [string]$Checklist = "official-v7.json",
  [switch]$WithApprovals,
  [switch]$Reset,
  [switch]$NoBrowser,
  [switch]$Live,
  [string]$EnvFile,
  [string]$Model = "gpt-5.4-mini-2026-03-17",
  [int]$LiveCalls = 10
)
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..\..")).Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$AppDir = Join-Path $Root "outputs\app"
$Url = "http://127.0.0.1:$Port/"

function Get-CqaServer([int]$OnPort) {
  $conn = Get-NetTCPConnection -LocalPort $OnPort -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
  if (-not $conn) { return $null }
  $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$($conn.OwningProcess)"
  [pscustomobject]@{ Pid = $conn.OwningProcess; IsCqa = ($proc.CommandLine -match 'cqa\.web'); CommandLine = $proc.CommandLine }
}

function Stop-CqaServer([int]$OnPort) {
  $server = Get-CqaServer $OnPort
  if (-not $server) { Write-Host "No server listens on port $OnPort."; return }
  if (-not $server.IsCqa) { throw "Port $OnPort belongs to a process that is not cqa.web (PID $($server.Pid)); not touching it." }
  Stop-Process -Id $server.Pid -Confirm:$false
  Write-Host "Stopped the CQA server (PID $($server.Pid)) on port $OnPort."
}

if ($Reset) {
  Stop-CqaServer $Port
  if (-not (Test-Path -LiteralPath $AppDir)) { Write-Host "outputs\app does not exist; state is already clean." }
  else {
    $files = @(Get-ChildItem -LiteralPath $AppDir -Recurse -File)
    $unexpected = @(Get-ChildItem -LiteralPath $AppDir | Where-Object {
        -not ($_.PSIsContainer -and $_.Name -in @("appeals", "checklists")) -and
        -not (-not $_.PSIsContainer -and $_.Name -match '^(rejected-)?[0-9a-f-]{36}\.json$') })
    Write-Host "outputs\app contains $($files.Count) files:"
    Get-ChildItem -LiteralPath $AppDir | Group-Object { if ($_.PSIsContainer) { "$($_.Name)\" } elseif ($_.Name -like "rejected-*") { "rejected diagnostics" } else { "evaluations" } } |
      ForEach-Object { Write-Host ("  {0,-22} {1}" -f $_.Name, $_.Count) }
    if ($files.Count) {
      $sorted = $files | Sort-Object LastWriteTime
      Write-Host "  oldest: $($sorted[0].LastWriteTime)   newest: $($sorted[-1].LastWriteTime)"
    }
    if ($unexpected.Count) {
      Write-Warning "Unexpected entries (not created by the app):"; $unexpected | ForEach-Object { Write-Warning "  $($_.Name)" }
      throw "Not deleting outputs\app: review the unexpected entries first."
    }
    $answer = Read-Host "Delete $AppDir (saved evaluations, appeals, saved checklist versions)? Type YES to confirm"
    if ($answer -cne "YES") { Write-Host "Cancelled; nothing deleted."; return }
    Remove-Item -LiteralPath $AppDir -Recurse -Force
    Write-Host "Deleted $AppDir. Built-in checklists v2-v7 stay available."
  }
}

if (-not (Test-Path -LiteralPath $Python)) { throw "No .venv found. Run: python -m venv .venv; .\.venv\Scripts\python.exe -m pip install --upgrade pip `"pydantic==2.13.5`"" }
$ChecklistPath = Join-Path "src\cqa\checklists" $Checklist
if (-not (Test-Path -LiteralPath (Join-Path $Root $ChecklistPath))) { throw "Checklist $ChecklistPath not found." }

$running = Get-CqaServer $Port
if ($running) {
  if ($running.IsCqa) { Write-Host "A CQA server is already running on $Url (use -Reset to stop it)."; if (-not $NoBrowser) { Start-Process $Url }; return }
  throw "Port $Port is used by another program (PID $($running.Pid)). Choose -Port <n>."
}

$activate = Join-Path $Root ".venv\Scripts\Activate.ps1"
if (Test-Path -LiteralPath $activate) { . $activate }
$env:PYTHONUTF8 = "1"
$env:PYTHONPATH = "src"
$env:CQA_REVIEWER_KEY = "demo-reviewer-key"

$serverArgs = @("-B", "-m", "cqa.web", "--port", "$Port", "--checklist", $ChecklistPath)
if ($Live) {
  if (-not $EnvFile -or -not (Test-Path -LiteralPath $EnvFile)) { throw "-Live needs -EnvFile <path to an ignored file with OPENAI_API_KEY=...>. Never put the key in the repository or on the command line." }
  if ($LiveCalls -lt 1) { throw "-LiveCalls must be at least 1." }
  $serverArgs += @("--env-file", $EnvFile, "--model", $Model, "--allow-external-synthetic", "--live-call-limit", "$LiveCalls")
  if ($WithApprovals) { $serverArgs += "--allow-external-authorized" }
  Write-Warning "LIVE MODE: real OpenAI calls ($Model), at most $LiveCalls per server run, about USD 0.013-0.023 each."
} else {
  $serverArgs += @("--live-call-limit", "0")
}
if ($WithApprovals) {
  $manifest = "restricted\demo-approvals.json"
  if (-not (Test-Path -LiteralPath (Join-Path $Root $manifest))) {
    throw "No $manifest. Create it (fictional demo records only): .\.venv\Scripts\python.exe -B -m cqa_results.grants --data docs\demo\fictional_new_conversations.json --data-class synthetic_test --reference demo-fictional-conversations --expires 2030-01-01T00:00:00Z --output $manifest  (add --external openai for -Live)"
  }
  $serverArgs += @("--authorization-manifest", $manifest)
}

if (-not $NoBrowser) {
  # Open the browser as soon as the port answers (background job; the server runs in this window).
  Start-Job -ArgumentList $Url -ScriptBlock {
    param($u)
    for ($i = 0; $i -lt 60; $i++) {
      try { Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 2 | Out-Null; Start-Process $u; return } catch { Start-Sleep -Milliseconds 500 }
    }
  } | Out-Null
}
Write-Host "Starting CQA on $Url  (checklist $Checklist, $(if ($Live) { "LIVE OpenAI $Model, max $LiveCalls calls" } else { 'live calls 0' }), reviewer key demo-reviewer-key$(if ($WithApprovals) { ', demo approvals ON' } else { ', no approvals: pasted input -> 403' })). Ctrl+C to stop."
Set-Location -LiteralPath $Root
& $Python @serverArgs
