@echo off
REM ================================================================
REM CITS VPS Agent -- GitHub polling command executor
REM Persistent background process. Polls every 60 seconds.
REM ================================================================

cd /d C:\cits\repo
set PYTHONPATH=C:\cits\repo

REM Load .env
for /f "usebackq tokens=1,2 delims==" %%a in ("C:\cits\repo\cits\.env") do (
    echo %%a | findstr /r "^#" >nul || (
        if not "%%b"=="" set "%%a=%%b"
    )
)

set CITS_SCHEDULED_RUN=TASKSCHEDULER
if not defined KABU_ORDER_PASSWORD set KABU_ORDER_PASSWORD=hiroki0380HM

set LOG_DIR=C:\cits\logs
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

REM Run agent in foreground (use 'start /B' for background)
C:\cits\venv\Scripts\python.exe -m cits.scripts.vps_agent
