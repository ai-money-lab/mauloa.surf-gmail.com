@echo off
REM ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REM CITS 毎日のトレード分析（API不要版）
REM タスクスケジューラで朝8:30に自動実行推奨
REM ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

cd /d %~dp0
call venv\Scripts\activate.bat
set PYTHONPATH=%cd%

REM .env読み込み
for /f "tokens=1,2 delims==" %%a in (cits\.env) do (
    echo %%a | findstr /r "^#" >nul || (
        if not "%%b"=="" set %%a=%%b
    )
)

echo ========================================
echo CITS 日次トレード分析
echo %date% %time%
echo ========================================

REM CIS式成功方程式ソルバー実行（API不要）
python -m cits.scripts.solve_equation --capital 100000

echo ========================================
echo 分析完了
echo ========================================
pause
