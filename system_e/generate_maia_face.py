"""Generate Maia's face — first look at the character.

Usage:
    # With FAL.ai (higher quality):
    FAL_API_KEY=your_key python system_e/generate_maia_face.py

    # With Gemini (free, 500/day):
    GEMINI_API_KEY=your_key python system_e/generate_maia_face.py --gemini

    # Dry run (show prompt only):
    python system_e/generate_maia_face.py --dry-run
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
import yaml
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
PROJECT_ROOT = Path(__file__).parent.parent
IMAGE_DIR = PROJECT_ROOT / "data" / "system_e" / "images"
CONFIG_PATH = Path(__file__).parent / "character_config.yaml"

# ─── Maiaの顔プロンプト（最重要：ここがアイデンティティを決める） ───

MAIA_FACE_PROMPT = """
Beautiful 26-year-old Japanese woman, stunning natural beauty, soft glowing skin.
Dark brown hair styled in a effortless messy bun, loose strands framing her delicate face.
Big expressive brown eyes, long eyelashes, subtle cat-eye shape.
Slim athletic body, toned but feminine. High cheekbones, small nose, full soft lips.
Wearing a fitted white crop top, showing toned midriff. Delicate silver watch on wrist.
Warm genuine smile, looking directly at camera with confident yet gentle gaze.
Golden morning sunlight through window, Tokyo apartment kitchen.
Matcha latte on marble counter. Soft bokeh background.
Shot on Sony A7IV, 85mm f/1.4 lens, shallow depth of field.
Magazine-quality editorial portrait, warm color grading, skin glow effect.
Photorealistic, ultra detailed, 8K quality.
""".strip()

MAIA_SCENE_PROMPTS = {
    "portrait_warm": MAIA_FACE_PROMPT,
    "selfie_cute": """
Adorable 26-year-old Japanese woman taking a mirror selfie in her bedroom.
Dark brown hair down, slightly wavy, past shoulders. Flawless dewy skin.
Big beautiful brown eyes, natural makeup with glossy lips.
Wearing an oversized off-shoulder knit sweater, showing collarbone.
Playful expression, slight head tilt, peace sign near face.
Warm soft lighting, fairy lights in background. Cozy aesthetic.
iPhone selfie style, natural and intimate. Ultra pretty, model-tier beauty.
""".strip(),
    "workout": """
Gorgeous 26-year-old Japanese fitness girl at a modern gym.
Dark brown hair in sleek high ponytail, baby hairs framing face.
Athletic toned body, visible abs, lean muscle definition.
Wearing black sports bra and high-waisted leggings, silver watch.
Mid-workout glow, light sweat on skin making it shine.
Confident powerful expression, looking at camera between sets.
Clean modern gym background, dramatic side lighting.
Fitness magazine editorial quality, Sony A7IV, 85mm lens.
Photorealistic, ultra detailed, beautiful lighting.
""".strip(),
    "evening_vulnerable": """
Stunningly beautiful 26-year-old Japanese woman in cozy evening setting.
Dark brown hair loose and flowing, soft waves. Luminous bare skin.
Wearing oversized cream cashmere sweater slipping off one shoulder, tiny shorts.
Sitting on plush rug, legs tucked under her, reading an old journal.
Soft dreamy expression, long eyelashes casting shadows on cheeks.
Orange tabby cat curled in her lap. Warm golden lamp light.
Intimate bedroom aesthetic, candles, fairy lights, soft textures.
Cinematic portrait, warm tones, shallow depth of field, editorial quality.
""".strip(),
    "matcha_ritual": """
