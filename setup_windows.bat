@echo off
REM ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REM CITS Windows 自動セットアップ
REM ダブルクリックで実行するだけでOK
REM ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

echo ========================================
echo CITS Windows セットアップ
echo ========================================

REM リポジトリに移動
cd /d %~dp0

REM Python仮想環境を作成（なければ）
if not exist "venv" (
    echo [1/5] Python仮想環境を作成中...
    python -m venv venv
) else (
    echo [1/5] Python仮想環境: 既存
)

REM 仮想環境を有効化
call venv\Scripts\activate.bat

REM 依存パッケージインストール
echo [2/5] 依存パッケージをインストール中...
pip install -r requirements.txt -q

REM PYTHONPATH設定
set PYTHONPATH=%cd%

REM .envファイル作成（なければ）
if not exist "cits\.env" (
    echo [3/5] .envファイルを作成中...
    copy cits\.env.example cits\.env
    echo .envファイルを編集してAPIキーを設定してください:
    echo   cits\.env
) else (
    echo [3/5] .envファイル: 既存
)

REM .envファイル読み込み
echo [4/5] 環境変数を読み込み中...
for /f "tokens=1,2 delims==" %%a in (cits\.env) do (
    REM コメント行をスキップ
    echo %%a | findstr /r "^#" >nul || (
        if not "%%b"=="" (
            set %%a=%%b
        )
    )
)

REM スモークテスト
echo [5/5] スモークテスト実行中...
python cits\tests\smoke_test.py
if %errorlevel% neq 0 (
    echo ⚠ スモークテスト失敗
    pause
    exit /b 1
)

echo.
echo ========================================
echo セットアップ完了！
echo ========================================
echo.
echo 利用可能なコマンド（API不要）:
echo   python -m cits.scripts.solve_equation --capital 100000
echo   python -m cits.scripts.paper_sim --days 20 --capital 100000 --verbose
echo   python -m cits.scripts.optimize --capital 100000 --period 1y --top 10
echo.
echo 利用可能なコマンド（API必要）:
echo   python -m cits.main --mode paper --ticker 2644
echo   python -m cits.scripts.run_paper_all
echo.
pause
