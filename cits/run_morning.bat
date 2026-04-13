@echo off
REM ================================================================
REM CITS Morning -- CIS Full Scan (08:30)
REM ================================================================

cd /d C:\cits\repo
set PYTHONPATH=C:\cits\repo

REM Logging (define early for sell_2170)
set LOG_DIR=C:\cits\logs
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set LOG_FILE=%LOG_DIR%\morning_%date:~0,4%%date:~5,2%%date:~8,2%.log

REM Auto-update code from GitHub
git pull --quiet 2>nul

REM One-time: sell 2170 at market (stop breach 610 -> current 606)
if not exist "C:\cits\logs\.sold_2170" (
    echo %date% %time% Selling 2170 at market >> "%LOG_FILE%"
    C:\cits\venv\Scripts\python.exe -m cits.scripts.sell_2170 >> "%LOG_FILE%" 2>&1
)

REM One-time: register ALL CITS tasks (v5 = comprehensive, new VPS ready)
if not exist "C:\cits\logs\.schtask_v5" (
    schtasks /Create /TN CITS_KabuStation_Start /TR "C:\Users\Administrator\AppData\Local\kabuStation\KabuS.exe" /SC DAILY /ST 08:25 /D MON,TUE,WED,THU,FRI /IT /F >nul 2>&1
    schtasks /Create /TN CITS_KabuStart_IT /TR "C:\Users\Administrator\AppData\Local\kabuStation\KabuS.exe" /SC ONCE /SD 12/31/2099 /ST 23:59 /IT /F >nul 2>&1
    schtasks /Create /TN CITS_PositionMonitor /TR "C:\cits\repo\cits\run_monitor.bat" /SC MINUTE /MO 30 /ST 09:30 /ET 15:25 /RL HIGHEST /F >nul 2>&1
    schtasks /Create /TN CITS_Prefetch /TR "C:\cits\repo\cits\run_prefetch.bat" /SC DAILY /ST 14:00 /D MON,TUE,WED,THU,FRI /RL HIGHEST /F >nul 2>&1
    schtasks /Create /TN CITS_Afternoon /TR "C:\cits\repo\cits\run_afternoon.bat" /SC DAILY /ST 15:20 /D MON,TUE,WED,THU,FRI /RL HIGHEST /F >nul 2>&1
    schtasks /Create /TN CITS_Watchdog /TR "C:\cits\repo\cits\run_watchdog.bat" /SC MINUTE /MO 5 /RL HIGHEST /F >nul 2>&1
    schtasks /Create /TN CITS_VPSAgent /TR "C:\cits\repo\cits\run_agent.bat" /SC ONSTART /DELAY 0002:00 /RL HIGHEST /F >nul 2>&1
    schtasks /Create /TN CITS_StartupRecovery /TR "C:\cits\repo\cits\run_morning.bat" /SC ONSTART /DELAY 0005:00 /F >nul 2>&1
    echo %date% %time% Tasks v5: all 8 CITS tasks registered > "C:\cits\logs\.schtask_v5"
    echo [TASKS] v5: All 8 CITS tasks registered >> "%LOG_FILE%"
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

REM ================================================================
REM ① kabuStation ログイン確認（毎回必須 -- 発注前に必ずログイン）
REM    already logged in → 即時リターン
REM    not logged in    → kill/restart + VNC + 2FA (最大5分)
REM ================================================================
echo %date% %time% [LOGIN] kabuStation login check... >> "%LOG_FILE%"
C:\cits\venv\Scripts\python.exe -m cits.scripts.kabu_auto_login_vps >> "%LOG_FILE%" 2>&1
if %ERRORLEVEL% neq 0 (
    echo %date% %time% [ERROR] kabuStation login FAILED -- trading ABORTED >> "%LOG_FILE%"
    call C:\cits\repo\cits\report_status.bat "LOGIN_FAIL" "kabu login failed - morning trading aborted"
    exit /b 1
)
echo %date% %time% [LOGIN] kabuStation: LOGGED IN >> "%LOG_FILE%"

C:\cits\venv\Scripts\python.exe -m cits.scripts.live_trader --mode morning --capital 300000 >> "%LOG_FILE%" 2>&1

REM Report status to GitHub for remote monitoring
call C:\cits\repo\cits\report_status.bat "MORNING" "See morning log for details"

echo ======================================== >> "%LOG_FILE%"
echo Complete: %date% %time% >> "%LOG_FILE%"
echo ======================================== >> "%LOG_FILE%"
