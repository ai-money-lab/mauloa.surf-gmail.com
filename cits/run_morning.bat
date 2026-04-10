@echo off
REM ================================================================
REM CITS Morning -- CIS ETF Scan (08:30)
REM 9 ETFs only. Fast (~10 seconds).
REM ================================================================

cd /d C:\cits\repo
set PYTHONPATH=C:\cits\repo

REM Logging (define early for sell_2170)
set LOG_DIR=C:\cits\logs
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set LOG_FILE=%LOG_DIR%\morning_%date:~0,4%%date:~5,2%%date:~8,2%.log

REM Auto-update code from GitHub
git pull origin claude/japanese-stock-trading-agent-kJBwp --quiet 2>nul

REM One-time: sell 2170 at market (stop breach 610 -> current 606)
if not exist "C:\cits\logs\.sold_2170" (
    echo %date% %time% Selling 2170 at market >> "%LOG_FILE%"
    C:\cits\venv\Scripts\python.exe -m cits.scripts.sell_2170 >> "%LOG_FILE%" 2>&1
)

REM One-time: update tasks + add startup recovery + VPS agent
if not exist "C:\cits\logs\.schtask_v4" (
    schtasks /Change /TN "CITS_Afternoon" /ST 15:20 >nul 2>&1
    schtasks /Create /TN "CITS_PositionMonitor" /TR "C:\cits\repo\cits\run_monitor.bat" /SC DAILY /ST 09:30 /RI 30 /DU 05:30 /D MON,TUE,WED,THU,FRI /F >nul 2>&1
    schtasks /Create /TN "CITS_StartupRecovery" /TR "C:\cits\repo\cits\run_morning.bat" /SC ONSTART /DELAY 0005:00 /F >nul 2>&1
    schtasks /Create /TN "CITS_VPSAgent" /TR "C:\cits\repo\cits\run_agent.bat" /SC ONSTART /DELAY 0002:00 /F >nul 2>&1
    schtasks /Create /TN "CITS_VPSAgent_Hourly" /TR "C:\cits\repo\cits\run_agent.bat" /SC HOURLY /F >nul 2>&1
    echo %date% %time% Tasks updated v4: +VPSAgent > "C:\cits\logs\.schtask_v4"
)

REM Start VPS agent if not running (polling GitHub for commands every 60s)
wmic process where "commandline like '%%vps_agent%%'" get processid 2>nul | find /i "." >nul
if errorlevel 1 (
    start /B "" C:\cits\venv\Scripts\python.exe -m cits.scripts.vps_agent
    echo %date% %time% VPS agent started >> "%LOG_FILE%"
)

REM Load .env
for /f "usebackq tokens=1,2 delims==" %%a in ("C:\cits\repo\cits\.env") do (
    echo %%a | findstr /r "^#" >nul || (
        if not "%%b"=="" set "%%a=%%b"
    )
)

REM Safety gate for live execution
set CITS_SCHEDULED_RUN=TASKSCHEDULER

REM Order password (separate from API password)
if not defined KABU_ORDER_PASSWORD set KABU_ORDER_PASSWORD=hiroki0380HM

echo ======================================== >> "%LOG_FILE%"
echo CITS Morning -- CIS Full Scan >> "%LOG_FILE%"
echo %date% %time% >> "%LOG_FILE%"
echo ======================================== >> "%LOG_FILE%"

C:\cits\venv\Scripts\python.exe -m cits.scripts.live_trader --mode morning --capital 300000 >> "%LOG_FILE%" 2>&1

REM Report status to GitHub for remote monitoring
call C:\cits\repo\cits\report_status.bat "MORNING" "See morning log for details"

echo ======================================== >> "%LOG_FILE%"
echo Complete: %date% %time% >> "%LOG_FILE%"
echo ======================================== >> "%LOG_FILE%"
