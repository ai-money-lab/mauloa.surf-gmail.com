@echo off
chcp 65001 >nul 2>&1
REM ═══════════════════════════════════════════════════
REM HIROKI AI Empire — ローカル環境自動セットアップ
REM .envファイル作成 & Kling動画テスト実行
REM ═══════════════════════════════════════════════════

echo.
echo ========================================
echo  HIROKI AI Empire - Local Setup
echo ========================================
echo.

REM プロジェクトルートに移動
cd /d "%~dp0.."

REM 1. 依存パッケージのインストール
echo [1/4] 依存パッケージをインストール中...
pip install -q python-dotenv requests PyJWT >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: pip install に失敗。手動で実行してください:
    echo   pip install python-dotenv requests PyJWT
)
echo       完了

REM 2. .envファイルの作成/更新
echo [2/4] .env ファイルを確認中...

if not exist ".env" (
    echo       .env が見つかりません。新規作成します。
    copy config\.env.example .env >nul 2>&1
    if not exist ".env" (
        echo # HIROKI AI Empire - Environment Variables > .env
    )
)

REM Kling APIキーが設定されているか確認
findstr /C:"KLING_ACCESS_KEY=" .env >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.>> .env
    echo # ═══ Kling AI API（System E: 動画生成）═══>> .env
    echo VIDEO_PROVIDER=kling>> .env
    echo KLING_ACCESS_KEY=>> .env
    echo KLING_SECRET_KEY=>> .env
    echo       Kling APIキーのプレースホルダーを追加しました。
    echo       .env を編集してキーを入力してください。
    goto :ask_keys
) else (
    REM キーに値が入っているか確認
    for /f "tokens=2 delims==" %%a in ('findstr /C:"KLING_ACCESS_KEY=" .env') do (
        if "%%a"=="" goto :ask_keys
    )
    echo       Kling APIキー設定済み
    goto :check_video_provider
)

:ask_keys
echo.
echo ----------------------------------------
echo  Kling AI API キーの設定
echo  https://platform.klingai.com で取得
echo ----------------------------------------
set /p "KLING_AK=KLING_ACCESS_KEY を入力: "
set /p "KLING_SK=KLING_SECRET_KEY を入力: "

if not "%KLING_AK%"=="" if not "%KLING_SK%"=="" (
    REM 既存のキー行を置換するためにtempファイル使用
    powershell -Command "(Get-Content .env) -replace '^KLING_ACCESS_KEY=.*', 'KLING_ACCESS_KEY=%KLING_AK%' -replace '^KLING_SECRET_KEY=.*', 'KLING_SECRET_KEY=%KLING_SK%' | Set-Content .env"
    echo       APIキーを .env に保存しました。
) else (
    echo       スキップしました。後で .env を手動編集してください。
)

:check_video_provider
REM VIDEO_PROVIDERが設定されているか確認
findstr /C:"VIDEO_PROVIDER=" .env >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo VIDEO_PROVIDER=kling>> .env
)

REM 3. 必要ディレクトリの作成
echo [3/4] ディレクトリ構造を作成中...
if not exist "data\system_e\images" mkdir "data\system_e\images"
if not exist "data\system_e\videos" mkdir "data\system_e\videos"
if not exist "data\system_e\generated" mkdir "data\system_e\generated"
echo       完了

REM 4. Kling接続テスト
echo [4/4] Kling API 接続テスト中...
python -c "from dotenv import load_dotenv; load_dotenv(); import os; ak=os.getenv('KLING_ACCESS_KEY',''); sk=os.getenv('KLING_SECRET_KEY',''); print(f'  ACCESS_KEY: {\"設定済み\" if ak else \"未設定\"}'); print(f'  SECRET_KEY: {\"設定済み\" if sk else \"未設定\"}'); exit(0 if ak and sk else 1)"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Kling APIキーが未設定です。
    echo .env ファイルを編集して KLING_ACCESS_KEY と KLING_SECRET_KEY を設定してください。
    goto :done
)

REM VideoPipeline テスト
python -c "from dotenv import load_dotenv; load_dotenv(); from system_e.video_pipeline import VideoPipeline; p=VideoPipeline(); print(f'  Provider: {p.video_provider}'); print(f'  Kling enabled: {p._kling.enabled}'); exit(0 if p._kling.enabled else 1)"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo  セットアップ完了！
    echo ========================================
    echo.
    echo 動画生成テストを実行するには:
    echo   python scripts\test_kling_video.py data\system_e\images\riena_001.jpg
    echo.
    echo 画像がない場合は先に生成:
    echo   python -c "from dotenv import load_dotenv; load_dotenv(); from system_e.image_pipeline import ImagePipeline; p=ImagePipeline(); p.generate('wellness portrait of Riena', 'data/system_e/images/riena_001.jpg')"
) else (
    echo.
    echo ERROR: VideoPipeline の初期化に失敗しました。
    echo ログを確認してください。
)

:done
echo.
pause
