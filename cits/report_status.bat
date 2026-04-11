@echo off
REM ================================================================
REM CITS Status Reporter -- Push execution status to GitHub
REM Called at the end of each bat file to report results
REM ================================================================

cd /d C:\cits\repo
set STATUS_FILE=cits\logs\vps_status.txt

echo ======================================== >> "%STATUS_FILE%"
echo %date% %time% [%~1] >> "%STATUS_FILE%"
echo %~2 >> "%STATUS_FILE%"
echo ======================================== >> "%STATUS_FILE%"

REM Push status to GitHub (best effort, don't block on failure)
git add "%STATUS_FILE%" >nul 2>&1
git add "cits\data\vps_status.json" >nul 2>&1
git commit -m "status: %~1 %date% %time%" --quiet >nul 2>&1
git push origin claude/japanese-stock-trading-agent-kJBwp --quiet >nul 2>&1
