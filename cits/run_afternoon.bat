@echo off
REM ================================================================
REM CITS Afternoon -- Kei-kun + ETF Fallback (15:00)
REM Kei-kun on cached data (instant) + CIS ETF fallback
REM Orders placed by 15:01, well before 15:25 pre-closing
REM ================================================================

cd /d C:\cits\repo
set PYTHONPATH=C:\cits\repo

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
