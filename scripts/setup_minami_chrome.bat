@echo off
REM === みなみ Chrome プロファイル セットアップ ===
REM
REM 使い方:
REM   1. VPS に RDP 接続
REM   2. このバッチを実行 → Chrome が起動する
REM   3. みなみアカウントで X (Twitter) に手動ログイン
REM   4. ログイン後 Chrome を閉じる → 以降は自動化で利用可能
REM
REM プロファイル保存先: C:\money-machine\chrome-profiles\minami

setlocal

set PROJECT_DIR=%~dp0..
set PROFILE_DIR=%PROJECT_DIR%\chrome-profiles\minami
set CHROME_EXE=C:\Program Files\Google\Chrome\Application\chrome.exe

REM --- 1. Chrome の存在確認 ---
if not exist "%CHROME_EXE%" (
    echo [ERROR] Chrome が見つかりません: %CHROME_EXE%
    echo Google Chrome をインストールしてから再実行してください。
    pause
    exit /b 1
)

REM --- 2. プロファイルディレクトリ作成 ---
if not exist "%PROFILE_DIR%" (
    echo [INFO] プロファイルディレクトリを作成: %PROFILE_DIR%
    mkdir "%PROFILE_DIR%"
) else (
    echo [INFO] 既存プロファイルを使用: %PROFILE_DIR%
)

REM --- 3. Chrome を専用プロファイルで起動 ---
echo.
echo ============================================
echo   みなみ用 Chrome を起動します
echo   プロファイル: %PROFILE_DIR%
echo ============================================
echo.
echo  ★ X (https://x.com) が開きます
echo  ★ みなみアカウントでログインしてください
echo  ★ ログイン完了後、Chrome を閉じてください
echo  ★ 以降はこのプロファイルで自動ログイン済みになります
echo.

start "" "%CHROME_EXE%" ^
    --user-data-dir="%PROFILE_DIR%" ^
    --no-first-run ^
    --no-default-browser-check ^
    --disable-features=TranslateUI ^
    --lang=ja ^
    "https://x.com/login"

echo [INFO] Chrome を起動しました。ログイン後に閉じてください。
echo.
pause
