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
MAIA_IDENTITY = """young Japanese woman, age 26, named Maia.
Face: oval face shape, high cheekbones with subtle definition, small straight nose with a very slight upturn at the tip, naturally full lips with a soft cupid's bow, clear double eyelids.
Eyes: large almond-shaped dark brown eyes, naturally thick long eyelashes, slight upward tilt at outer corners giving a gentle cat-eye effect.
Eyebrows: straight natural thick eyebrows with soft arch, dark brown, slightly messy and unfilled.
Skin: warm golden undertone, smooth but with natural skin texture visible — tiny pores on nose, faint beauty mark below left eye, very subtle light freckles across nose bridge from sun exposure. Healthy natural glow, no heavy foundation look.
Hair: dark chocolate brown, thick and healthy, medium length past shoulders. Natural slight wave texture, not perfectly straight.
Body: slim athletic build with toned arms and visible collarbone definition, long neck. 165cm, lean muscle tone from regular training.
Signature: vintage thin silver watch on left wrist (her late mother's).
""".strip()

MAIA_FACE_PROMPT = f"""Intimate portrait photograph of {MAIA_IDENTITY}
Hair styled in a loose low messy bun with soft wispy pieces framing face and neck.
Wearing a simple white ribbed tank top, minimal jewelry.
Expression: warm knowing half-smile, eyes slightly crinkled with genuine warmth, looking directly into camera as if sharing a private moment with someone she trusts.
Setting: bright airy Tokyo apartment kitchen, morning. Soft natural window light from the left creating gentle shadows. A ceramic cup of matcha with foam art on white marble counter. Green plants soft in background. Everything feels lived-in and real.
Shot on Fujifilm X-T5 with XF 56mm f/1.2 lens, shot wide open. Fuji Pro 400H film simulation, warm muted tones with creamy skin rendering. Shallow depth of field, focus on eyes. Natural light only, no flash.
This looks like a real photograph taken by her boyfriend on a lazy Sunday morning. Not staged, not perfect, real.
""".strip()

MAIA_SCENE_PROMPTS = {
    "portrait_warm": MAIA_FACE_PROMPT,

    "selfie_cute": f"""Casual mirror selfie photograph of {MAIA_IDENTITY}
Hair down, natural waves, slightly messy from just waking up. Curtain bangs softly parted.
Wearing an oversized cream cable-knit sweater slipping off one shoulder, bare collarbone visible.
Holding iPhone at slightly above eye level, other hand touching hair.
Expression: playful sleepy smile, one eyebrow slightly raised, eyes half-lidded but sparkling.
Background: sunlit bedroom, white linen sheets unmade, morning light through sheer curtains, small potted plants on windowsill.
Shot on iPhone 15 Pro, portrait mode, natural morning light. The effortless kind of selfie that gets 10K likes because it feels unplanned. Slight lens flare from window. Warm golden tones, soft and dreamy.
""".strip(),

    "workout_power": f"""Fitness photograph of {MAIA_IDENTITY}
Hair in sleek high ponytail, baby hairs along hairline, few loose strands stuck to temples from sweat.
Athletic body on full display — toned shoulders, lean visible abs, defined arms. Skin glistening with light sweat catching overhead lights.
Wearing matte black sports bra and matching high-waisted compression leggings, white training shoes, silver watch.
She's just finished a set of deadlifts, standing tall with one hand on the barbell, other hand on hip. Chest slightly heaving. Expression: fierce quiet confidence, slight smirk, direct eye contact with camera.
Setting: premium minimal gym, concrete floors, natural wood accents, large mirrors. Golden hour light streaming through floor-to-ceiling windows mixing with warm overhead spots.
Shot on Sony A7IV, 85mm f/1.4 GM lens. Dramatic side lighting creating sculptural shadows on muscle definition. Shot at 1/500s freezing any motion. Slight orange and teal color grade. This is an Adidas or Nike campaign image.
""".strip(),

    "evening_intimate": f"""Intimate evening photograph of {MAIA_IDENTITY}
Hair completely down, natural waves, slightly tangled. No makeup, bare natural face — slightly flushed cheeks, lips naturally pink.
Wearing an oversized vintage cream wool cardigan over a thin white camisole, soft cotton shorts. Bare legs tucked underneath her.
She's sitting on a worn Persian rug on wooden apartment floor, leaning against the couch. An old leather notebook open in her lap — her mother's handwritten recipes visible. Expression: tender and thoughtful, looking down at the notebook, lashes casting shadows on cheeks. An orange tabby cat curled asleep pressed against her thigh.
Warm golden light from a single vintage brass table lamp. Background: bookshelves, stacked paperbacks, a half-drunk cup of hojicha tea, a small framed photo.
Shot on Leica Q3, 28mm f/1.7, available warm lamp light only. Kodak Portra 800 pushed, visible grain, deep warm shadows. The intimacy of this image is almost uncomfortable — you feel like you're seeing something private.
""".strip(),

    "matcha_aesthetic": f"""Overhead lifestyle photograph featuring {MAIA_IDENTITY}
Only her hands and partial face visible from above. Graceful fingers with short clean nails, thin silver watch on left wrist.
She's whisking vibrant emerald matcha in a handmade ceramic chawan. The surface around her: bamboo chasen whisk, a small plate with two delicate wagashi, folded linen napkin, her phone face-down.
Her face partially visible at top of frame: soft smile, eyes focused on the matcha, dark brown hair in messy low bun with a wooden hair stick.
Morning golden directional light from upper left creating long dramatic shadows. White oak counter surface.
Shot on Canon R5, RF 35mm f/1.4 from directly above on tripod. Perfectly styled but feels organic — a few matcha powder specks on the counter, a slight water ring from the cup. Japanese minimalism meets Kinfolk magazine aesthetic.
""".strip(),

    "tokyo_golden": f"""Street fashion photograph of {MAIA_IDENTITY}
Hair down with natural movement from walking, catching golden backlight creating a halo rim-light effect.
Wearing a perfectly fitted camel wool coat over a white crew-neck tee, high-waisted straight-leg vintage Levi's, white Adidas Sambas. Canvas tote bag on shoulder, thin silver watch visible at wrist.
She's walking through Daikanyama backstreets at golden hour, glancing back over her shoulder at camera with a magnetic smile — teeth slightly showing, eyes alive with warmth.
Background: soft bokeh of warm Tokyo residential street, old wooden buildings, a bicycle, green hedge, dappled light through trees.
Shot on Contax T2 with Kodak Portra 400, 38mm f/2.8. Real film grain, warm nostalgic color palette. Natural golden backlight. This is the photo that makes someone fall in love. Editorial street style meets stolen moment.
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
