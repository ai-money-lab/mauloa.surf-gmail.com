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
Face: oval face with slim jawline and delicate small chin, soft rounded cheeks. Large round-almond dark brown eyes with big sparkling irises, slightly downturned outer corners, double eyelids, warm gentle gaze. Straight refined nose, natural height. Slightly full natural pink lips with rounded upper lip. Softly arched natural eyebrows. Default expression: warm soft closed-lip smile with slight head tilt, approachable and gentle. Sometimes serene/mysterious or slightly pouty. Looks like a Japanese-Korean model or actress — refined elegant beauty.
Skin: flawless luminous very fair porcelain skin, semi-matte to dewy finish, smooth and clear, does not tan easily.
Hair: glossy medium brown (NOT black), long past shoulders, loose soft waves or straight, wispy sheer bangs (see-through bangs), face-framing pieces, natural movement.
Body: very slender with soft feminine curves, naturally slim but subtly toned, very slim waist with visible waistline, flat stomach with faint vertical line, medium natural bust, well-rounded firm hips, delicate sloping shoulders, prominent collarbones, very slim arms, long slim legs with thigh gap, long neck, thin profile from side. 168cm tall. Petite upper body with slightly curvier lower body — naturally slim Japanese model body type, NOT muscular.
Signature: delicate thin vintage silver watch on left wrist.
""".strip()

# NG要素を防ぐネガティブプロンプト
NEGATIVE_PROMPT = "baby face, round face, childish, cute idol look, dimples, button nose, glossy plump lips, overweight, thick, muscular bodybuilder, cartoon, anime, illustration, 3D render, lowres, blurry, deformed, ugly, bad anatomy, masculine jaw, aged, wrinkles, sagging"

RIENA_FACE_PROMPT = f"""Close-up portrait photograph of {RIENA_IDENTITY}
Medium brown hair down in loose soft waves with face-framing wispy pieces, sheer bangs.
Wearing off-shoulder cream white blouse, showing elegant collarbones and sloping shoulders.
Warm soft closed-lip smile, gentle gaze directly at camera, head slightly tilted.
Bright airy room, soft natural window light from behind, clean white background.
Portrait shot, 85mm f/1.4, shallow depth of field, warm soft tones, photorealistic, 8K.
Avoid: {NEGATIVE_PROMPT}
""".strip()

RIENA_SCENE_PROMPTS = {
    "portrait_warm": RIENA_FACE_PROMPT,

    "selfie_natural": f"""Natural mirror selfie of {RIENA_IDENTITY}
Medium brown hair down, soft waves, sheer bangs. Very fair luminous skin, minimal natural makeup.
Wearing simple fitted white tank top and high-waisted jeans, slender figure visible in mirror. Prominent collarbones, very slim waist.
Warm soft smile, one hand holding phone, elegant relaxed pose.
Bright room, full length mirror, warm morning sunlight.
iPhone selfie, natural tones, photorealistic. Elegant NOT cute.
Avoid: {NEGATIVE_PROMPT}
""".strip(),

    "workout_power": f"""Gym photograph of {RIENA_IDENTITY}
Medium brown hair in sleek high ponytail, showing elegant jawline and long neck.
Wearing brown sports bra and brown bike shorts. Very slender subtly toned body: very slim waist, flat stomach with faint vertical line, medium bust, long slim legs.
Standing with quiet confidence, one hand on hip, calm focused expression.
Premium gym, golden warm light, mirrors reflecting.
Full body shot, 35mm f/1.8, dramatic lighting on slim silhouette.
Ultra photorealistic. Nike campaign quality — athletic elegance.
Avoid: {NEGATIVE_PROMPT}
""".strip(),

    "bikini_pool": f"""Poolside photograph of {RIENA_IDENTITY}
Medium brown hair down, slightly tousled by breeze, very fair porcelain skin.
Wearing simple white bikini. Very slender body with soft feminine curves: very slim waist, flat stomach, medium natural bust, well-rounded hips, long slim legs with thigh gap.
Standing by infinity pool, one hand gently touching hair. Warm soft smile at camera.
Bright blue sky, turquoise pool water, tropical resort, bright natural sunlight.
Full body shot, 35mm lens, bright natural colors, fair skin in sunlight.
Ultra photorealistic. Refined elegance, NOT idol-like.
Avoid: {NEGATIVE_PROMPT}
""".strip(),

    "evening_intimate": f"""Evening portrait photograph of {RIENA_IDENTITY}
Medium brown hair down in loose waves, soft and natural, sheer bangs. Wearing oversized cream knit sweater, off one shoulder, showing delicate collarbones and sloping shoulders. Bare legs, bare feet.
Very slender figure visible even in cozy clothing.
Standing by window, warm lamplight, holding a mug with both hands. Warm gentle smile, eyes looking slightly away.
Warm golden amber tones, intimate evening atmosphere.
Medium shot, 50mm f/1.4, warm film tones, Kodak Portra feel. Photorealistic.
Avoid: {NEGATIVE_PROMPT}
""".strip(),

    "tokyo_golden": f"""Street photograph of {RIENA_IDENTITY}
Medium brown hair flowing in gentle breeze, golden backlight creating a soft halo.
Wearing fitted beige trench coat, slim belt at very slim waist, midi skirt, low heels. Elegant Tokyo street style.
Walking through Tokyo at golden hour, looking back over shoulder with warm soft half-smile.
Very slender silhouette backlit, slim waist and long legs visible.
Bokeh Tokyo street lights, warm golden tones, Shinjuku or Omotesando atmosphere.
Full body shot, 50mm f/1.4, Kodak Portra warmth. Ultra photorealistic.
Avoid: {NEGATIVE_PROMPT}
""".strip(),

    # ─── LoRA学習用追加シーン ───
    "lora_front_neutral": f"""Front-facing portrait photograph of {RIENA_IDENTITY}
