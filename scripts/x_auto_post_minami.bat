@echo off
REM === X 自動投稿バッチ（みなみアカウント用） ===
REM タスクスケジューラから呼び出される
REM みなみアカウント専用の自動投稿スクリプト

cd /d "%~dp0\.."

REM みなみ用Chromeプロファイルを設定
set CHROME_PROFILE_DIR=%~dp0\..\chrome-profiles\minami

call venv\Scripts\activate.bat 2>nul

set PYTHONPATH=%cd%
python -m system_a.generate_and_post --account minami >> logs\x_auto_post_minami.log 2>&1

echo [%date% %time%] Finished >> logs\x_auto_post_minami.log
