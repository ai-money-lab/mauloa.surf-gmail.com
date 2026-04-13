@echo off
REM ================================================================
REM CITS Git Repair -- 毎朝06:00実行
REM git.exe のVC++ランタイム破損を予防・修復する。
REM winget upgrade で最新のGit for Windowsを維持する。
REM ================================================================

set LOG_DIR=C:\cits\logs
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo [%DATE% %TIME%] CITS_GitRepair: start >> "%LOG_DIR%\gitrepair.log" 2>&1

REM 1. まずgitが動くか確認
git --version >> "%LOG_DIR%\gitrepair.log" 2>&1
if %ERRORLEVEL% neq 0 (
    echo [%DATE% %TIME%] git.exe broken -- running repair >> "%LOG_DIR%\gitrepair.log" 2>&1
)

REM 2. winget で Git.Git を最新に保つ（すでに最新なら no-op）
winget upgrade Git.Git --silent --accept-package-agreements --accept-source-agreements >> "%LOG_DIR%\gitrepair.log" 2>&1

REM 3. VC++ランタイム（git依存）を最新に保つ
winget upgrade Microsoft.VCRedist.2015+.x64 --silent --accept-package-agreements --accept-source-agreements >> "%LOG_DIR%\gitrepair.log" 2>&1

REM 4. 修復後の確認
git --version >> "%LOG_DIR%\gitrepair.log" 2>&1

echo [%DATE% %TIME%] CITS_GitRepair: done >> "%LOG_DIR%\gitrepair.log" 2>&1