Medium brown hair with sheer bangs, loose waves. Looking directly at camera.
Wearing black turtleneck sweater. Warm soft closed-lip smile, head slightly tilted.
Very fair porcelain skin, large dark brown eyes with sparkling irises.
Plain white background, studio soft lighting, even illumination.
Headshot, 85mm f/2.0, sharp focus on face, photorealistic, 8K.
Avoid: {NEGATIVE_PROMPT}
""".strip(),

    "lora_threequarter_left": f"""Three-quarter left portrait of {RIENA_IDENTITY}
Medium brown hair with sheer bangs, soft waves. Face turned slightly left, eyes at camera.
Wearing simple grey crew neck t-shirt. Gentle serene expression.
Very fair porcelain skin, visible jawline and chin profile.
Plain light grey background, natural soft lighting.
Portrait shot, 85mm f/1.8, shallow depth of field, photorealistic.
Avoid: {NEGATIVE_PROMPT}
""".strip(),

    "lora_threequarter_right": f"""Three-quarter right portrait of {RIENA_IDENTITY}
Medium brown hair with sheer bangs, soft waves. Face turned slightly right, warm gentle gaze.
Wearing white off-shoulder knit top, collarbones visible, sloping shoulders.
Warm soft smile, natural makeup, very fair skin.
Plain cream background, warm studio lighting.
Portrait shot, 85mm f/1.8, shallow depth of field, photorealistic.
Avoid: {NEGATIVE_PROMPT}
""".strip(),

    "lora_profile_left": f"""Left profile portrait of {RIENA_IDENTITY}
Medium brown hair down, showing left side profile. Straight refined nose, slim jawline, delicate chin, long neck.
Wearing black sleeveless top. Serene calm expression.
Very fair porcelain skin, prominent collarbones.
Clean dark background, dramatic side lighting.
Profile portrait, 85mm f/2.0, sharp focus, photorealistic.
Avoid: {NEGATIVE_PROMPT}
""".strip(),

    "lora_full_body_casual": f"""Full body photograph of {RIENA_IDENTITY}
Medium brown hair with sheer bangs, loose waves. Standing naturally, weight on one leg.
Wearing blue crop t-shirt and white high-waisted jeans with crossbody bag. Flat stomach visible, very slim waist, sloping shoulders.
Warm soft smile, looking slightly to the side.
Tokyo street, overcast daylight, concrete building background.
Full body shot, 35mm f/2.0, street photography style, photorealistic.
Avoid: {NEGATIVE_PROMPT}
""".strip(),

    "lora_full_body_dress": f"""Full body photograph of {RIENA_IDENTITY}
Medium brown hair down, loose waves. Standing elegantly.
Wearing black off-shoulder midi dress and heels. Very slender figure: slim waist, long slim legs, sloping shoulders, medium bust.
Serene confident expression, looking to the side.
Tokyo alley at golden hour, warm backlight.
Full body shot, 50mm f/1.4, warm tones, photorealistic.
Avoid: {NEGATIVE_PROMPT}
""".strip(),

    "lora_bikini_beach": f"""Beach photograph of {RIENA_IDENTITY}
Medium brown hair slightly wet from ocean, natural. Very fair porcelain skin.
Wearing black triangle string bikini. Very slender body: very slim waist, flat stomach with faint line, medium bust, well-rounded firm hips, long slim legs, thigh gap.
Standing in shallow water, natural relaxed pose. Calm serene expression.
Tropical beach, turquoise water, bright daylight, blue sky.
Full body shot, 35mm lens, natural bright colors, photorealistic.
Avoid: {NEGATIVE_PROMPT}
""".strip(),

    "lora_gym_mirror": f"""Gym mirror selfie of {RIENA_IDENTITY}
Medium brown hair in ponytail. Wearing black sports bra and black leggings.
Very slender subtly toned body: flat stomach with faint vertical line, very slim waist, medium bust, slim arms, prominent collarbones.
Holding phone in mirror, calm confident expression.
Modern gym background, fluorescent lighting.
Mirror selfie, iPhone quality, natural tones, photorealistic.
Avoid: {NEGATIVE_PROMPT}
""".strip(),

    "lora_seated_cafe": f"""Cafe photograph of {RIENA_IDENTITY}
Medium brown hair with sheer bangs, shoulder length with layers. Silver hoop earrings.
Wearing blue ribbed knit sleeveless high-neck top. Sitting at cafe table.
Warm soft closed-lip smile, head tilted, hand near face. Large dark brown sparkling eyes.
Very fair luminous skin.
Cozy cafe interior, warm ambient lighting.
Close-up portrait, 50mm f/1.4, warm tones, photorealistic.
Avoid: {NEGATIVE_PROMPT}
""".strip(),

    "lora_back_view_sporty": f"""Rear view photograph of {RIENA_IDENTITY}
Medium brown hair down, natural. Wearing grey crop top and grey shorts.
Slim back, very slim waist from behind, well-rounded firm hips and buttocks, slim thighs.
Walking away, looking slightly over shoulder.
Seaside walkway, bright overcast sky, ocean background.
Full body rear view, 35mm lens, bright natural daylight, photorealistic.
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
