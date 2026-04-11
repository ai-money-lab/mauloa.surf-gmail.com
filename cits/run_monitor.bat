@echo off
REM ================================================================
REM CITS Position Monitor -- Exit strategy enforcement
REM Runs every 30 min during market hours (9:30-15:25)
REM ================================================================

cd /d C:\cits\repo
set PYTHONPATH=C:\cits\repo

REM Auto-update code from GitHub
git pull --quiet 2>nul

set CITS_SCHEDULED_RUN=TASKSCHEDULER
if not defined KABU_ORDER_PASSWORD set KABU_ORDER_PASSWORD=hiroki0380HM

for /f "usebackq tokens=1,2 delims==" %%a in ("C:\cits\repo\cits\.env") do (
    echo %%a | findstr /r "^#" >nul || (
        if not "%%b"=="" set "%%a=%%b"
    )
)

set LOG_DIR=C:\cits\logs
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set LOG_FILE=%LOG_DIR%\monitor_%date:~0,4%%date:~5,2%%date:~8,2%.log

echo %date% %time% MONITOR >> "%LOG_FILE%"
C:\cits\venv\Scripts\python.exe -m cits.scripts.position_monitor >> "%LOG_FILE%" 2>&1

REM Push status to GitHub every 30 min for remote monitoring
call C:\cits\repo\cits\report_status.bat "MONITOR" "Position check complete"
