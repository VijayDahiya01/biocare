# Start everything BioCore needs, in the right order, then open the browser.
# Safe to run twice - anything already running is left alone.
. (Join-Path $PSScriptRoot "common.ps1")

Write-Host ""
Write-Host "  Starting BioCore" -ForegroundColor White
Write-Host "  ----------------" -ForegroundColor DarkGray
Say "  This takes about half a minute. You can leave this window open or close it."

$failed = @()

Step "1/5  Database"
if (Test-Port 5544) { Good "already running" }
else {
  & "$PgBin\pg_ctl.exe" -D $PgData -o "-p 5544" -l (Join-Path $env:TEMP "biocore-pg.log") start | Out-Null
  if (Wait-Port 5544 40) { Good "started" } else { Bad "would not start"; $failed += "Database" }
}

Step "2/5  Sessions"
if (Test-Port 6379) { Good "already running" }
elseif (Test-Path $RedisExe) {
  Start-Process -FilePath $RedisExe -ArgumentList "--port 6379","--save ''","--appendonly no" -WindowStyle Hidden
  if (Wait-Port 6379 25) { Good "started" } else { Bad "would not start"; $failed += "Sessions" }
} else { Bad "not installed at $RedisExe"; $failed += "Sessions" }

Step "3/5  Face recognition"
$engine = Get-Setting "CREDENTIAL_ENGINE" "template"
if ($engine -eq "bioverify") {
  Say "  Set up to use the BioVerify service, so nothing to start on this PC."
  $url = Get-Setting "BIOVERIFY_URL"
  try {
    $b = Invoke-RestMethod -Uri "$url/health" -TimeoutSec 20
    if ($b.models_loaded) { Good "BioVerify is reachable and ready" } else { Warn "BioVerify is still loading" }
  } catch { Bad "BioVerify cannot be reached - face registration and gates will not work"; $failed += "BioVerify" }
} elseif (Test-Port 8099) { Good "already running" }
else {
  Start-Process -FilePath $FacePy -ArgumentList "`"$FaceSrv`"" -WindowStyle Minimized
  Say "  First run downloads about 300MB, so this can take a few minutes."
  if (Wait-Port 8099 300) { Good "started" } else { Bad "would not start"; $failed += "Face recognition" }
}

Step "4/5  BioCore application"
if (Test-Port 8080) { Good "already running" }
else {
  $cmd = "cd /d `"$Backend`" && for /f `"usebackq tokens=1,* delims==`" %a in (`".env.real`") do @set `"%a=%b`" && `"$BackendPy`" -m uvicorn app.main:app --host 127.0.0.1 --port 8080"
  Start-Process -FilePath "cmd.exe" -ArgumentList "/c", $cmd -WindowStyle Minimized
  if (Wait-Port 8080 60) { Good "started" } else { Bad "would not start"; $failed += "BioCore application" }
}

Step "5/5  Website"
if (Test-Port 3001) { Good "already running" }
else {
  $cmd = "cd /d `"$Frontend`" && set `"PATH=$NodeDir;%PATH%`" && node node_modules\next\dist\bin\next dev -p 3001"
  Start-Process -FilePath "cmd.exe" -ArgumentList "/c", $cmd -WindowStyle Minimized
  if (Wait-Port 3001 90) { Good "started" } else { Bad "would not start"; $failed += "Website" }
}

Write-Host ""
if ($failed.Count -eq 0) {
  Write-Host "  READY" -ForegroundColor Green
  Write-Host "  Opening http://localhost:3001/admin/login" -ForegroundColor White
  Start-Sleep -Seconds 2
  Start-Process "http://localhost:3001/admin/login"
} else {
  Write-Host "  Some parts did not start: $($failed -join ', ')" -ForegroundColor Red
  Write-Host "  Double-click BioCore-Check for detail." -ForegroundColor White
}
Write-Host ""
Pause-Exit
