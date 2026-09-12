# Is BioCore working right now? Plain English, no jargon.
. (Join-Path $PSScriptRoot "common.ps1")

Write-Host ""
Write-Host "  BioCore - system check" -ForegroundColor White
Write-Host "  ----------------------" -ForegroundColor DarkGray

$broken = @()

Step "Are the parts running?"
foreach ($s in $Services) {
  if (Test-Port $s.Port) { Good "$($s.Name) - $($s.Why)" }
  else { Bad "$($s.Name) is NOT running - $($s.Why)"; $broken += $s.Name }
}

Step "Can the app answer?"
try {
  $h = Invoke-RestMethod -Uri "http://127.0.0.1:8080/api/v1/health" -TimeoutSec 10
  if ($h.success) { Good "the application is responding" } else { Bad "the application replied oddly"; $broken += "app" }
} catch { Bad "the application is not responding"; $broken += "app" }

Step "Can people open the screens?"
try {
  $r = Invoke-WebRequest -Uri "http://localhost:3001/admin/login" -TimeoutSec 20 -UseBasicParsing
  if ($r.StatusCode -eq 200) { Good "the sign-in page loads" } else { Bad "the sign-in page returned $($r.StatusCode)"; $broken += "web" }
} catch { Bad "the website is not responding"; $broken += "web" }

Step "Face recognition"
$engine = Get-Setting "CREDENTIAL_ENGINE" "template"
if ($engine -eq "bioverify") {
  $url = Get-Setting "BIOVERIFY_URL"
  Say "  Using the BioVerify service at $url"
  try {
    $b = Invoke-RestMethod -Uri "$url/health" -TimeoutSec 20
    if ($b.models_loaded) { Good "BioVerify is reachable and ready" }
    else { Warn "BioVerify is reachable but still loading - the first face check may be slow" }
  } catch {
    Bad "BioVerify cannot be reached - nobody can register a face or pass a gate"
    Say  "        Check with whoever runs that server."
    $broken += "BioVerify"
  }
} else {
  Say "  Using the face engine on this PC"
  if (Test-Port 8099) { Good "the face engine is running" }
  else { Bad "the face engine is NOT running - nobody can register a face or pass a gate"; $broken += "face engine" }
}

Step "Is anything unsafe left switched on?"
$devFlags = @(
  @{ Key = "DEV_LOGIN";          Bad = "true";  Msg = "ANYONE can sign in as anyone - turn this off" }
  @{ Key = "DEMO_DISABLE_TOTP";  Bad = "true";  Msg = "admins sign in without a 2FA code" }
  @{ Key = "FAKE_GOV_IDENTITY";  Bad = "true";  Msg = "ID checks are pretend, not real" }
)
$unsafe = 0
foreach ($f in $devFlags) {
  if ((Get-Setting $f.Key).ToLower() -eq $f.Bad) { Warn "$($f.Key) is on - $($f.Msg)"; $unsafe++ }
}
if ($unsafe -eq 0) { Good "no test shortcuts are switched on" }

Write-Host ""
if ($broken.Count -eq 0) {
  Write-Host "  READY - everything needed is working." -ForegroundColor Green
  Write-Host "  Open: http://localhost:3001/admin/login" -ForegroundColor White
  if ($unsafe -gt 0) {
    Write-Host "  ($unsafe test shortcut(s) still on - fine for testing, not for real users.)" -ForegroundColor Yellow
  }
} else {
  Write-Host "  NOT READY - these are down: $($broken -join ', ')" -ForegroundColor Red
  Write-Host "  Try double-clicking BioCore-Start first." -ForegroundColor White
}
Write-Host ""
Pause-Exit
