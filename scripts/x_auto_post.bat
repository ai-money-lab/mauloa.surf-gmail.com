@echo off
REM === X 自動投稿バッチ ===
REM タスクスケジューラから呼び出される

cd /d "%~dp0\.."
call venv\Scripts\activate.bat 2>nul

set PYTHONPATH=%cd%
python -m system_a.generate_and_post >> logs\x_auto_post.log 2>&1

echo [%date% %time%] Finished >> logs\x_auto_post.log
