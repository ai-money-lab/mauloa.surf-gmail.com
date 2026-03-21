"""Generate Riena — production-quality AI character images.

Imagen 4.0 Ultra (Google最高品質) をデフォルトで使用。
Gemini generateContent は補助。本気で世界を取るならImagen。

Usage:
    # Imagen 4.0 Ultra (最高品質・デフォルト):
    GEMINI_API_KEY=your_key python3 system_e/generate_riena_face.py

    # Gemini (fallback):
    GEMINI_API_KEY=your_key python3 system_e/generate_riena_face.py --gemini

    # FAL.ai Flux Pro (要FAL_API_KEY):
    FAL_API_KEY=your_key python3 system_e/generate_riena_face.py --fal

    # 全シーン一括:
    GEMINI_API_KEY=your_key python3 system_e/generate_riena_face.py --all-scenes

    # 1シーンN枚生成（ベストを選ぶ）:
    GEMINI_API_KEY=your_key python3 system_e/generate_riena_face.py --count 4
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
# キャラクター定義: Riena
#
# Aitana Lopez ($10K+/月) の制作者が使うテクニック:
# 1. 超具体的な顔の特徴（毎回同じ人物に見える）
# 2. 不完全さ（完璧はAIっぽい。肌質感、乱れ髪）
# 3. フィルム感（Kodak Portra, Fuji Pro 400H = リアリティ）
# 4. 実在する場所の空気感
# ═══════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════
# Rienaのシグネチャー: 「きれい系ハーフ × アスリート体型」
#
# AI美女界のポジションマップ:
#   凛、Aitana → かわいい/セクシー × ファッション（飽和）
#   imma       → かわいい × ハイファッション（飽和）
#   Riena       → きれい系ハーフ顔 × スレンダー体型（空席！！）
#
# 凛とした美しさ × 健康的なスレンダー体型。
# この「知的な色気」が0.5秒で人を止める。
# Nike/Adidas/Lululemonが組みたくなる唯一のAI美女。
# ═══════════════════════════════════════════════════════════

RIENA_IDENTITY = """extremely beautiful young Japanese woman, 24 years old, elegant refined face, half-Japanese aesthetic.
Face: oval face with slim jawline and delicate chin, large almond-shaped dark brown eyes with soft intelligent gaze, double eyelids, straight elegant nose with slightly high bridge, slightly full natural pink lips, softly arched natural eyebrows. Serene confident expression with hint of mystery. Looks like a Japanese-Korean model or actress — refined beauty NOT cute idol type.
Skin: flawless luminous fair porcelain skin, natural dewy glow, smooth and clear, does not tan easily.
Hair: glossy dark brown to near-black, very long past shoulders, loose soft waves with natural volume, wispy face-framing pieces, natural movement.
Body: slender with soft feminine curves, slim waist, flat stomach, long legs, delicate sloping shoulders, visible delicate collarbones, slim arms, graceful proportions. 168cm tall. Model-like silhouette — slim yet feminine, NOT muscular or athletic.
Signature: delicate thin vintage silver watch on left wrist.
""".strip()

# NG要素を防ぐネガティブプロンプト
NEGATIVE_PROMPT = "baby face, round face, childish, cute idol look, dimples, button nose, glossy plump lips, overweight, thick, muscular bodybuilder, cartoon, anime, illustration, 3D render, lowres, blurry, deformed, ugly, bad anatomy, masculine jaw, aged, wrinkles, sagging"

RIENA_FACE_PROMPT = f"""Close-up portrait photograph of {RIENA_IDENTITY}
Hair down in loose soft waves with face-framing wispy pieces, natural volume.
Wearing off-shoulder cream white blouse, showing elegant collarbones and shoulders.
Serene confident expression, soft gaze directly at camera, slightly parted lips.
Bright airy room, soft natural window light from behind, clean white background.
Portrait shot, 85mm f/1.4, shallow depth of field, warm soft tones, photorealistic, 8K.
Avoid: {NEGATIVE_PROMPT}
""".strip()

RIENA_SCENE_PROMPTS = {
    "portrait_warm": RIENA_FACE_PROMPT,

    "selfie_natural": f"""Natural mirror selfie of {RIENA_IDENTITY}
Long dark brown hair down, soft waves. Luminous dewy skin, minimal natural makeup.
Wearing simple fitted white tank top and high-waisted jeans, her slender graceful figure visible in mirror. Delicate collarbones, slim waist.
Calm confident expression, soft slight smile, one hand holding phone, elegant pose.
Bright room, full length mirror, warm morning sunlight.
iPhone selfie, natural tones, photorealistic. Elegant NOT cute.
Avoid: {NEGATIVE_PROMPT}
""".strip(),

    "workout_power": f"""Gym photograph of {RIENA_IDENTITY}
Hair in sleek high ponytail, showing her elegant jawline and neck.
Wearing black sports bra and black leggings. Slender toned body: slim waist, toned stomach, graceful proportions, long legs.
Standing with quiet confidence, one hand on hip, calm focused expression.
Premium gym, golden warm light, mirrors reflecting.
Full body shot, 35mm f/1.8, dramatic lighting on her slim silhouette.
Ultra photorealistic. Nike campaign quality — athletic elegance.
Avoid: {NEGATIVE_PROMPT}
""".strip(),

    "bikini_pool": f"""Poolside photograph of {RIENA_IDENTITY}
