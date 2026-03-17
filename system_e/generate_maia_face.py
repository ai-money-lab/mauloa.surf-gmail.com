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

# ═══════════════════════════════════════════════════════════
# キャラクター定義: Maia
#
# Aitana Lopez ($10K+/月) の制作者が使うテクニック:
# 1. 超具体的な顔の特徴（毎回同じ人物に見える）
# 2. 不完全さ（完璧はAIっぽい。そばかす、肌質感、乱れ髪）
# 3. フィルム感（Kodak Portra, Fuji Pro 400H = リアリティ）
# 4. 実在する場所の空気感
#
# Source: https://www.theinfluencer.ai/blog/how-to-create-an-ai-influencer-like-aitana-lopez
# Source: https://metricsmule.com/ai/create-ai-influencers/
# ═══════════════════════════════════════════════════════════

# キャラクター固定パーツ（全プロンプトで共有 = 一貫性の鍵）
# 重要: AI画像生成で「26歳」は老ける。「20歳」「baby face」で若く出す。
# ネガティブワードで老け防止。これがAI美女界隈の常識。
MAIA_IDENTITY = """extremely beautiful young Japanese girl, 20 years old, baby face, youthful glowing dewy skin.
Face: small oval face, soft round cheeks, cute button nose with slight upturn, plump glossy lips with natural pink tint, adorable dimples when smiling, clear double eyelids.
Eyes: big round sparkling dark brown eyes, long thick natural eyelashes, innocent yet captivating gaze, puppy-dog eyes.
Eyebrows: soft natural straight eyebrows, well-groomed.
Skin: flawless porcelain-like smooth skin with natural healthy glow, youthful radiance, dewy finish, no wrinkles, no blemishes, baby-soft skin texture. Tiny beauty mark below left eye.
Hair: glossy dark brown hair, silky texture, soft highlights, healthy and shiny, medium-long past shoulders.
Body: slim petite toned figure, delicate collarbones, long slender neck, 163cm. Toned but soft feminine curves.
Signature: delicate thin vintage silver watch on left wrist.
""".strip()

# おばさん化を防ぐネガティブプロンプト
NEGATIVE_PROMPT = "old, aged, wrinkles, mature face, sagging skin, dark circles, tired eyes, rough skin, large pores, masculine features, thick neck, broad shoulders, cartoon, anime, illustration, 3D render, lowres, blurry, deformed, ugly, bad anatomy"

MAIA_FACE_PROMPT = f"""Stunning portrait photograph of {MAIA_IDENTITY}
Glossy dark brown hair in a loose messy bun with soft wispy face-framing pieces and curtain bangs.
Wearing a white off-shoulder knit top, showing delicate collarbones.
Expression: adorable sweet smile showing slight dimples, sparkling eyes looking at camera with warmth and charm. Head slightly tilted. She looks like she's about to laugh.
Setting: bright modern Tokyo apartment, soft golden morning light through large window. Matcha latte on white counter, green plants. Clean and aesthetic.
Shot on Sony A7IV, 85mm f/1.4, wide open. Soft dreamy bokeh. Warm golden tones, skin looks luminous and dewy. Soft sunlight creating a halo effect on hair.
Ultra photorealistic, magazine beauty editorial, skin retouching, 8K detail. The kind of face that stops your scroll on Instagram.
Avoid: {NEGATIVE_PROMPT}
""".strip()

MAIA_SCENE_PROMPTS = {
    "portrait_warm": MAIA_FACE_PROMPT,

    "selfie_cute": f"""Adorable selfie of {MAIA_IDENTITY}
Glossy dark brown hair down with soft natural waves, wispy curtain bangs framing face perfectly.
Wearing oversized cream knit sweater, off-shoulder showing smooth skin and delicate collarbone.
Taking selfie from slightly above, one hand playing with hair strand, big innocent eyes looking up at camera.
Expression: cute pouty lips, sweet playful smile, head tilted, irresistible charm.
Background: cozy sunlit bedroom, white sheets, fairy lights, warm dreamy atmosphere.
iPhone selfie aesthetic, portrait mode bokeh, warm golden light, dewy glowing skin.
Ultra photorealistic, beautiful young girl, Instagram viral quality. Baby face, youthful.
Avoid: {NEGATIVE_PROMPT}
""".strip(),

    "workout_power": f"""Fitness photo of {MAIA_IDENTITY}
Glossy dark brown hair in high ponytail with cute face-framing baby hairs.
Slim toned body, flat stomach, lean arms. Skin has pretty workout glow.
Wearing black sports bra and high-waisted leggings, delicate silver watch.
Standing between sets, one hand on hip, confident cute smirk at camera. Youthful energy.
Setting: clean modern gym, golden light through windows.
Shot on Sony A7IV, 85mm f/1.4. Beautiful lighting on skin. Fitness magazine quality.
Ultra photorealistic, young athletic girl, healthy and beautiful.
Avoid: {NEGATIVE_PROMPT}
""".strip(),

    "evening_intimate": f"""Cozy evening photo of {MAIA_IDENTITY}
Glossy dark brown hair down, soft waves, slightly messy in a cute way.
Wearing oversized cream cashmere cardigan over thin white camisole, bare legs.
Sitting on soft rug, hugging knees, reading an old journal. Sweet tender expression, long lashes.
Orange tabby cat curled up beside her. Warm golden lamp light, candles.
Cozy intimate bedroom, books, tea cup, fairy lights.
Shot on 50mm f/1.4, warm available light. Soft dreamy tones, dewy skin glow.
Ultra photorealistic, adorable young girl in private moment.
Avoid: {NEGATIVE_PROMPT}
""".strip(),

    "matcha_aesthetic": f"""Aesthetic morning photo of {MAIA_IDENTITY}
Glossy dark brown hair in cute messy low bun with wispy bangs.
Wearing sage green silk camisole, delicate silver watch visible.
Preparing matcha in ceramic bowl, graceful hands, serene sweet expression.
Bright morning golden light, white minimalist kitchen, steam rising.
Overhead angle, shallow depth of field, clean Japanese aesthetic.
Shot on 35mm f/1.4, magazine lifestyle editorial quality.
Ultra photorealistic, beautiful young girl, peaceful and radiant.
Avoid: {NEGATIVE_PROMPT}
""".strip(),

    "tokyo_golden": f"""Street fashion photo of {MAIA_IDENTITY}
Glossy dark brown hair flowing in light breeze, golden backlight creating halo rim-light.
Wearing fitted camel coat, white tee, high-waisted jeans, white sneakers. Silver watch, canvas tote.
Walking through pretty Tokyo backstreet at golden hour, glancing back over shoulder with bright charming smile.
Soft bokeh background, warm buildings, trees, dappled sunlight.
Shot on 85mm f/1.2, Kodak Portra 400 film tones, warm nostalgic palette.
Ultra photorealistic, adorable young Japanese girl, the photo that stops your scroll.
Avoid: {NEGATIVE_PROMPT}
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
