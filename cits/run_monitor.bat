@echo off
REM ================================================================
REM CITS Position Monitor -- Exit strategy enforcement
REM Runs every 30 min during market hours (9:30-15:25)
REM ================================================================

cd /d C:\cits\repo
set PYTHONPATH=C:\cits\repo
set CITS_SCHEDULED_RUN=TASKSCHEDULER

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
