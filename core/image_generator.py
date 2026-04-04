"""Gemini Imagen (Nano Banana 2) image generation client.

Uses Google Gemini API to generate images from text prompts.
Free tier: up to 500 images/day.
"""

import base64
import logging
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
IMAGE_DIR = Path(__file__).parent.parent / "data" / "system_a" / "images"


class ImageGenerator:
    """Generate images using Google Gemini Imagen API."""

    GENERATE_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent"

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    @property
    def enabled(self) -> bool:
        """Check if image generation is configured."""
        return bool(self.api_key)

    def generate_image(self, prompt: str) -> str | None:
        """Generate an image from a text prompt.

        Args:
            prompt: Image generation prompt (English recommended for best results).

        Returns:
            Path to the saved image file, or None on failure.
        """
        if not self.enabled:
            logger.warning("GEMINI_API_KEY not set — skipping image generation")
            return None

        url = f"{self.GENERATE_URL}?key={self.api_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"],
            },
        }

        try:
            resp = requests.post(url, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()

            # Extract image from response
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

                    now = datetime.now(JST)
                    filename = now.strftime("%Y%m%d_%H%M%S") + f".{ext}"
                    filepath = IMAGE_DIR / filename
                    filepath.write_bytes(image_bytes)
                    logger.info("Image saved: %s (%d bytes)", filepath, len(image_bytes))
                    return str(filepath)

            logger.warning("No image data found in Gemini response")
            return None

        except requests.exceptions.Timeout:
            logger.error("Gemini API timeout (60s)")
            return None
        except requests.exceptions.HTTPError as e:
            logger.error("Gemini API HTTP error: %s", e)
            return None
        except Exception as e:
            logger.error("Image generation failed: %s", e)
            return None

    def generate_for_post(self, post_text: str, pillar: int = 0) -> str | None:
        """Generate an image suitable for an X post.

        Creates an image prompt from the post text and pillar,
        then generates the image.

        Args:
            post_text: The X post text content.
            pillar: The content pillar number (1-5).

        Returns:
            Path to the saved image file, or None on failure.
        """
        image_prompt = build_image_prompt(post_text, pillar)
        logger.info("Image prompt: %s", image_prompt[:100])
        return self.generate_image(image_prompt)


# ── Image prompt builder ──────────────────────────────────

PILLAR_VISUAL_HINTS = {
    1: "real estate, house, property, warm residential scene",
    2: "apartment building, property management, modern building exterior",
    3: "cozy room interior, moving boxes, comfortable living space",
    4: "financial planning, home and money balance, piggy bank with house",
    5: "lifestyle, plants, coffee, peaceful daily moment",
}

STYLE_DIRECTIVE = (
    "Clean, modern Japanese infographic style illustration. "
    "Soft warm color palette (beige, light blue, soft green). "
    "Minimalist design, no text overlay, no words, no letters. "
    "Suitable for Instagram Reels. "
    "Friendly and approachable mood, NOT corporate or cold. "
    "9:16 vertical aspect ratio, 1080x1920 pixels."
)


def build_image_prompt(post_text: str, pillar: int = 0) -> str:
    """Build an image generation prompt from post text and pillar.

    Extracts the core concept from the post and combines it with
    pillar-specific visual hints and a consistent style directive.
    """
    # Get pillar visual hint
    visual_hint = PILLAR_VISUAL_HINTS.get(pillar, "lifestyle, housing, daily life")

    # Build the prompt
    prompt = (
        f"Create an illustration about: {visual_hint}. "
        f"The topic is related to: {post_text[:200]}. "
        f"{STYLE_DIRECTIVE}"
    )

    return prompt
