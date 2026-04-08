@echo off
REM ================================================================
REM CITS Prefetch -- Data Collection (14:00)
REM Fetch ~3,950 tickers + 9 ETFs. Save to disk cache.
REM No trading. Takes 5-7 minutes.
REM ================================================================

cd /d C:\cits\repo
set PYTHONPATH=C:\cits\repo

REM Auto-update code from GitHub
git pull origin claude/japanese-stock-trading-agent-kJBwp --quiet 2>nul

REM Load .env (not needed for prefetch, but for consistency)
for /f "usebackq tokens=1,2 delims==" %%a in ("C:\cits\repo\cits\.env") do (
    echo %%a | findstr /r "^#" >nul || (
        if not "%%b"=="" set "%%a=%%b"
    )
)

REM Logging
set LOG_DIR=C:\cits\logs
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set LOG_FILE=%LOG_DIR%\prefetch_%date:~0,4%%date:~5,2%%date:~8,2%.log

echo ======================================== >> "%LOG_FILE%"
echo CITS Prefetch -- Data Collection >> "%LOG_FILE%"
echo %date% %time% >> "%LOG_FILE%"
echo ======================================== >> "%LOG_FILE%"

C:\cits\venv\Scripts\python.exe -m cits.scripts.live_trader --mode prefetch --capital 300000 >> "%LOG_FILE%" 2>&1

echo ======================================== >> "%LOG_FILE%"
echo Complete: %date% %time% >> "%LOG_FILE%"
echo ======================================== >> "%LOG_FILE%"
