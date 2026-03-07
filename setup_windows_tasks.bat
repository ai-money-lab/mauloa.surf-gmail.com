@echo off
REM ============================================
REM System A: Windowsタスクスケジューラ設定
REM
REM 4つのタスクを登録:
REM   06:00 - daily_pipeline.py  (収集→分析→変換→スケジュール生成)
REM   07:00 - run_scheduled_posts.py (朝の投稿)
REM   12:00 - run_scheduled_posts.py (昼の投稿)
REM   19:00 - run_scheduled_posts.py (夜の投稿)
REM
REM Usage:
REM   コマンドプロンプトで実行:
REM   > setup_windows_tasks.bat
REM ============================================

set PROJECT_DIR=%~dp0
set PYTHON_CMD=C:\Users\maulo\AppData\Local\Programs\Python\Python312\python.exe

echo ============================================
echo System A - Task Scheduler Setup
echo ============================================
echo.
echo Project: %PROJECT_DIR%
echo Python:  %PYTHON_CMD%
echo.

REM --- Task 1: Daily Pipeline (06:00) ---
echo [1/4] Creating task: SystemA_DailyPipeline (06:00)...
schtasks /Create /TN "SystemA_DailyPipeline" /TR "\"%PYTHON_CMD%\" \"%PROJECT_DIR%system_a\daily_pipeline.py\"" /SC DAILY /ST 06:00 /F
if %ERRORLEVEL% equ 0 (
    echo   OK: SystemA_DailyPipeline created
) else (
    echo   FAILED: Could not create SystemA_DailyPipeline
)
echo.

REM --- Task 2: Post 07:00 ---
echo [2/4] Creating task: SystemA_Post_0700 (07:00)...
schtasks /Create /TN "SystemA_Post_0700" /TR "\"%PYTHON_CMD%\" \"%PROJECT_DIR%system_a\run_scheduled_posts.py\"" /SC DAILY /ST 07:00 /F
if %ERRORLEVEL% equ 0 (
    echo   OK: SystemA_Post_0700 created
) else (
    echo   FAILED: Could not create SystemA_Post_0700
)
echo.

REM --- Task 3: Post 12:00 ---
echo [3/4] Creating task: SystemA_Post_1200 (12:00)...
schtasks /Create /TN "SystemA_Post_1200" /TR "\"%PYTHON_CMD%\" \"%PROJECT_DIR%system_a\run_scheduled_posts.py\"" /SC DAILY /ST 12:00 /F
if %ERRORLEVEL% equ 0 (
    echo   OK: SystemA_Post_1200 created
) else (
    echo   FAILED: Could not create SystemA_Post_1200
)
echo.

REM --- Task 4: Post 19:00 ---
echo [4/4] Creating task: SystemA_Post_1900 (19:00)...
schtasks /Create /TN "SystemA_Post_1900" /TR "\"%PYTHON_CMD%\" \"%PROJECT_DIR%system_a\run_scheduled_posts.py\"" /SC DAILY /ST 19:00 /F
if %ERRORLEVEL% equ 0 (
    echo   OK: SystemA_Post_1900 created
) else (
    echo   FAILED: Could not create SystemA_Post_1900
)
echo.

echo ============================================
echo Setup Complete!
echo ============================================
echo.
echo To verify tasks, run:
echo   schtasks /Query /TN "SystemA_DailyPipeline"
echo   schtasks /Query /TN "SystemA_Post_0700"
echo   schtasks /Query /TN "SystemA_Post_1200"
echo   schtasks /Query /TN "SystemA_Post_1900"
echo.
echo To delete all tasks:
echo   schtasks /Delete /TN "SystemA_DailyPipeline" /F
echo   schtasks /Delete /TN "SystemA_Post_0700" /F
echo   schtasks /Delete /TN "SystemA_Post_1200" /F
echo   schtasks /Delete /TN "SystemA_Post_1900" /F
echo.
