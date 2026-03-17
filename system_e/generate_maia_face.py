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

# ═══════════════════════════════════════════════════════════
# Maiaのシグネチャー: 「かわいいのに強い」
#
# AI美女界のポジションマップ:
#   凛、Aitana → かわいい/セクシー × ファッション（飽和）
#   imma       → かわいい × ハイファッション（飽和）
#   Maia       → かわいい × アスリート体型（空席！！）
#
# ベビーフェイスなのに腹筋が割れている。
# この「ギャップ」が0.5秒で人を止める。
# Nike/Adidas/Lululemonが組みたくなる唯一のAI美女。
# ═══════════════════════════════════════════════════════════

# ベンチマーク: @i.am_natsuki_ (186万フォロワー), @373off
# あの超スレンダー体型 × ベビーフェイスが基準。それ以下は論外。
MAIA_IDENTITY = """extremely beautiful young Japanese girl, 20 years old, baby face, full body shot from head to toe.
Face: adorable small round baby face, big sparkling doe eyes, cute button nose, plump glossy pink lips, dimples, double eyelids. Looks like a Japanese idol.
Skin: flawless glowing dewy skin, porcelain smooth, youthful.
Hair: glossy dark brown, silky, long past shoulders, natural soft waves.
Body: EXTREMELY slender and slim, super skinny tiny waist, very long slim legs, thigh gap, flat toned stomach, full bust, nice round perky hips, prominent collarbones, slim arms. 170cm tall with extremely long legs. Supermodel body proportions like a Victoria's Secret angel. Think Natsuki Abe body type — impossibly slim yet curvy.
IMPORTANT: always show FULL BODY from head to feet. The body is the signature. Never crop at waist.
Signature: delicate thin vintage silver watch on left wrist.
""".strip()

# おばさん化を防ぐ＋アスリート感を保つネガティブプロンプト
NEGATIVE_PROMPT = "old, aged, wrinkles, mature face, sagging skin, dark circles, tired, rough skin, large pores, thick neck, overweight, soft body, no muscle definition, cartoon, anime, illustration, 3D render, lowres, blurry, deformed, ugly, bad anatomy, masculine jaw"

MAIA_FACE_PROMPT = f"""FULL BODY photograph from head to feet of {MAIA_IDENTITY}
Long glossy dark brown hair down, soft waves, curtain bangs.
Wearing white fitted crop top and high-waisted mini skirt showing her extremely slim waist, long bare legs from thigh to feet, white sneakers.
Full body visible head to toe. Her super slender figure is the focus — impossibly thin waist, long model legs, perfect proportions.
Adorable baby face smiling sweetly at camera, big doe eyes, dimples. Cute face, killer body.
Bright Tokyo apartment, golden morning light, clean white aesthetic.
Full body shot, 35mm lens, warm golden tones, photorealistic, 8K, fashion editorial.
Avoid: {NEGATIVE_PROMPT}
""".strip()

MAIA_SCENE_PROMPTS = {
    "portrait_warm": MAIA_FACE_PROMPT,

    "selfie_cute": f"""FULL BODY mirror selfie from head to feet of {MAIA_IDENTITY}
Long glossy hair down, soft waves. Dewy glowing skin.
Wearing cropped tank top and tiny denim shorts — her entire super slender body visible in full length mirror: extremely thin waist, long slim legs, thigh gap, nice figure. Head to toe reflected.
Adorable cute face, peace sign, sweet smile. Baby face on a supermodel body.
Bright room, full length mirror, warm sunlight.
iPhone selfie, full body visible, warm golden tones, photorealistic.
Avoid: {NEGATIVE_PROMPT}
""".strip(),

    "workout_power": f"""FULL BODY gym photograph from head to feet of {MAIA_IDENTITY}
Hair in high ponytail.
Wearing black sports bra and black leggings. Her ENTIRE body visible head to toe: super slender waist, flat toned stomach, full bust, round hips, very long slim toned legs. Think Natsuki Abe proportions.
Standing full body, one hand on hip, cute confident smirk on her baby face.
Premium gym, golden light, mirrors.
Full body shot, 35mm f/1.8, dramatic lighting showing her incredible slim silhouette.
Ultra photorealistic. Gymshark campaign quality.
Avoid: {NEGATIVE_PROMPT}
""".strip(),

    "bikini_pool": f"""FULL BODY photograph from head to feet of {MAIA_IDENTITY}
Long glossy hair down, slightly wet, sun-kissed.
Wearing simple white bikini. Her full body visible: extremely slender tiny waist, flat stomach, full bust, beautiful hips, very long slim legs, thigh gap. Perfect supermodel proportions.
Standing by infinity pool edge, one hand in hair. Adorable sweet smile on her baby face looking at camera.
Bright blue sky, turquoise pool water, tropical resort setting, golden sunlight.
Full body shot head to toe, 35mm lens, bright vivid colors, sun-kissed skin glow.
Ultra photorealistic, Sports Illustrated swimsuit quality.
Avoid: {NEGATIVE_PROMPT}
""".strip(),

    "evening_intimate": f"""FULL BODY photograph from head to feet of {MAIA_IDENTITY}
Hair down, soft waves. Wearing oversized cream knit sweater as dress, barely covering her thighs, showing extremely long bare slim legs all the way down to bare feet.
Even in cozy mode her super slender figure is obvious — tiny waist, long legs, model proportions.
Standing by window in warm lamplight, hugging a mug, sweet innocent expression, big doe eyes.
Cat at her feet. Warm golden tones, intimate evening light.
Full body shot, 50mm f/1.4, warm tones. Photorealistic. Baby face, supermodel legs.
Avoid: {NEGATIVE_PROMPT}
""".strip(),

    "tokyo_golden": f"""FULL BODY photograph from head to feet of {MAIA_IDENTITY}
Long hair flowing in breeze, golden backlight halo.
Wearing fitted cropped jacket, tiny waist belt, mini skirt showing her incredibly long slim legs, heeled boots.
Walking through Tokyo at golden hour, full body visible, looking back over shoulder with adorable bright smile.
Her silhouette from behind shows her super slender figure — impossibly thin waist, long legs, perfect proportions.
Bokeh Tokyo street, warm golden tones.
Full body shot, 50mm f/1.4, Kodak Portra warmth. Ultra photorealistic. Scroll-stopping.
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
