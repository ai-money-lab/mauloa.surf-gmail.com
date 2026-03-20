@echo off
chcp 65001 >nul 2>&1
REM ═══════════════════════════════════════════════════
REM Kling AI 動画生成テスト（ローカルPC用）
REM training_data から画像を自動選択して動画生成
REM ═══════════════════════════════════════════════════

echo.
echo ========================================
echo  Kling AI Video Generation Test
echo ========================================
echo.

cd /d "%~dp0.."

REM training_data フォルダの自動検出
set "TRAINING_DIR="

REM 候補パスを順番にチェック
if exist "C:\Users\maulo\XaiX\v7_current\training_data" (
    set "TRAINING_DIR=C:\Users\maulo\XaiX\v7_current\training_data"
)
if exist "%~dp0..\..\XaiX\v7_current\training_data" (
    set "TRAINING_DIR=%~dp0..\..\XaiX\v7_current\training_data"
)

if "%TRAINING_DIR%"=="" (
    echo ERROR: training_data フォルダが見つかりません
    echo 以下のパスを確認してください:
    echo   C:\Users\maulo\XaiX\v7_current\training_data
    pause
    exit /b 1
)

echo  Training data: %TRAINING_DIR%

REM 最初のJPG/PNG画像を自動選択
set "IMAGE_FILE="
for %%f in ("%TRAINING_DIR%\*.jpg" "%TRAINING_DIR%\*.png" "%TRAINING_DIR%\*.webp") do (
    if not defined IMAGE_FILE set "IMAGE_FILE=%%f"
)

if "%IMAGE_FILE%"=="" (
    echo ERROR: 画像ファイルが見つかりません
    pause
    exit /b 1
)

echo  Selected image: %IMAGE_FILE%
echo.

REM 出力ディレクトリ作成
if not exist "data\system_e\videos" mkdir "data\system_e\videos"

REM Python テスト実行
echo  Kling API で動画生成を開始します...
echo  （1〜3分かかります）
echo.

python -c "
import sys
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()

from system_e.video_pipeline import VideoPipeline

pipeline = VideoPipeline()
print(f'Video provider: {pipeline.video_provider}')
print(f'Kling enabled: {pipeline._kling.enabled}')

if not pipeline._kling.enabled:
    print('ERROR: Kling API keys not set. Run setup_local_env.bat first.')
    sys.exit(1)

image = r'%IMAGE_FILE%'
print(f'\nGenerating video from: {image}')

prompt = 'gentle wind blowing hair, soft natural movement, warm golden hour sunlight, slight smile, cinematic'
print(f'Prompt: {prompt}')
print(f'Mode: std, Duration: 5s, Aspect: 9:16')
print('Processing...\n')

result = pipeline._kling.generate(
    image_url=image,
    prompt=prompt,
    duration_s=5,
    aspect_ratio='9:16',
)

if result and result.get('video_url'):
    print(f'SUCCESS! Video URL: {result[\"video_url\"]}')

    import requests
    from pathlib import Path
    video_dir = Path('data/system_e/videos')
    video_dir.mkdir(parents=True, exist_ok=True)
    out_path = video_dir / 'kling_test_riena_001.mp4'

    print(f'Downloading to: {out_path}')
    resp = requests.get(result['video_url'], timeout=120)
    out_path.write_bytes(resp.content)
    print(f'SAVED: {out_path} ({len(resp.content) / 1024:.0f} KB)')
    print(f'\nOpen the video: start {out_path}')
else:
    print('FAILED: Video generation did not return a URL.')
    if result:
        print(f'Response: {result}')
    sys.exit(1)
"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo  動画生成テスト完了！
    echo ========================================
    echo  出力: data\system_e\videos\kling_test_riena_001.mp4
    echo.
    REM 動画を自動で開く
    if exist "data\system_e\videos\kling_test_riena_001.mp4" (
        start "" "data\system_e\videos\kling_test_riena_001.mp4"
    )
) else (
    echo.
    echo ERROR: 動画生成に失敗しました。
    echo ログを確認してください。
)

echo.
pause
