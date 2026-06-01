@echo off
title AI Trading Agent
color 0A
echo ==========================================
echo   AI Trading Agent - Starting Services
echo ==========================================
echo.

echo [1/6] Checking Docker...
docker ps >nul 2>&1
if errorlevel 1 (
    echo     Starting Docker Desktop, wait 30s...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    timeout /t 30 /nobreak >nul
) else (
    echo     Docker OK
)

echo [2/6] Starting PostgreSQL + Redis...
cd /d "D:\XAU\ai-trading-agent"
docker compose up -d >nul 2>&1
echo     DB ports 5434 / 6380 up

echo [3/6] Opening MetaTrader 5 EXNESS...
start "" "C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe"
echo     Waiting 15s for MT5...
timeout /t 15 /nobreak >nul

echo [4/6] Starting MT5 Bridge (8001)...
start "MT5 Bridge" /min powershell -NoExit -Command "Set-Location D:\XAU\ai-trading-agent\mt5_bridge; .venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8001"

echo [5/6] Starting Backend (8000)...
start "Backend" /min powershell -NoExit -Command "Set-Location D:\XAU\ai-trading-agent\backend; .venv\Scripts\python.exe -m uvicorn app.main:app --port 8000"

echo [6/6] Starting Frontend (3000)...
start "Frontend" /min powershell -NoExit -Command "Set-Location D:\XAU\ai-trading-agent\frontend; npm run dev"

echo.
echo Waiting 25s for services...
timeout /t 25 /nobreak >nul
start http://localhost:3000

echo.
echo ==========================================
echo   DONE - 3 windows running (minimized)
echo   Frontend : http://localhost:3000
echo   Mode     : MICRO (real demo orders 0.01)
echo   Keep the 3 windows OPEN
echo ==========================================
echo.
pause
