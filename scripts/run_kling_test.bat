@echo off
chcp 65001 >nul 2>&1
REM ═══════════════════════════════════════════════════
REM Riena Kling動画生成 — 完全自動スクリプト
REM 1. .env にKling APIキーを自動設定
REM 2. training_data から画像を自動検出
REM 3. Kling API で動画生成
REM 4. 動画を自動ダウンロード＆再生
REM ═══════════════════════════════════════════════════

echo.
echo ========================================
echo  Riena - Kling Video Auto Generator
echo ========================================
echo.

REM プロジェクトルートに移動
cd /d "%~dp0.."
echo [DIR] %CD%

REM ── 1. 依存パッケージ確認 ──
echo.
echo [1/5] 依存パッケージ確認...
pip install -q python-dotenv requests PyJWT pyyaml >nul 2>&1
echo       OK

REM ── 2. .env にKling APIキーを自動設定 ──
echo [2/5] .env 設定...

if not exist ".env" (
    echo # HIROKI AI Empire - Environment Variables > .env
)

REM Kling APIキーを自動書き込み（PowerShellで確実に置換）
powershell -Command ^
  "$content = Get-Content '.env' -Raw -ErrorAction SilentlyContinue; " ^
  "if (-not $content) { $content = '' }; " ^
  "if ($content -match 'KLING_ACCESS_KEY=') { " ^
  "  $content = $content -replace 'KLING_ACCESS_KEY=.*', 'KLING_ACCESS_KEY=AQK4BmBJne4f8GYY99tEK9GnDELTpDTJ'; " ^
  "  $content = $content -replace 'KLING_SECRET_KEY=.*', 'KLING_SECRET_KEY=EdKMGLLDHkfpta8tykL4AEy3rygahene'; " ^
  "} else { " ^
  "  $content += \"`nVIDEO_PROVIDER=kling`nKLING_ACCESS_KEY=AQK4BmBJne4f8GYY99tEK9GnDELTpDTJ`nKLING_SECRET_KEY=EdKMGLLDHkfpta8tykL4AEy3rygahene`n\"; " ^
  "}; " ^
  "if ($content -notmatch 'VIDEO_PROVIDER=') { $content += \"`nVIDEO_PROVIDER=kling`n\" }; " ^
  "Set-Content '.env' $content"

echo       Kling APIキー設定完了

REM ── 3. training_data から画像検出 ──
echo [3/5] 画像検出...

set "TRAINING_DIR="
set "IMAGE_FILE="

REM 候補パスをチェック
for %%d in (
    "C:\Users\maulo\XaiX\v7_current\training_data"
    "%USERPROFILE%\XaiX\v7_current\training_data"
    "%~dp0..\..\XaiX\v7_current\training_data"
) do (
    if exist %%d (
        set "TRAINING_DIR=%%~d"
    )
)

if "%TRAINING_DIR%"=="" (
    echo       training_data が見つかりません
    echo       data\system_e\images を確認中...
    for %%f in ("data\system_e\images\*.jpg" "data\system_e\images\*.png") do (
        if not defined IMAGE_FILE set "IMAGE_FILE=%%f"
    )
) else (
    echo       Found: %TRAINING_DIR%
    REM 最初の画像を選択
    for %%f in ("%TRAINING_DIR%\*.jpg" "%TRAINING_DIR%\*.png" "%TRAINING_DIR%\*.webp") do (
        if not defined IMAGE_FILE set "IMAGE_FILE=%%f"
    )
)

if "%IMAGE_FILE%"=="" (
    echo       ERROR: 画像が見つかりません
    echo       training_data フォルダに画像を配置してください
    pause
    exit /b 1
)

echo       Image: %IMAGE_FILE%

REM ── 4. ディレクトリ作成 ──
echo [4/5] 出力ディレクトリ準備...
if not exist "data\system_e\videos" mkdir "data\system_e\videos"
if not exist "data\system_e\images" mkdir "data\system_e\images"
echo       OK

REM ── 5. Kling API で動画生成 ──
echo [5/5] Kling 動画生成開始...
echo.
echo ----------------------------------------
echo  Image: %IMAGE_FILE%
echo  Duration: 5s / Aspect: 9:16
echo  Mode: std (free tier)
echo  所要時間: 1〜3分
echo ----------------------------------------
echo.

python "%~dp0kling_generate.py" "%IMAGE_FILE%"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo  動画生成完了！
    echo ========================================
    echo  出力: data\system_e\videos\
) else (
    echo.
    echo  動画生成に失敗しました。
    echo  エラーログを確認してください。
)

echo.
pause
