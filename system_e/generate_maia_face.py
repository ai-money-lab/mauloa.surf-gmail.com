"""Generate Maia — production-quality AI character images.

Imagen 4.0 Ultra (Google最高品質) をデフォルトで使用。
Gemini generateContent は補助。本気で世界を取るならImagen。

Usage:
    # Imagen 4.0 Ultra (最高品質・デフォルト):
    GEMINI_API_KEY=your_key python3 system_e/generate_maia_face.py

    # Gemini (fallback):
    GEMINI_API_KEY=your_key python3 system_e/generate_maia_face.py --gemini

    # FAL.ai Flux Pro (要FAL_API_KEY):
    FAL_API_KEY=your_key python3 system_e/generate_maia_face.py --fal

    # 全シーン一括:
    GEMINI_API_KEY=your_key python3 system_e/generate_maia_face.py --all-scenes

    # 1シーンN枚生成（ベストを選ぶ）:
    GEMINI_API_KEY=your_key python3 system_e/generate_maia_face.py --count 4
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import sys
import time
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
PROJECT_ROOT = Path(__file__).parent.parent
IMAGE_DIR = PROJECT_ROOT / "data" / "system_e" / "images"

# ═══════════════════════════════════════════════════════════
# プロンプト設計
#
# 凛(@i_am_rin_jp)は46Kフォロワー。あの品質が最低ライン。
# それ以上を出す。妥協しない。
# ═══════════════════════════════════════════════════════════

MAIA_FACE_PROMPT = """
A stunning portrait photograph of a 26-year-old Japanese woman.
She has silky dark brown hair in a loose messy bun with soft face-framing layers.
Large expressive almond-shaped brown eyes with naturally long lashes.
Flawless luminous skin with a natural healthy glow, high cheekbones, small straight nose, soft full lips with a natural pink tint.
Slim toned athletic figure, elegant neck and collarbones visible.
She wears a simple fitted white top and a delicate vintage silver watch on her left wrist.
Her expression is a warm, confident half-smile — the kind that makes you feel like she's sharing a secret with you.

Setting: Bright modern Tokyo apartment, golden morning sunlight streaming through large windows.
A beautifully prepared matcha latte on the counter beside her.
Soft creamy bokeh background with hints of green plants.

Technical: Shot on Canon R5, RF 85mm f/1.2L USM lens at f/1.4, natural window light with subtle fill.
Professional fashion editorial photography, skin retouching, warm color grade.
Ultra high resolution, photorealistic, magazine cover quality.
""".strip()

MAIA_SCENE_PROMPTS = {
    "portrait_warm": MAIA_FACE_PROMPT,

    "selfie_cute": """
A beautiful 26-year-old Japanese woman taking a casual selfie, slightly above eye level angle.
Silky dark brown hair down past shoulders with soft waves, wispy curtain bangs.
Large sparkling brown eyes, dewy glowing skin, natural makeup with glossy lips and subtle blush.
Wearing a cream off-shoulder oversized knit, delicate gold necklace, showing elegant collarbones.
Sweet genuine smile showing just a hint of teeth, slight playful head tilt.
Background: cozy bedroom with warm fairy lights, soft neutral tones, potted plants.
Natural warm lighting from golden hour window light.
iPhone 15 Pro selfie aesthetic but magazine quality skin and detail.
Photorealistic, ultra detailed, stunning natural beauty.
""".strip(),

    "workout_power": """
A gorgeous 26-year-old Japanese woman in a high-end modern gym.
Dark brown hair in a sleek high ponytail with face-framing baby hairs.
Athletic toned physique — defined shoulders, visible lean abs, strong legs.
Wearing a black designer sports bra and matching high-waisted leggings, silver watch on wrist.
She's standing between sets, one hand on hip, looking at camera with fierce confident energy.
Skin has a beautiful natural workout glow, light perspiration catching the light.
Background: clean premium gym with warm industrial lighting, mirrors reflecting depth.
Shot on Sony A1, 70-200mm f/2.8 at 85mm, dramatic Rembrandt lighting from above-left.
Fitness editorial for Vogue or Women's Health. Ultra sharp, cinematic color grade.
""".strip(),

    "evening_intimate": """
A strikingly beautiful 26-year-old Japanese woman in a warm evening setting.
Dark brown hair loose and flowing with natural soft waves, catching warm lamplight.
Luminous bare skin, naturally flushed cheeks, sleepy soft eyes with long lashes.
Wearing an oversized cream cashmere sweater that slips off one shoulder, revealing smooth skin.
She's sitting on a soft white rug, knees drawn up, holding an old leather journal.
An orange tabby cat is nestled against her side.
Warm golden light from designer table lamp, candles flickering in background.
Atmosphere: intimate, private, like a photo her closest friend took without her noticing.
Shot on Leica SL2-S, Summilux 50mm f/1.4, available light only.
Cinematic film look, warm analog tones, slight grain. Editorial intimacy.
""".strip(),

    "matcha_aesthetic": """
