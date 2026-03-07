@echo off
REM ============================================
REM System A: スケジュール済み投稿の実行
REM Windowsタスクスケジューラから呼び出される
REM ============================================

cd /d "%~dp0"

REM Python実行
python system_a\run_scheduled_posts.py

if %ERRORLEVEL% neq 0 (
    echo [ERROR] run_scheduled_posts.py failed with exit code %ERRORLEVEL%
    exit /b %ERRORLEVEL%
)
