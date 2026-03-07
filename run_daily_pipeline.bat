@echo off
REM ============================================
REM HIROKI AI Empire - System A Daily Pipeline
REM Runs at 06:00 JST daily
REM ============================================

cd /d "C:\Users\maulo\OneDrive\副業\hiroki-ai-empire"

REM Set environment
set DOTENV_OVERRIDE=1

REM Run pipeline with logging
"C:\Users\maulo\AppData\Local\Programs\Python\Python312\python.exe" -c "from dotenv import load_dotenv; load_dotenv(override=True); from system_a.daily_pipeline import main; main()" >> "C:\Users\maulo\OneDrive\副業\hiroki-ai-empire\data\pipeline.log" 2>&1

echo %date% %time% - Pipeline completed >> "C:\Users\maulo\OneDrive\副業\hiroki-ai-empire\data\pipeline.log"