Overhead flat-lay style photograph of a beautiful Japanese woman's hands preparing matcha.
Graceful slender fingers with clean short nails, delicate silver watch visible.
She's whisking vibrant green matcha in a handmade ceramic chawan bowl.
The surface shows: bamboo chasen, a small plate with wagashi sweets, a linen napkin, her phone showing data.
Her face is partially visible at the top of frame — glowing skin, soft smile, dark brown hair in low bun.
Morning golden light creating long shadows across the white marble counter.
Minimalist Japanese aesthetic meets Scandinavian design.
Shot from directly above, Canon R5, RF 35mm f/1.4, perfectly styled editorial.
Clean, serene, aspirational lifestyle content. Magazine quality.
""".strip(),

    "tokyo_street": """
A fashionable 26-year-old Japanese woman walking through a Tokyo street at golden hour.
Dark brown hair flowing in a light breeze, catching sunlight with golden highlights.
She wears a tailored beige trench coat over a white tee, high-waisted vintage jeans, white sneakers.
Silver watch and minimal jewelry. Carrying a canvas tote bag.
She's glancing back over her shoulder at the camera with a magnetic confident smile.
Background: blurred Tokyo streetscape — warm-toned buildings, cherry blossom trees, soft city lights.
Shot on Canon R5, RF 85mm f/1.2 at f/1.4, beautiful natural backlight creating a rim light effect.
Fashion street photography, editorial quality, warm cinematic color grade.
The kind of photo that stops your scroll.
""".strip(),
}


# ═══════════════════════════════════════════════════════════
# Imagen 4.0 Ultra — Google最高品質の専用画像生成モデル
# ═══════════════════════════════════════════════════════════

def generate_with_imagen(prompt: str, api_key: str, aspect_ratio: str = "3:4", count: int = 1) -> list[str]:
    """Generate images using Imagen 4.0 Ultra (highest quality)."""
    # Try models: Ultra > Standard > Fast
    models = [
        "imagen-4.0-ultra-generate-001",
        "imagen-4.0-generate-001",
        "imagen-4.0-fast-generate-001",
    ]

    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:predict?key={api_key}"
        payload = {
            "instances": [{"prompt": prompt}],
            "parameters": {
                "sampleCount": min(count, 4),
                "aspectRatio": aspect_ratio,
                "personGeneration": "allow_all",
            },
        }

        logger.info("Trying Imagen model: %s (count=%d)", model, count)
        try:
            resp = requests.post(url, json=payload, timeout=120)
            if resp.status_code == 200:
                logger.info("Success with Imagen model: %s", model)
                return _parse_imagen_response(resp.json(), model)
            logger.warning("Imagen %s returned %d, trying next...", model, resp.status_code)
        except requests.exceptions.Timeout:
            logger.warning("Imagen %s timed out, trying next...", model)
            continue

    # Fallback: try generateContent API with image models
    logger.info("Imagen predict API failed. Trying generateContent API...")
    return _generate_with_gemini_image(prompt, api_key, count)


def _parse_imagen_response(data: dict, model: str) -> list[str]:
    """Parse Imagen API response and save images."""
    saved = []
    predictions = data.get("predictions", [])
    for i, pred in enumerate(predictions):
        image_b64 = pred.get("bytesBase64Encoded", "")
        if not image_b64:
            continue
        mime = pred.get("mimeType", "image/png")
        ext = "png" if "png" in mime else "jpg"
        path = _save_image(base64.b64decode(image_b64), f"maia_{model}", ext)
        saved.append(path)
        logger.info("Imagen image %d/%d saved: %s", i + 1, len(predictions), path)
    return saved


def _generate_with_gemini_image(prompt: str, api_key: str, count: int = 1) -> list[str]:
    """Fallback: generate via Gemini generateContent with image modality."""
    models = [
        "gemini-3-pro-image-preview",
        "gemini-3.1-flash-image-preview",
        "gemini-2.5-flash-image",
    ]
    payload = {
        "contents": [{"parts": [{"text": f"Generate this photograph: {prompt}"}]}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
    }

    saved = []
    for attempt in range(count):
        for model in models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            if attempt == 0:
                logger.info("Trying Gemini image model: %s", model)
            try:
                resp = requests.post(url, json=payload, timeout=90)
                if resp.status_code != 200:
                    continue

                data = resp.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    continue

                parts = candidates[0].get("content", {}).get("parts", [])
                for part in parts:
                    inline_data = part.get("inlineData")
                    if inline_data and inline_data.get("mimeType", "").startswith("image/"):
                        image_bytes = base64.b64decode(inline_data["data"])
                        ext = inline_data["mimeType"].split("/")[-1]
                        if ext == "jpeg":
                            ext = "jpg"
                        path = _save_image(image_bytes, f"maia_{model}", ext)
                        saved.append(path)
                        logger.info("Gemini image %d/%d saved: %s", attempt + 1, count, path)
                        break
                break  # success with this model, don't try others
            except Exception as e:
                logger.warning("Gemini %s error: %s", model, e)
                continue

        if count > 1 and attempt < count - 1:
            time.sleep(1)

    return saved


# ═══════════════════════════════════════════════════════════
# FAL.ai Flux Pro — 業界標準の画像生成
# ═══════════════════════════════════════════════════════════

def generate_with_fal(prompt: str, api_key: str, aspect_ratio: str = "3:4", count: int = 1) -> list[str]:
    """Generate images using FAL.ai Flux Pro v1.1 Ultra."""
    url = "https://queue.fal.run/fal-ai/flux-pro/v1.1-ultra"
    headers = {
        "Authorization": f"Key {api_key}",
        "Content-Type": "application/json",
    }

    saved = []
    for i in range(count):
        payload = {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "output_format": "jpeg",
            "safety_tolerance": "2",
            "seed": random.randint(0, 2**32) if count > 1 else None,
        }
        if payload["seed"] is None:
            del payload["seed"]

        logger.info("FAL.ai generation %d/%d...", i + 1, count)
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            result = resp.json()

            image_url = _extract_fal_image_url(result)
            if not image_url:
                request_id = result.get("request_id")
                if request_id:
                    image_url = _poll_fal(request_id, "fal-ai/flux-pro/v1.1-ultra", headers)

            if image_url:
                path = _download_image(image_url, "maia_flux_pro")
                saved.append(path)
        except Exception as e:
            logger.error("FAL.ai error: %s", e)

        if count > 1 and i < count - 1:
            time.sleep(1)

    return saved


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


# ═══════════════════════════════════════════════════════════
# ユーティリティ
# ═══════════════════════════════════════════════════════════

def _download_image(url: str, prefix: str) -> str:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return _save_image(resp.content, prefix, "jpg")


def _save_image(data: bytes, prefix: str, ext: str) -> str:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(JST)
    filename = f"{prefix}_{now.strftime('%Y%m%d_%H%M%S')}_{random.randint(1000,9999)}.{ext}"
    filepath = IMAGE_DIR / filename
    filepath.write_bytes(data)
    logger.info("Saved: %s (%d bytes / %.1f KB)", filepath, len(data), len(data) / 1024)
    return str(filepath)


# ═══════════════════════════════════════════════════════════
# メイン
# ═══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Generate Maia — production quality")
    parser.add_argument("--gemini", action="store_true", help="Force Gemini generateContent (lower quality)")
    parser.add_argument("--fal", action="store_true", help="Use FAL.ai Flux Pro (requires FAL_API_KEY)")
    parser.add_argument("--scene", choices=list(MAIA_SCENE_PROMPTS.keys()), default="portrait_warm")
    parser.add_argument("--all-scenes", action="store_true", help="Generate all scenes")
    parser.add_argument("--count", type=int, default=1, help="Number of images per scene (pick the best)")
    parser.add_argument("--dry-run", action="store_true", help="Show prompts only")
    args = parser.parse_args()

    scenes = list(MAIA_SCENE_PROMPTS.keys()) if args.all_scenes else [args.scene]

    total_generated = 0
    for scene in scenes:
        prompt = MAIA_SCENE_PROMPTS[scene]
        print(f"\n{'='*60}")
        print(f"Scene: {scene}")
        print(f"{'='*60}")

        if args.dry_run:
            print(f"Prompt:\n{prompt}\n")
            print("[DRY RUN] Skipping generation.")
            continue

        api_key = os.getenv("GEMINI_API_KEY", "")
        fal_key = os.getenv("FAL_API_KEY", "")

        if args.fal:
            if not fal_key:
                print("ERROR: FAL_API_KEY not set. Get one at: https://fal.ai/dashboard/keys")
                sys.exit(1)
            results = generate_with_fal(prompt, fal_key, count=args.count)
        elif args.gemini:
            if not api_key:
                print("ERROR: GEMINI_API_KEY not set.")
                sys.exit(1)
            results = _generate_with_gemini_image(prompt, api_key, count=args.count)
        else:
            # Default: Imagen 4.0 Ultra (最高品質)
            if not api_key:
                print("ERROR: GEMINI_API_KEY not set. Get one at: https://aistudio.google.com/apikey")
                sys.exit(1)
            results = generate_with_imagen(prompt, api_key, count=args.count)

        if results:
            total_generated += len(results)
            for r in results:
                print(f"  Generated: {r}")
        else:
            print("  Generation failed.")

        if len(scenes) > 1 and scene != scenes[-1]:
            time.sleep(2)

    if not args.dry_run:
        print(f"\n{'='*60}")
        print(f"Total: {total_generated} images generated")
        print(f"Folder: {IMAGE_DIR}")
        print(f"Open:   open {IMAGE_DIR}")
        print(f"{'='*60}")


if __name__ == "__main__":
    main()
