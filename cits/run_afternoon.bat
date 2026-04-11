@echo off
REM ================================================================
REM CITS Afternoon -- CIS+KEI Full Market Scan (15:20)
REM ================================================================

cd /d C:\cits\repo
set PYTHONPATH=C:\cits\repo

REM Auto-update code from GitHub
git pull origin claude/continue-kabusute-DmFKB --quiet 2>nul

REM Load .env
for /f "usebackq tokens=1,2 delims==" %%a in ("C:\cits\repo\cits\.env") do (
    echo %%a | findstr /r "^#" >nul || (
        if not "%%b"=="" set "%%a=%%b"
    )
)

REM Safety gate for live execution
set CITS_SCHEDULED_RUN=TASKSCHEDULER
if not defined KABU_ORDER_PASSWORD set KABU_ORDER_PASSWORD=hiroki0380HM

REM Logging
set LOG_DIR=C:\cits\logs
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set LOG_FILE=%LOG_DIR%\afternoon_%date:~0,4%%date:~5,2%%date:~8,2%.log

REM Sell 2170 if not yet sold (failsafe)
if not exist "C:\cits\logs\.sold_2170" (
    echo %date% %time% AFTERNOON: Selling 2170 >> "%LOG_FILE%"
    C:\cits\venv\Scripts\python.exe -m cits.scripts.sell_2170 >> "%LOG_FILE%" 2>&1
)

echo ======================================== >> "%LOG_FILE%"
echo CITS Afternoon -- 15:20 Chart Exit Check + Buy Scan >> "%LOG_FILE%"
echo %date% %time% >> "%LOG_FILE%"
echo ======================================== >> "%LOG_FILE%"

REM Step 1: Position monitor -- sell if chart says EXIT
echo --- STEP 1: Position Monitor (sell check) --- >> "%LOG_FILE%"
C:\cits\venv\Scripts\python.exe -m cits.scripts.position_monitor >> "%LOG_FILE%" 2>&1

REM Step 2: Buy scan -- CIS+KEI on all tickers
echo --- STEP 2: Buy Scan (CIS+KEI) --- >> "%LOG_FILE%"
C:\cits\venv\Scripts\python.exe -m cits.scripts.live_trader --mode afternoon --capital 300000 >> "%LOG_FILE%" 2>&1

REM Report status to GitHub for remote monitoring
call C:\cits\repo\cits\report_status.bat "AFTERNOON" "See afternoon log for details"

echo ======================================== >> "%LOG_FILE%"
echo Complete: %date% %time% >> "%LOG_FILE%"
echo ======================================== >> "%LOG_FILE%"