Long dark brown hair down, slightly tousled by breeze, sun-kissed glow.
Wearing simple white bikini. Slender graceful body: slim waist, toned stomach, elegant proportions, long legs.
Standing by infinity pool, one hand gently touching hair. Serene confident gaze at camera, soft natural expression.
Bright blue sky, turquoise pool water, tropical resort, golden sunlight.
Full body shot, 35mm lens, bright natural colors, warm sun-kissed skin.
Ultra photorealistic. Refined elegance, NOT idol-like.
Avoid: {NEGATIVE_PROMPT}
""".strip(),

    "evening_intimate": f"""Evening portrait photograph of {RIENA_IDENTITY}
Hair down in loose waves, soft and natural. Wearing oversized cream knit sweater, off one shoulder, showing delicate collarbones. Bare legs, bare feet.
Slender graceful figure visible even in cozy clothing.
Standing by window, warm lamplight, holding a mug with both hands. Soft reflective expression, gentle slight smile, eyes looking slightly away.
Orange tabby cat at her feet. Warm golden amber tones, intimate evening atmosphere.
Medium shot, 50mm f/1.4, warm film tones, Kodak Portra feel. Photorealistic.
Avoid: {NEGATIVE_PROMPT}
""".strip(),

    "tokyo_golden": f"""Street photograph of {RIENA_IDENTITY}
Long dark brown hair flowing in gentle breeze, golden backlight creating a soft halo.
Wearing fitted beige trench coat, slim belt at waist, midi skirt, low heels. Elegant Tokyo street style.
Walking through Tokyo at golden hour, looking back over shoulder with calm confident half-smile.
Slender silhouette backlit, graceful proportions visible.
Bokeh Tokyo street lights, warm golden tones, Shinjuku or Omotesando atmosphere.
Full body shot, 50mm f/1.4, Kodak Portra warmth. Ultra photorealistic. Scroll-stopping refined beauty.
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
        path = _save_image(base64.b64decode(image_b64), f"riena_{model}", ext)
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
                        path = _save_image(image_bytes, f"riena_{model}", ext)
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
                path = _download_image(image_url, "riena_flux_pro")
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
# ImagePipeline (RunPod / ComfyUI Pod) — config.yamlのproviderを使用
# ═══════════════════════════════════════════════════════════

def _generate_with_pipeline(scene: str, prompt: str, count: int = 1) -> list[str]:
    """Generate images using the ImagePipeline (RunPod/ComfyUI/FAL via config)."""
    from system_e.image_pipeline import ImagePipeline

    pipeline = ImagePipeline()
    logger.info("ImagePipeline provider: %s, enabled: %s", pipeline.provider, pipeline.enabled)

    if not pipeline.enabled:
        logger.error("ImagePipeline is disabled. Check config/config.yaml and API keys.")
        return []

    saved = []
    for i in range(count):
        logger.info("ImagePipeline generation %d/%d (scene=%s)...", i + 1, count, scene)
        result_path = pipeline.generate_for_scene(scene, extra_prompt=prompt, aspect_ratio="3:4")
        if result_path:
            saved.append(result_path)
            logger.info("Generated: %s", result_path)
        else:
            logger.warning("Generation %d/%d failed", i + 1, count)

        if count > 1 and i < count - 1:
            time.sleep(1)

    return saved


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
    parser = argparse.ArgumentParser(description="Generate Riena — production quality")
    parser.add_argument("--gemini", action="store_true", help="Force Gemini generateContent (lower quality)")
    parser.add_argument("--fal", action="store_true", help="Use FAL.ai Flux Pro (requires FAL_API_KEY)")
    parser.add_argument("--runpod", action="store_true", help="Use ImagePipeline (RunPod/ComfyUI — uses config/config.yaml provider)")
    parser.add_argument("--scene", choices=list(RIENA_SCENE_PROMPTS.keys()), default="portrait_warm")
    parser.add_argument("--all-scenes", action="store_true", help="Generate all scenes")
    parser.add_argument("--count", type=int, default=1, help="Number of images per scene (pick the best)")
    parser.add_argument("--dry-run", action="store_true", help="Show prompts only")
    args = parser.parse_args()

    scenes = list(RIENA_SCENE_PROMPTS.keys()) if args.all_scenes else [args.scene]

    total_generated = 0
    for scene in scenes:
        prompt = RIENA_SCENE_PROMPTS[scene]
        print(f"\n{'='*60}")
        print(f"Scene: {scene}")
        print(f"{'='*60}")

        if args.dry_run:
            print(f"Prompt:\n{prompt}\n")
            print("[DRY RUN] Skipping generation.")
            continue

        api_key = os.getenv("GEMINI_API_KEY", "")
        fal_key = os.getenv("FAL_API_KEY", "")

        if args.runpod:
            results = _generate_with_pipeline(scene, prompt, count=args.count)
        elif args.fal:
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
            # Default: try ImagePipeline first, then Imagen
            if api_key:
                results = generate_with_imagen(prompt, api_key, count=args.count)
            else:
                print("INFO: GEMINI_API_KEY not set. Using ImagePipeline (RunPod/ComfyUI)...")
                results = _generate_with_pipeline(scene, prompt, count=args.count)

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
