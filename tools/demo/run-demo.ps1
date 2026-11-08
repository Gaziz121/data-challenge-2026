<#
.SYNOPSIS
  Запуск демо CQA на Windows (PowerShell 5.1+). Проще всего — двойной клик tools\demo\demo-start.cmd.

.DESCRIPTION
  Включает .venv, задаёт PYTHONUTF8=1, PYTHONPATH=src и CQA_REVIEWER_KEY=demo-reviewer-key, запускает
  `python -m cqa.web` с --live-call-limit 0 (никаких платных вызовов OpenAI) и открывает браузер.
  Остановить сервер: Ctrl+C в этом окне.
  Первый запуск на новом компьютере сам создаёт .venv и ставит pydantic 2.13.5 (нужен интернет один раз).
  Если Python не установлен — подсказывает, где взять Python 3.11.

.PARAMETER Checklist
  Чек-лист сервера по умолчанию (файл в src\cqa\checklists). По умолчанию official-v7.json, как в README.

.PARAMETER WithApprovals
  Добавить --authorization-manifest restricted\demo-approvals.json (три ВЫМЫШЛЕННЫХ демо-диалога, DEMO.md 4b).
  Без этого вставленный диалог получает отказ 403 — это сценарий «без разрешения».

.PARAMETER Reset
  Остановить сервер на порту и удалить outputs\app (сохранённые оценки, апелляции, версии чек-листов)
  после показа содержимого и подтверждения YES. Папка restricted\ не затрагивается.

.PARAMETER Live
  НАСТОЯЩАЯ оценка OpenAI (платно, около 0.013–0.023 USD за оценку). Нужен -EnvFile: локальный файл вне Git
  со строкой OPENAI_API_KEY=... Добавляет --env-file, --model, --allow-external-synthetic и --live-call-limit <LiveCalls>.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\tools\demo\run-demo.ps1
  powershell -ExecutionPolicy Bypass -File .\tools\demo\run-demo.ps1 -Reset
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
  if (-not $server) { Write-Host "На порту $OnPort сервер не запущен."; return }
  if (-not $server.IsCqa) { throw "Порт $OnPort занят другой программой (PID $($server.Pid)), её не трогаю." }
  Stop-Process -Id $server.Pid -Confirm:$false
  Write-Host "Сервер CQA остановлен (PID $($server.Pid), порт $OnPort)."
}

if ($Reset) {
  Stop-CqaServer $Port
  if (-not (Test-Path -LiteralPath $AppDir)) { Write-Host "Папки outputs\app нет — история уже чистая." }
  else {
    $files = @(Get-ChildItem -LiteralPath $AppDir -Recurse -File)
    $unexpected = @(Get-ChildItem -LiteralPath $AppDir | Where-Object {
        -not ($_.PSIsContainer -and $_.Name -in @("appeals", "checklists")) -and
        -not (-not $_.PSIsContainer -and $_.Name -match '^(rejected-)?[0-9a-f-]{36}\.json$') })
    Write-Host "В outputs\app файлов: $($files.Count)"
    Get-ChildItem -LiteralPath $AppDir | Group-Object { if ($_.PSIsContainer) { "$($_.Name)\" } elseif ($_.Name -like "rejected-*") { "отклонённые оценки" } else { "оценки" } } |
      ForEach-Object { Write-Host ("  {0,-22} {1}" -f $_.Name, $_.Count) }
    if ($files.Count) {
      $sorted = $files | Sort-Object LastWriteTime
      Write-Host "  самый старый: $($sorted[0].LastWriteTime)   самый новый: $($sorted[-1].LastWriteTime)"
    }
    if ($unexpected.Count) {
      Write-Warning "Найдены посторонние файлы (их создало не приложение):"; $unexpected | ForEach-Object { Write-Warning "  $($_.Name)" }
      throw "outputs\app не удаляю: сначала проверьте посторонние файлы."
    }
    $answer = Read-Host "Удалить $AppDir (оценки, апелляции, сохранённые версии чек-листов)? Введите YES для подтверждения"
    if ($answer -cne "YES") { Write-Host "Отменено, ничего не удалено."; return }
    Remove-Item -LiteralPath $AppDir -Recurse -Force
    Write-Host "Удалено. Встроенные чек-листы v2–v7 остаются."
  }
}

function Find-BasePython {
  # Сначала лаунчер py (ставится установщиком с python.org), потом python: голый python может быть заглушкой Microsoft Store.
  foreach ($candidate in @(@("py", "-3"), @("python"))) {
    $exe = $candidate[0]; $pre = @($candidate | Select-Object -Skip 1)
    if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
    try { $version = & $exe @pre -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null } catch { continue }
    if ($LASTEXITCODE -eq 0 -and "$version" -match '^3\.(\d+)$' -and [int]$Matches[1] -ge 9) {
      return [pscustomobject]@{ Exe = $exe; Pre = $pre; Version = "$version" }
    }
  }
  return $null
}

function Test-Pydantic {
  if (-not (Test-Path -LiteralPath $Python)) { return $false }
  try { & $Python -c "import pydantic" 2>$null; return ($LASTEXITCODE -eq 0) } catch { return $false }
}

if (-not (Test-Pydantic)) {
  # Первый запуск на новом компьютере: создать .venv и поставить pydantic (нужен интернет один раз).
  if (-not (Test-Path -LiteralPath $Python)) {
    $base = Find-BasePython
    if (-not $base) {
      Write-Host ""
      Write-Host "Python не найден. Установите Python 3.11 (откроется страница загрузки):" -ForegroundColor Yellow
      Write-Host "  https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
      Write-Host "  В первом окне установщика отметьте «Add python.exe to PATH» и нажмите «Install Now»."
      Write-Host "  Потом снова дважды щёлкните demo-start.cmd."
      Start-Process "https://www.python.org/downloads/release/python-3119/"
      throw "Сначала установите Python."
    }
    Write-Host "Первый запуск: создаю окружение Python (Python $($base.Version)) в папке .venv..."
    & $base.Exe @($base.Pre + @("-m", "venv", (Join-Path $Root ".venv")))
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $Python)) { throw "Не удалось создать .venv." }
  }
  Write-Host "Ставлю pydantic 2.13.5 (нужен интернет, обычно меньше минуты)..."
  & $Python -m pip install --disable-pip-version-check --quiet "pydantic==2.13.5"
  if ($LASTEXITCODE -ne 0 -or -not (Test-Pydantic)) { throw "Не удалось установить pydantic. Проверьте интернет и снова дважды щёлкните demo-start.cmd." }
  Write-Host "Готово: окружение установлено, дальше демо работает без интернета."
}
$ChecklistPath = Join-Path "src\cqa\checklists" $Checklist
if (-not (Test-Path -LiteralPath (Join-Path $Root $ChecklistPath))) { throw "Не найден чек-лист $ChecklistPath." }

