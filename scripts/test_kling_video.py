#!/usr/bin/env python3
"""Test Kling AI image-to-video generation.

Usage:
    python scripts/test_kling_video.py <image_path_or_url>
    python scripts/test_kling_video.py data/system_e/images/riena_001.jpg

The generated video will be saved under data/system_e/videos/.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from system_e.video_pipeline import VideoPipeline  # noqa: E402


def main():
    image = sys.argv[1] if len(sys.argv) > 1 else None
    if not image:
        print("Usage: python scripts/test_kling_video.py <image_path_or_url>")
        sys.exit(1)

    pipeline = VideoPipeline()
    print(f"Video provider: {pipeline.video_provider}")
    print(f"Kling enabled: {pipeline._kling.enabled}")

    if not pipeline._kling.enabled:
        print("ERROR: Kling API keys not set. Check .env")
        sys.exit(1)

    print(f"\nGenerating video from: {image}")
    print("Prompt: gentle wind blowing hair, soft natural movement, warm sunlight")
    print("Mode: std (free tier), Duration: 5s, Aspect: 9:16")
    print("This may take 1-3 minutes...\n")

    result = pipeline._kling.generate(
        image_url=image,
        prompt="gentle wind blowing hair, soft natural movement, warm sunlight, slight smile",
        duration_s=5,
        aspect_ratio="9:16",
    )

    if result and result.get("video_url"):
        print(f"Video generated: {result['video_url']}")

        # Download
        import requests

        video_dir = Path("data/system_e/videos")
        video_dir.mkdir(parents=True, exist_ok=True)
        out_path = video_dir / "kling_test_001.mp4"

        resp = requests.get(result["video_url"], timeout=120)
        out_path.write_bytes(resp.content)
        print(f"Saved to: {out_path}")
    else:
        print("Generation failed. Check logs.")
        sys.exit(1)


if __name__ == "__main__":
    main()
