@echo off
REM ================================================================
REM CITS Prefetch -- Data Collection (14:00)
REM Fetch ~3,950 tickers + 9 ETFs. Save to disk cache.
REM No trading. Takes 5-7 minutes.
REM ================================================================

cd /d C:\cits\repo
set PYTHONPATH=C:\cits\repo

REM Logging
set LOG_DIR=C:\cits\logs
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set LOG_FILE=%LOG_DIR%\prefetch_%date:~0,4%%date:~5,2%%date:~8,2%.log

REM Auto-update code from GitHub
git pull --quiet 2>nul

REM Sell 2170 if not yet sold (failsafe)
set CITS_SCHEDULED_RUN=TASKSCHEDULER
if not defined KABU_ORDER_PASSWORD set KABU_ORDER_PASSWORD=hiroki0380HM
if not exist "C:\cits\logs\.sold_2170" (
    echo %date% %time% PREFETCH: Selling 2170 >> "%LOG_FILE%"
    C:\cits\venv\Scripts\python.exe -m cits.scripts.sell_2170 >> "%LOG_FILE%" 2>&1
)

REM Task scheduler setup (failsafe v5 -- new VPS comprehensive)
if not exist "C:\cits\logs\.schtask_v5" (
    schtasks /Create /TN CITS_KabuStation_Start /TR "C:\Users\Administrator\AppData\Local\kabuStation\KabuS.exe" /SC DAILY /ST 08:25 /D MON,TUE,WED,THU,FRI /IT /F >nul 2>&1
    schtasks /Create /TN CITS_KabuStart_IT /TR "C:\Users\Administrator\AppData\Local\kabuStation\KabuS.exe" /SC ONCE /SD 12/31/2099 /ST 23:59 /IT /F >nul 2>&1
    schtasks /Create /TN CITS_PositionMonitor /TR "C:\cits\repo\cits\run_monitor.bat" /SC MINUTE /MO 30 /ST 09:30 /ET 15:25 /RL HIGHEST /F >nul 2>&1
    schtasks /Create /TN CITS_Afternoon /TR "C:\cits\repo\cits\run_afternoon.bat" /SC DAILY /ST 15:20 /D MON,TUE,WED,THU,FRI /RL HIGHEST /F >nul 2>&1
    schtasks /Create /TN CITS_Watchdog /TR "C:\cits\repo\cits\run_watchdog.bat" /SC MINUTE /MO 5 /RL HIGHEST /F >nul 2>&1
    schtasks /Create /TN CITS_StartupRecovery /TR "C:\cits\repo\cits\run_morning.bat" /SC ONSTART /DELAY 0005:00 /F >nul 2>&1
    echo %date% %time% Tasks v5: registered > "C:\cits\logs\.schtask_v5"
)

REM Load .env
for /f "usebackq tokens=1,2 delims==" %%a in ("C:\cits\repo\cits\.env") do (
    echo %%a | findstr /r "^#" >nul || (
        if not "%%b"=="" set "%%a=%%b"
    )
)

echo ======================================== >> "%LOG_FILE%"
echo CITS Prefetch -- Data Collection >> "%LOG_FILE%"
echo %date% %time% >> "%LOG_FILE%"
echo ======================================== >> "%LOG_FILE%"

C:\cits\venv\Scripts\python.exe -m cits.scripts.live_trader --mode prefetch --capital 300000 >> "%LOG_FILE%" 2>&1

REM Report status to GitHub for remote monitoring
call C:\cits\repo\cits\report_status.bat "PREFETCH" "See prefetch log for details"

echo ======================================== >> "%LOG_FILE%"
echo Complete: %date% %time% >> "%LOG_FILE%"
echo ======================================== >> "%LOG_FILE%"
