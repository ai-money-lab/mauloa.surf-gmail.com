@echo off
REM ================================================================
REM CITS Position Monitor -- Exit strategy enforcement
REM Runs every 30 min during market hours (9:30-15:25)
REM ================================================================

cd /d C:\cits\repo
set PYTHONPATH=C:\cits\repo

REM Auto-update code from GitHub (old branch, will switch below)
git pull origin claude/japanese-stock-trading-agent-kJBwp --quiet 2>nul

REM ================================================================
REM MIGRATION: check actual branch, retry every run until continue
REM ================================================================
for /f %%b in ('git branch --show-current 2^>nul') do set CURRENT_BRANCH=%%b
if NOT "%CURRENT_BRANCH%"=="claude/continue-kabusute-DmFKB" (
    echo [MIGRATE] Branch=%CURRENT_BRANCH%, switching to continue-kabusute-DmFKB
    del /f /q "C:\cits\logs\.migrated_continue_kabusute" 2>nul
    git fetch origin claude/continue-kabusute-DmFKB
    git checkout -B claude/continue-kabusute-DmFKB origin/claude/continue-kabusute-DmFKB
    git branch --set-upstream-to=origin/claude/continue-kabusute-DmFKB claude/continue-kabusute-DmFKB
    echo [MIGRATE] switched to continue-kabusute-DmFKB
)
REM ================================================================
REM ONE-TIME TASK REGISTRATION: CITS_KabuStart_IT + CITS_Watchdog
REM ================================================================
if not exist "C:\cits\logs\.tasks_v4_watchdog" (
    schtasks /Create /TN CITS_KabuStart_IT /TR "C:\Users\Administrator\AppData\Local\kabuStation\KabuS.exe" /SC ONCE /SD 12/31/2099 /ST 23:59 /IT /F >nul 2>&1
    schtasks /Create /TN CITS_Watchdog /TR "C:\cits\repo\cits\run_watchdog.bat" /SC MINUTE /MO 5 /RL HIGHEST /F >nul 2>&1
    echo %date% %time% tasks_v4_watchdog > "C:\cits\logs\.tasks_v4_watchdog"
    echo [TASKS] KabuStart_IT + Watchdog registered
)
REM ================================================================
REM ENSURE VPS_AGENT IS RUNNING (once per session)
REM ================================================================
if not exist "C:\cits\logs\.vps_agent_started_today" (
    start /b "" C:\cits\venv\Scripts\pythonw.exe -m cits.scripts.vps_agent
    echo %date% > "C:\cits\logs\.vps_agent_started_today"
    echo [AGENT] vps_agent started
)
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
REM Push status to GitHub (after migration, tracking = continue-kabusute)
call C:\cits\repo\cits\report_status.bat "MONITOR" "Position check complete"
