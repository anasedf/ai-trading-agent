# check_health.ps1 - one-shot health check for the AI Trading Agent stack.
# Run:  powershell -ExecutionPolicy Bypass -File check_health.ps1
# Verifies Docker (Postgres/Redis), MT5 Bridge, Backend, Frontend, and the
# backend's view of MT5 + AI. Exits 0 if all critical services are up.

$ErrorActionPreference = "SilentlyContinue"
$ok = $true

function Line($name, $good, $detail) {
    $mark = if ($good) { "[ OK ]" } else { "[FAIL]" }
    $color = if ($good) { "Green" } else { "Red" }
    Write-Host ("{0}  {1,-16} {2}" -f $mark, $name, $detail) -ForegroundColor $color
}

Write-Host "=== AI Trading Agent - health check ===" -ForegroundColor Cyan

# 1. Docker containers
$pg = (docker ps --filter "name=goldbot-postgres" --format "{{.Names}}") 2>$null
$rd = (docker ps --filter "name=goldbot-redis" --format "{{.Names}}") 2>$null
$pgUp = ($pg -ne $null -and $pg -ne "")
$rdUp = ($rd -ne $null -and $rd -ne "")
Line "PostgreSQL" $pgUp $(if ($pgUp) { "container up (port 5434)" } else { "NOT running - docker compose up -d" })
Line "Redis" $rdUp $(if ($rdUp) { "container up (port 6380)" } else { "NOT running - docker compose up -d" })
if (-not $pgUp -or -not $rdUp) { $ok = $false }

# 2. MT5 Bridge
try {
    $b = (Invoke-WebRequest "http://localhost:8001/health" -UseBasicParsing -TimeoutSec 5).Content | ConvertFrom-Json
    $up = ($b.status -eq "ok" -and $b.mt5 -ne $null)
    Line "MT5 Bridge" $up "$($b.status) login=$($b.mt5.login) server=$($b.mt5.server)"
    if (-not $up) { $ok = $false }
} catch {
    Line "MT5 Bridge" $false "DOWN (port 8001) - is MT5 open and bridge running?"
    $ok = $false
}

# 3. Backend
try {
    $h = (Invoke-WebRequest "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 5).Content | ConvertFrom-Json
    Line "Backend" ($h.status -eq "ok") "status=$($h.status) bot=$($h.bot_state)"
    Line "  MT5 link" ([bool]$h.mt5_connected) $(if ($h.mt5_connected) { "backend sees MT5" } else { "backend cannot reach bridge" })
    Line "  Redis link" ([bool]$h.redis_connected) ""
    Line "  AI" ([bool]$h.ai_available) $(if ($h.ai_available) { "Claude available" } else { "AI not available" })
    if ($h.status -ne "ok") { $ok = $false }
} catch {
    Line "Backend" $false "DOWN (port 8000)"
    $ok = $false
}

# 4. Frontend
try {
    $f = (Invoke-WebRequest "http://localhost:3000" -UseBasicParsing -TimeoutSec 8).StatusCode
    Line "Frontend" ($f -eq 200) "HTTP $f (port 3000)"
    if ($f -ne 200) { $ok = $false }
} catch {
    Line "Frontend" $false "DOWN (port 3000) - npm run dev not ready?"
    $ok = $false
}

Write-Host ""
if ($ok) {
    Write-Host "ALL CRITICAL SERVICES UP" -ForegroundColor Green
    exit 0
} else {
    Write-Host "SOME SERVICES DOWN - see above" -ForegroundColor Red
    exit 1
}
