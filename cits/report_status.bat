@echo off
REM ================================================================
REM CITS Status Reporter -- Push execution status to GitHub
REM Read fresh from disk via 'call', so git pull updates take effect.
REM This version migrates VPS to continue-kabusute before pushing.
REM ================================================================

cd /d C:\cits\repo
set STATUS_FILE=cits\logs\vps_status.txt

echo ======================================== >> "%STATUS_FILE%"
echo %date% %time% [%~1] >> "%STATUS_FILE%"
echo %~2 >> "%STATUS_FILE%"
echo ======================================== >> "%STATUS_FILE%"

REM ================================================================
REM MIGRATION: switch to continue-kabusute before pushing
REM (marker deleted; uses branch check so it retries until success)
REM ================================================================
del /f /q "C:\cits\logs\.migrated_continue_kabusute" 2>nul
for /f %%b in ('git branch --show-current 2^>nul') do set CB=%%b
if NOT "%CB%"=="claude/continue-kabusute-DmFKB" (
    git stash 2>nul
    git fetch origin claude/continue-kabusute-DmFKB --quiet 2>nul
    git checkout -B claude/continue-kabusute-DmFKB origin/claude/continue-kabusute-DmFKB 2>nul
    git branch --set-upstream-to=origin/claude/continue-kabusute-DmFKB claude/continue-kabusute-DmFKB 2>nul
)

REM Push status to continue-kabusute
git add -f "%STATUS_FILE%" >nul 2>&1
git add -f "cits\data\vps_status.json" >nul 2>&1
git commit -m "status: %~1 %date% %time%" --quiet >nul 2>&1
git push origin claude/continue-kabusute-DmFKB --quiet >nul 2>&1
