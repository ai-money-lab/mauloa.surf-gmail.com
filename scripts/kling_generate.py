"""Kling動画生成スクリプト — run_kling_test.bat から呼び出される"""
import sys
import time
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv(override=True, encoding="utf-8")

ak = os.getenv("KLING_ACCESS_KEY", "")
sk = os.getenv("KLING_SECRET_KEY", "")
print(f"Access Key: {ak[:8]}...{ak[-4:] if len(ak) > 4 else 'N/A'}")
print(f"Secret Key: {sk[:8]}...{sk[-4:] if len(sk) > 4 else 'N/A'}")

if not ak or not sk:
    print("ERROR: Kling APIキーが設定されていません")
    sys.exit(1)

from system_e.video_pipeline import VideoPipeline

pipeline = VideoPipeline()
print(f"Provider: {pipeline.video_provider}")
print(f"Kling enabled: {pipeline._kling.enabled}")

if not pipeline._kling.enabled:
    print("ERROR: Kling が無効です")
    sys.exit(1)

# 画像パスはコマンドライン引数から取得
if len(sys.argv) < 2:
    print("ERROR: 画像パスを引数で指定してください")
    sys.exit(1)

image = sys.argv[1]
prompt = (
    "gentle wind blowing hair, soft natural movement, "
    "warm golden hour sunlight, slight smile, looking at camera, "
    "cinematic shallow depth of field"
)

print(f"\nGenerating video...")
print(f"Image: {image}")
print(f"Prompt: {prompt}")
start = time.time()

result = pipeline._kling.generate(
    image_url=image,
    prompt=prompt,
    duration_s=5,
    aspect_ratio="9:16",
)

elapsed = time.time() - start
print(f"Elapsed: {elapsed:.0f}s")

if result and result.get("video_url"):
    print(f"\nSUCCESS!")
    print(f"Video URL: {result['video_url']}")

    import requests
    from pathlib import Path
    from datetime import datetime

    video_dir = Path("data/system_e/videos")
    video_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = video_dir / f"riena_kling_{ts}.mp4"

    print("Downloading...")
    resp = requests.get(result["video_url"], timeout=120)
    out_path.write_bytes(resp.content)
    size_kb = len(resp.content) / 1024
    print(f"SAVED: {out_path} ({size_kb:.0f} KB)")

    import subprocess

    subprocess.Popen(["start", "", str(out_path)], shell=True)
    print("\nVideo player opening...")
else:
    print("\nFAILED: 動画生成に失敗しました")
    if result:
        print(f"Response: {result}")
    sys.exit(1)
