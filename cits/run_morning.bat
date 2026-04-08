@echo off
REM ================================================================
REM CITS Morning -- CIS ETF Scan (08:30)
REM 9 ETFs only. Fast (~10 seconds).
REM ================================================================

cd /d C:\cits\repo
set PYTHONPATH=C:\cits\repo

REM Auto-update code from GitHub
git pull origin claude/japanese-stock-trading-agent-kJBwp --quiet 2>nul

REM One-time: update CITS_Afternoon to 15:20 + register position monitor
if not exist "C:\cits\logs\.schtask_v2" (
    schtasks /Change /TN "CITS_Afternoon" /ST 15:20 >nul 2>&1
    REM Position monitor: every 30 min from 09:30 to 15:00 on weekdays
    schtasks /Create /TN "CITS_PositionMonitor" /TR "C:\cits\repo\cits\run_monitor.bat" /SC DAILY /ST 09:30 /RI 30 /DU 05:30 /D MON,TUE,WED,THU,FRI /F >nul 2>&1
    echo %date% %time% Tasks updated: Afternoon=15:20, Monitor=every30min > "C:\cits\logs\.schtask_v2"
)

REM Load .env
for /f "usebackq tokens=1,2 delims==" %%a in ("C:\cits\repo\cits\.env") do (
    echo %%a | findstr /r "^#" >nul || (
        if not "%%b"=="" set "%%a=%%b"
    )
)

REM Safety gate for live execution
set CITS_SCHEDULED_RUN=TASKSCHEDULER

REM Logging
set LOG_DIR=C:\cits\logs
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set LOG_FILE=%LOG_DIR%\morning_%date:~0,4%%date:~5,2%%date:~8,2%.log

echo ======================================== >> "%LOG_FILE%"
echo CITS Morning -- CIS ETF Scan >> "%LOG_FILE%"
echo %date% %time% >> "%LOG_FILE%"
echo ======================================== >> "%LOG_FILE%"

C:\cits\venv\Scripts\python.exe -m cits.scripts.live_trader --mode morning --capital 300000 >> "%LOG_FILE%" 2>&1

echo ======================================== >> "%LOG_FILE%"
echo Complete: %date% %time% >> "%LOG_FILE%"
echo ======================================== >> "%LOG_FILE%"
