"""System E — AI Character Image Generation Pipeline.

Generates character-consistent images using FAL.ai (Flux models)
with LoRA support for identity preservation.
"""

import json
import logging
import os
import random
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
import yaml
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
CONFIG_PATH = Path(__file__).parent / "character_config.yaml"
IMAGE_DIR = Path(__file__).parent.parent / "data" / "system_e" / "images"
GENERATED_DIR = Path(__file__).parent.parent / "data" / "system_e" / "generated"


def load_character_config() -> dict:
    """Load character configuration from YAML."""
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


class ImagePipeline:
    """Generate character-consistent images via FAL.ai Flux models."""

    # FAL.ai endpoints
    FAL_FLUX_PRO_URL = "https://queue.fal.run/fal-ai/flux-pro/v1.1-ultra"
    FAL_FLUX_KONTEXT_URL = "https://queue.fal.run/fal-ai/flux-pro/kontext"
    FAL_STATUS_URL = "https://queue.fal.run/fal-ai/flux-pro"

    def __init__(self):
        self.fal_api_key = os.getenv("FAL_API_KEY", "")
        self.config = load_character_config()
        self.character = self.config["character"]
        self.image_config = self.config["image_generation"]
        IMAGE_DIR.mkdir(parents=True, exist_ok=True)
        GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    @property
    def enabled(self) -> bool:
        return bool(self.fal_api_key)

    def _fal_headers(self) -> dict:
        return {
            "Authorization": f"Key {self.fal_api_key}",
            "Content-Type": "application/json",
        }

    def _build_character_prompt(self, scene: str, extra: str = "") -> str:
        """Build a prompt that maintains character consistency.

        Combines character visual identity with scene description.
        """
        char = self.character
        visual = char["visual_identity"]
        lora = self.image_config.get("lora", {})
        trigger = lora.get("trigger_word", "")

        # Base character description
        parts = []
        if trigger:
            parts.append(trigger)

        parts.extend([
            f"A {char['age']}-year-old {visual.get('ethnicity', '')} woman",
            f"with {visual.get('hair', 'dark hair')}",
            f"{visual.get('body_type', 'fit')} build",
            f"wearing {visual.get('style', 'casual athletic clothing')}",
        ])

        # Add signature elements
        for elem in visual.get("signature_elements", []):
            parts.append(elem.lower())

        # Add scene
        scene_config = self.image_config.get("scene_categories", {}).get(scene, {})
        scene_prefix = scene_config.get("prompts_prefix", scene)
        parts.append(scene_prefix)

        if extra:
            parts.append(extra)

        # Photo quality directives
        parts.extend([
            "professional photography",
            "natural lighting",
            "high quality",
            "sharp focus",
            "4K detail",
        ])

        return ", ".join(parts)

    def generate_flux_pro(
        self,
        prompt: str,
        aspect_ratio: str = "3:4",
        seed: int | None = None,
    ) -> str | None:
        """Generate an image using Flux Pro v1.1 Ultra via FAL.ai.

        Args:
            prompt: The full image generation prompt.
            aspect_ratio: Image aspect ratio (e.g., "3:4", "16:9", "1:1").
            seed: Optional seed for reproducibility.

        Returns:
            Path to saved image file, or None on failure.
        """
        if not self.enabled:
            logger.warning("FAL_API_KEY not set — skipping image generation")
            return None

        payload = {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "output_format": "jpeg",
            "safety_tolerance": "2",
        }
        if seed is not None:
            payload["seed"] = seed

        # Add LoRA if configured
        lora_path = self.image_config.get("lora", {}).get("model_path", "")
        if lora_path:
            lora_strength = self.image_config["lora"].get("strength", 0.8)
            payload["loras"] = [{"path": lora_path, "scale": lora_strength}]

        try:
            # Submit to queue
            resp = requests.post(
                self.FAL_FLUX_PRO_URL,
                headers=self._fal_headers(),
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            result = resp.json()

            # FAL returns either direct result or queue status
            image_url = self._extract_image_url(result)
            if not image_url:
                # Poll for result
                request_id = result.get("request_id")
                if request_id:
                    image_url = self._poll_result(request_id, "fal-ai/flux-pro/v1.1-ultra")

            if image_url:
                return self._download_and_save(image_url, "flux_pro")

            logger.error("No image URL in Flux Pro response")
            return None

        except requests.exceptions.Timeout:
            logger.error("FAL.ai API timeout")
            return None
        except requests.exceptions.HTTPError as e:
            logger.error("FAL.ai HTTP error: %s — %s", e, e.response.text if e.response else "")
            return None
        except Exception as e:
            logger.error("Image generation failed: %s", e)
            return None

    def generate_kontext(
        self,
        prompt: str,
        reference_image_url: str,
        aspect_ratio: str = "3:4",
    ) -> str | None:
        """Generate a character-consistent image using Flux Kontext.

        Uses a reference image to maintain character identity across scenes.

        Args:
            prompt: Scene/pose description.
            reference_image_url: URL of reference image for consistency.
            aspect_ratio: Output aspect ratio.

        Returns:
            Path to saved image file, or None on failure.
        """
        if not self.enabled:
            logger.warning("FAL_API_KEY not set — skipping Kontext generation")
            return None

        payload = {
            "prompt": prompt,
            "image_url": reference_image_url,
            "aspect_ratio": aspect_ratio,
            "output_format": "jpeg",
        }

        try:
            resp = requests.post(
                self.FAL_FLUX_KONTEXT_URL,
                headers=self._fal_headers(),
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            result = resp.json()

            image_url = self._extract_image_url(result)
            if not image_url:
                request_id = result.get("request_id")
                if request_id:
                    image_url = self._poll_result(request_id, "fal-ai/flux-pro/kontext")

            if image_url:
                return self._download_and_save(image_url, "kontext")

            logger.error("No image URL in Kontext response")
            return None

        except Exception as e:
            logger.error("Kontext generation failed: %s", e)
            return None

    def _extract_image_url(self, result: dict) -> str | None:
        """Extract image URL from FAL.ai response."""
        # Direct result format
        images = result.get("images", [])
        if images:
            return images[0].get("url")
        # Single image format
        image = result.get("image")
        if isinstance(image, dict):
            return image.get("url")
        if isinstance(image, str):
            return image
        return None

    def _poll_result(self, request_id: str, model_path: str, max_wait: int = 120) -> str | None:
        """Poll FAL.ai queue for result."""
        status_url = f"https://queue.fal.run/{model_path}/requests/{request_id}/status"
        result_url = f"https://queue.fal.run/{model_path}/requests/{request_id}"

        start = time.time()
        while time.time() - start < max_wait:
            try:
                resp = requests.get(status_url, headers=self._fal_headers(), timeout=10)
                resp.raise_for_status()
                status = resp.json()

                if status.get("status") == "COMPLETED":
                    resp = requests.get(result_url, headers=self._fal_headers(), timeout=10)
                    resp.raise_for_status()
                    return self._extract_image_url(resp.json())
                elif status.get("status") == "FAILED":
                    logger.error("FAL.ai request failed: %s", status.get("error"))
                    return None

                time.sleep(2)
            except Exception as e:
                logger.warning("Poll error: %s", e)
                time.sleep(3)

        logger.error("FAL.ai polling timed out after %ds", max_wait)
        return None

    def _download_and_save(self, url: str, prefix: str) -> str | None:
        """Download image from URL and save locally."""
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()

            now = datetime.now(JST)
            filename = f"{prefix}_{now.strftime('%Y%m%d_%H%M%S')}_{random.randint(1000,9999)}.jpg"
            filepath = IMAGE_DIR / filename
            filepath.write_bytes(resp.content)
            logger.info("Image saved: %s (%d bytes)", filepath, len(resp.content))
            return str(filepath)

        except Exception as e:
            logger.error("Image download failed: %s", e)
            return None

    def generate_for_scene(
        self,
        scene: str,
        extra_prompt: str = "",
        aspect_ratio: str = "3:4",
        reference_image_url: str | None = None,
    ) -> str | None:
        """Generate a character image for a specific scene.

        This is the main entry point for content generation.

        Args:
            scene: Scene category from character_config.yaml.
            extra_prompt: Additional prompt elements.
            aspect_ratio: Output aspect ratio.
            reference_image_url: If provided, uses Kontext for consistency.

        Returns:
            Path to saved image file, or None on failure.
        """
        prompt = self._build_character_prompt(scene, extra_prompt)
        logger.info("Generating scene=%s, prompt=%s", scene, prompt[:100])

        if reference_image_url:
            return self.generate_kontext(prompt, reference_image_url, aspect_ratio)
        return self.generate_flux_pro(prompt, aspect_ratio)

    def generate_batch(
        self,
        scenes: list[dict],
        reference_image_url: str | None = None,
    ) -> list[dict]:
        """Generate a batch of images for multiple scenes.

        Args:
            scenes: List of dicts with 'scene', 'extra_prompt', 'aspect_ratio'.
            reference_image_url: Reference image for Kontext consistency.

        Returns:
            List of dicts with generation results.
        """
        results = []
        for i, scene_spec in enumerate(scenes):
            scene = scene_spec.get("scene", "lifestyle")
            extra = scene_spec.get("extra_prompt", "")
            ratio = scene_spec.get("aspect_ratio", "3:4")

            logger.info("Batch %d/%d: scene=%s", i + 1, len(scenes), scene)
            image_path = self.generate_for_scene(
                scene, extra, ratio, reference_image_url
            )

            results.append({
                "scene": scene,
                "image_path": image_path,
                "success": image_path is not None,
                "timestamp": datetime.now(JST).isoformat(),
            })

            # Rate limiting between generations
            if i < len(scenes) - 1:
                time.sleep(1)

        # Save batch results
        now = datetime.now(JST)
        batch_file = GENERATED_DIR / f"batch_{now.strftime('%Y%m%d_%H%M%S')}.json"
        batch_file.write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        success_count = sum(1 for r in results if r["success"])
        logger.info("Batch complete: %d/%d succeeded", success_count, len(results))
        return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    pipeline = ImagePipeline()
    if pipeline.enabled:
        result = pipeline.generate_for_scene("morning_routine")
        print(f"Generated: {result}")
    else:
        print("FAL_API_KEY not set. Set it to generate images.")
