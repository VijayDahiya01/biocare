# Shared settings and helpers for the BioCore start / stop / check scripts.
#
# Machine-specific paths live HERE and nowhere else. If this project moves to another PC,
# these five lines are the only thing to change.

$ErrorActionPreference = "Stop"

$Root      = Split-Path -Parent (Split-Path -Parent $PSCommandPath)   # ...\prod\biocore
$Backend   = Join-Path $Root "backend"
$Frontend  = Join-Path $Root "frontend"
$FaceSrv   = Join-Path $Root "face-engine\server.py"

$PgBin     = "C:\Users\DELL\tools\pg17\bin"
$PgData    = "C:\Users\DELL\AppData\Local\biocore_pgdata"
$RedisExe  = "C:\Users\DELL\tools\redis\redis-server.exe"
$NodeDir   = "C:\Users\DELL\tools\node24"
$FacePy    = "C:\Users\DELL\bcface\Scripts\python.exe"
$BackendPy = Join-Path $Backend ".venv\Scripts\python.exe"

$Services = @(
  @{ Name = "Database";     Port = 5544; Why = "stores everyone's records" }
  @{ Name = "Sessions";     Port = 6379; Why = "keeps people signed in, delivers sign-in codes" }
  @{ Name = "BioCore";      Port = 8080; Why = "the application itself" }
  @{ Name = "Website";      Port = 3001; Why = "the screens you click" }
)

function Test-Port([int]$Port) {
  try {
    $c = New-Object Net.Sockets.TcpClient
    $c.Connect("127.0.0.1", $Port)
    $c.Close()
    return $true
  } catch { return $false }
}

function Wait-Port([int]$Port, [int]$Seconds = 60) {
  for ($i = 0; $i -lt $Seconds; $i++) {
    if (Test-Port $Port) { return $true }
    Start-Sleep -Seconds 1
  }
  return $false
}

function Get-PortPid([int]$Port) {
  $line = (netstat -ano | Select-String ":$Port\s" | Select-String "LISTENING" | Select-Object -First 1)
  if (-not $line) { return $null }
  return ($line.ToString().Trim() -split "\s+")[-1]
}

# Reads one KEY=value out of backend\.env.real without needing anything installed.
function Get-Setting([string]$Key, [string]$Default = "") {
  $file = Join-Path $Backend ".env.real"
  if (-not (Test-Path $file)) { return $Default }
  $m = Select-String -Path $file -Pattern "^$Key=(.*)$" | Select-Object -First 1
  if (-not $m) { return $Default }
  return $m.Matches[0].Groups[1].Value.Trim()
}

function Say([string]$Text)  { Write-Host $Text }
function Good([string]$Text) { Write-Host "  OK    $Text" -ForegroundColor Green }
function Bad([string]$Text)  { Write-Host "  STOP  $Text" -ForegroundColor Red }
function Warn([string]$Text) { Write-Host "  NOTE  $Text" -ForegroundColor Yellow }
function Step([string]$Text) { Write-Host "`n$Text" -ForegroundColor Cyan }

function Pause-Exit {
  # Keeps the window open for a double-click. Skipped when run from a script or CI, where
  # there is no keyboard and ReadKey would throw.
  if ($env:BIOCORE_NOPAUSE) { return }
  Write-Host ""
  Write-Host "Press any key to close this window..." -ForegroundColor DarkGray
  try { $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown") } catch { Start-Sleep -Seconds 2 }
}
