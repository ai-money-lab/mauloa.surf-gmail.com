@echo off
REM ================================================================
REM CITS Afternoon -- CIS+KEI Full Market Scan (15:20)
REM CIS on all cached tickers + KEI on cached data + fresh ETFs
REM Task Scheduler: 15:20 (after chart patterns finalize)
REM ================================================================

cd /d C:\cits\repo
set PYTHONPATH=C:\cits\repo

REM Auto-update code from GitHub
git pull origin claude/japanese-stock-trading-agent-kJBwp --quiet 2>nul

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
set LOG_FILE=%LOG_DIR%\afternoon_%date:~0,4%%date:~5,2%%date:~8,2%.log

echo ======================================== >> "%LOG_FILE%"
echo CITS Afternoon -- Kei-kun + ETF Fallback >> "%LOG_FILE%"
echo %date% %time% >> "%LOG_FILE%"
echo ======================================== >> "%LOG_FILE%"

C:\cits\venv\Scripts\python.exe -m cits.scripts.live_trader --mode afternoon --capital 300000 >> "%LOG_FILE%" 2>&1

echo ======================================== >> "%LOG_FILE%"
echo Complete: %date% %time% >> "%LOG_FILE%"
echo ======================================== >> "%LOG_FILE%"
