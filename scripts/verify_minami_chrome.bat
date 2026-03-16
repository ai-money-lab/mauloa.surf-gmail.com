@echo off
REM === みなみ Chrome プロファイル検証スクリプト ===
REM
REM 概要:
REM   Chrome のインストール状態、プロファイルディレクトリ、
REM   Cookie ファイル（ログイン済みかどうか）を確認して結果を表示する。
REM
REM 終了コード:
REM   0 = すべて正常
REM   1 = 問題あり

setlocal

REM --- パス設定 ---
set PROJECT_DIR=%~dp0..
set PROFILE_DIR=%PROJECT_DIR%\chrome-profiles\minami
set CHROME_EXE=C:\Program Files\Google\Chrome\Application\chrome.exe

REM --- 問題カウンタ初期化 ---
set ISSUES=0

echo.
echo ============================================
echo   みなみ Chrome プロファイル検証
echo ============================================
echo.

REM --- 1. Chrome インストール確認 ---
if exist "%CHROME_EXE%" (
    echo   [OK] Chrome インストール済み
) else (
    echo   [NG] Chrome が見つかりません: %CHROME_EXE%
    echo        Google Chrome をインストールしてください。
    set /a ISSUES+=1
)

REM --- 2. プロファイルディレクトリ確認 ---
if exist "%PROFILE_DIR%\" (
    echo   [OK] プロファイルディレクトリ存在
) else (
    echo   [NG] プロファイルディレクトリなし: %PROFILE_DIR%
    echo        setup_minami_chrome.bat を実行してプロファイルを作成してください。
    set /a ISSUES+=1
)

REM --- 3. Cookie ファイル確認（ログイン状態の判定） ---
REM Chrome は Default\Network\Cookies または Default\Cookies に Cookie を保存する
set COOKIE_FOUND=0

if exist "%PROFILE_DIR%\Default\Network\Cookies" (
    set COOKIE_FOUND=1
)
if exist "%PROFILE_DIR%\Default\Cookies" (
    set COOKIE_FOUND=1
)

if %COOKIE_FOUND%==1 (
    echo   [OK] Cookie ファイル存在（ログイン済み）
) else (
    echo   [NG] Cookie ファイルなし（setup_minami_chrome.bat を実行してログインしてください）
    set /a ISSUES+=1
)

REM --- 結果まとめ ---
echo.
echo ============================================
if %ISSUES%==0 (
    echo   検証結果: すべて正常です
    echo ============================================
    echo.
    endlocal
    exit /b 0
) else (
    echo   検証結果: %ISSUES% 件の問題があります
    echo ============================================
    echo.
    endlocal
    exit /b 1
)