Beautiful 26-year-old Japanese woman preparing matcha in minimalist kitchen.
Dark brown hair in loose low bun, wispy bangs. Glowing morning skin.
Wearing silk camisole in sage green, delicate silver watch.
Graceful hands whisking matcha in handmade ceramic bowl.
Serene focused expression, natural beauty, no makeup look.
Soft morning golden light streaming through sheer curtains.
Steam rising from matcha. Clean minimalist Japanese aesthetic.
Overhead angle, shallow depth of field on her hands and matcha foam.
Lifestyle editorial photography, warm film tones, magazine quality.
""".strip(),
}


def generate_with_fal(prompt: str, api_key: str, aspect_ratio: str = "3:4") -> str | None:
    """Generate image using FAL.ai Flux Pro v1.1 Ultra."""
    url = "https://queue.fal.run/fal-ai/flux-pro/v1.1-ultra"
    headers = {
        "Authorization": f"Key {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "output_format": "jpeg",
        "safety_tolerance": "2",
    }

    logger.info("Submitting to FAL.ai Flux Pro...")
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    result = resp.json()

    # Try direct result
    image_url = _extract_fal_image_url(result)

    # If queued, poll for result
    if not image_url:
        request_id = result.get("request_id")
        if request_id:
            logger.info("Queued. Polling for result (request_id=%s)...", request_id)
            image_url = _poll_fal(request_id, "fal-ai/flux-pro/v1.1-ultra", headers)

    if image_url:
        return _download_image(image_url, "maia_fal")

    logger.error("No image URL in FAL response")
    return None


def generate_with_gemini(prompt: str, api_key: str) -> str | None:
    """Generate image using Gemini API (free tier)."""
    # Try models in order: highest quality first
    # Pro > Flash, newer > older, Ultra > Standard
    models = [
        "gemini-3-pro-image-preview",       # Pro = 最高品質
        "gemini-3.1-flash-image-preview",    # 3.1 Flash = 最新
        "gemini-2.5-flash-image",            # 安定版
        "nano-banana-pro-preview",           # Nano Banana Pro
    ]
    payload = {
        "contents": [{"parts": [{"text": f"Generate this image: {prompt}"}]}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
    }

    resp = None
    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        logger.info("Trying model: %s", model)
        resp = requests.post(url, json=payload, timeout=60)
        if resp.status_code == 200:
            logger.info("Success with model: %s", model)
            break
        logger.warning("Model %s returned %d, trying next...", model, resp.status_code)

    if resp is None or resp.status_code != 200:
        logger.error("All models failed. Last status: %s", resp.status_code if resp else "none")
        if resp is not None:
            logger.error("Response: %s", resp.text[:500])
        return None

    logger.info("Submitting to Gemini API...")
    data = resp.json()

    candidates = data.get("candidates", [])
    if not candidates:
        logger.error("No candidates in Gemini response")
        return None

    parts = candidates[0].get("content", {}).get("parts", [])
    for part in parts:
        inline_data = part.get("inlineData")
        if inline_data and inline_data.get("mimeType", "").startswith("image/"):
            image_bytes = base64.b64decode(inline_data["data"])
            ext = inline_data["mimeType"].split("/")[-1]
            if ext == "jpeg":
                ext = "jpg"
            return _save_image(image_bytes, f"maia_gemini", ext)

    logger.warning("No image data in Gemini response")
    return None


def _extract_fal_image_url(result: dict) -> str | None:
    images = result.get("images", [])
    if images:
        return images[0].get("url")
    image = result.get("image")
    if isinstance(image, dict):
        return image.get("url")
    if isinstance(image, str):
        return image
    return None


def _poll_fal(request_id: str, model_path: str, headers: dict, max_wait: int = 120) -> str | None:
    status_url = f"https://queue.fal.run/{model_path}/requests/{request_id}/status"
    result_url = f"https://queue.fal.run/{model_path}/requests/{request_id}"

    start = time.time()
    while time.time() - start < max_wait:
        resp = requests.get(status_url, headers=headers, timeout=10)
        resp.raise_for_status()
        status = resp.json()

        if status.get("status") == "COMPLETED":
            resp = requests.get(result_url, headers=headers, timeout=10)
            resp.raise_for_status()
            return _extract_fal_image_url(resp.json())
        elif status.get("status") == "FAILED":
            logger.error("FAL request failed: %s", status.get("error"))
            return None

        time.sleep(2)

    logger.error("Polling timed out after %ds", max_wait)
    return None


def _download_image(url: str, prefix: str) -> str | None:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return _save_image(resp.content, prefix, "jpg")


def _save_image(data: bytes, prefix: str, ext: str) -> str:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(JST)
    filename = f"{prefix}_{now.strftime('%Y%m%d_%H%M%S')}.{ext}"
    filepath = IMAGE_DIR / filename
    filepath.write_bytes(data)
    logger.info("Saved: %s (%d bytes)", filepath, len(data))
    return str(filepath)


def main():
    parser = argparse.ArgumentParser(description="Generate Maia's face")
    parser.add_argument("--gemini", action="store_true", help="Use Gemini API instead of FAL.ai")
    parser.add_argument("--scene", choices=list(MAIA_SCENE_PROMPTS.keys()), default="portrait_warm",
                        help="Scene to generate")
    parser.add_argument("--all-scenes", action="store_true", help="Generate all scenes")
    parser.add_argument("--dry-run", action="store_true", help="Show prompt only, don't generate")
    args = parser.parse_args()

    scenes = list(MAIA_SCENE_PROMPTS.keys()) if args.all_scenes else [args.scene]

    for scene in scenes:
        prompt = MAIA_SCENE_PROMPTS[scene]
        print(f"\n{'='*60}")
        print(f"Scene: {scene}")
        print(f"{'='*60}")
        print(f"Prompt:\n{prompt}\n")

        if args.dry_run:
            print("[DRY RUN] Skipping generation.")
            continue

        if args.gemini:
            api_key = os.getenv("GEMINI_API_KEY", "")
            if not api_key:
                print("ERROR: GEMINI_API_KEY not set.")
                print("Get one free at: https://aistudio.google.com/apikey")
                sys.exit(1)
            result = generate_with_gemini(prompt, api_key)
        else:
            api_key = os.getenv("FAL_API_KEY", "")
            if not api_key:
                print("ERROR: FAL_API_KEY not set.")
                print("Get one at: https://fal.ai/dashboard/keys")
                print("\nTip: Try --gemini for free generation (500/day)")
                sys.exit(1)
            result = generate_with_fal(prompt, api_key)

        if result:
            print(f"\nMaia generated: {result}")
        else:
            print("\nGeneration failed. Check logs above.")

        # Rate limit between scenes
        if len(scenes) > 1 and scene != scenes[-1]:
            time.sleep(2)

    if args.dry_run:
        print(f"\n{'='*60}")
        print("To generate, set an API key:")
        print("  FAL.ai:  FAL_API_KEY=xxx python system_e/generate_maia_face.py")
        print("  Gemini:  GEMINI_API_KEY=xxx python system_e/generate_maia_face.py --gemini")
        print(f"{'='*60}")


if __name__ == "__main__":
    main()
