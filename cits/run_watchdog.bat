@echo off
REM ================================================================
REM CITS Watchdog -- Self-Healing Monitor (every 5 min)
REM Checks kabuStation, vps_agent, and all scheduled tasks.
REM Re-registers any missing tasks automatically.
REM ================================================================

cd /d C:\cits\repo
set PYTHONPATH=C:\cits\repo

REM Auto-update code from GitHub
git pull --quiet 2>nul

REM Load .env
for /f "usebackq tokens=1,2 delims==" %%a in ("C:\cits\repo\cits\.env") do (
    echo %%a | findstr /r "^#" >nul || (
        if not "%%b"=="" set "%%a=%%b"
    )
)

set LOG_DIR=C:\cits\logs
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

C:\cits\venv\Scripts\python.exe -m cits.scripts.watchdog >> "%LOG_DIR%\watchdog.log" 2>&1