$running = Get-CqaServer $Port
if ($running) {
  if ($running.IsCqa) { Write-Host "Сервер CQA уже запущен: $Url (для перезапуска с чистой историей — demo-reset.cmd)."; if (-not $NoBrowser) { Start-Process $Url }; return }
  throw "Порт $Port занят другой программой (PID $($running.Pid)). Укажите другой: -Port 8770."
}

$activate = Join-Path $Root ".venv\Scripts\Activate.ps1"
if (Test-Path -LiteralPath $activate) { . $activate }
$env:PYTHONUTF8 = "1"
$env:PYTHONPATH = "src"
$env:CQA_REVIEWER_KEY = "demo-reviewer-key"

$serverArgs = @("-B", "-m", "cqa.web", "--port", "$Port", "--checklist", $ChecklistPath)
if ($Live) {
  if (-not $EnvFile -or -not (Test-Path -LiteralPath $EnvFile)) { throw "Для -Live нужен -EnvFile <путь к файлу со строкой OPENAI_API_KEY=...>. Ключ нельзя класть в репозиторий или писать в командной строке." }
  if ($LiveCalls -lt 1) { throw "-LiveCalls должен быть не меньше 1." }
  $serverArgs += @("--env-file", $EnvFile, "--model", $Model, "--allow-external-synthetic", "--live-call-limit", "$LiveCalls")
  if ($WithApprovals) { $serverArgs += "--allow-external-authorized" }
  Write-Warning "ЖИВОЙ РЕЖИМ: настоящие вызовы OpenAI ($Model), не больше $LiveCalls за запуск, около 0.013–0.023 USD каждый."
} else {
  $serverArgs += @("--live-call-limit", "0")
}
if ($WithApprovals) {
  $manifest = "restricted\demo-approvals.json"
  if (-not (Test-Path -LiteralPath (Join-Path $Root $manifest))) {
    throw "Нет $manifest. Создайте (только вымышленные демо-диалоги): .\.venv\Scripts\python.exe -B -m cqa_results.grants --data docs\demo\fictional_new_conversations.json --data-class synthetic_test --reference demo-fictional-conversations --expires 2030-01-01T00:00:00Z --output $manifest  (для -Live добавьте --external openai)"
  }
  $serverArgs += @("--authorization-manifest", $manifest)
}

if (-not $NoBrowser) {
  # Браузер откроется, как только сервер ответит (фоновая задача; сервер работает в этом окне).
  Start-Job -ArgumentList $Url -ScriptBlock {
    param($u)
    for ($i = 0; $i -lt 60; $i++) {
      try { Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 2 | Out-Null; Start-Process $u; return } catch { Start-Sleep -Milliseconds 500 }
    }
  } | Out-Null
}
$mode = if ($Live) { "ЖИВОЙ OpenAI $Model, максимум $LiveCalls вызовов" } else { "платных вызовов 0" }
$approvals = if ($WithApprovals) { "разрешения для демо-диалогов включены" } else { "без разрешений: вставленный диалог -> 403" }
Write-Host "Запускаю CQA: $Url  (чек-лист $Checklist, $mode, ключ проверяющего demo-reviewer-key, $approvals). Остановить: Ctrl+C."
Set-Location -LiteralPath $Root
& $Python @serverArgs
