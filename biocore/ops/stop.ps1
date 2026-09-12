# Stop BioCore. Nothing is deleted - all records stay exactly as they are.
. (Join-Path $PSScriptRoot "common.ps1")

Write-Host ""
Write-Host "  Stopping BioCore" -ForegroundColor White
Write-Host "  ----------------" -ForegroundColor DarkGray
Say "  Your data is not touched. Start it again any time."

Step "Website, application and face recognition"
foreach ($p in @(3001, 8080, 8099)) {
  $procId = Get-PortPid $p
  if ($procId) {
    try { Stop-Process -Id $procId -Force -ErrorAction Stop; Good "stopped (port $p)" }
    catch { Warn "could not stop the program on port $p" }
  } else { Say "  nothing was running on port $p" }
}

Step "Database"
if (Test-Port 5544) {
  & "$PgBin\pg_ctl.exe" -D $PgData -m fast stop | Out-Null
  Start-Sleep -Seconds 3
  if (Test-Port 5544) { Warn "the database is still running" } else { Good "stopped cleanly" }
} else { Say "  was not running" }

Step "Sessions"
Say "  Left running on purpose - it is shared with other things on this PC,"
Say "  it holds nothing permanent, and it costs almost nothing to leave up."

Write-Host ""
Write-Host "  STOPPED" -ForegroundColor Green
Write-Host ""
Pause-Exit
