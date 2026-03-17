"""System E — AI Character Image Generation Pipeline.

Generates character-consistent images using RunPod Serverless (primary)
or FAL.ai (fallback). Supports Flux.1 Dev with LoRA for identity preservation.
"""

from __future__ import annotations

import base64
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
SYSTEM_CONFIG_PATH = Path(__file__).parent.parent / "config" / "config.yaml"
IMAGE_DIR = Path(__file__).parent.parent / "data" / "system_e" / "images"
GENERATED_DIR = Path(__file__).parent.parent / "data" / "system_e" / "generated"


def load_character_config() -> dict:
    """Load character configuration from YAML."""
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_system_config() -> dict:
    """Load system configuration from YAML."""
    with open(SYSTEM_CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _resolve_aspect_ratio(aspect_ratio: str, defaults: dict) -> tuple[int, int]:
    """Convert aspect ratio string to width/height using config defaults."""
    base = defaults.get("width", 1024)
    ratio_map = {
        "3:4": (base, int(base * 4 / 3)),
        "4:3": (int(base * 4 / 3), base),
        "16:9": (int(base * 16 / 9), base),
        "9:16": (base, int(base * 16 / 9)),
        "1:1": (base, base),
    }
    return ratio_map.get(aspect_ratio, (base, base))


class RunPodBackend:
    """Image generation via RunPod Serverless (Flux.1 Dev + LoRA)."""

    def __init__(self, endpoint_id: str, api_key: str, image_config: dict):
        self.endpoint_id = endpoint_id
        self.api_key = api_key
        self.image_config = image_config
        self.base_url = f"https://api.runpod.ai/v2/{endpoint_id}"

    @property
    def enabled(self) -> bool:
        return bool(self.api_key and self.endpoint_id)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _build_workflow(
        self,
        prompt: str,
        width: int,
        height: int,
        steps: int,
        seed: int,
    ) -> dict:
        """Build a ComfyUI API workflow JSON for Flux.1 Dev fp8.

        Flux.1 Dev requires cfg=1.0 with KSampler (guidance is baked into the model).
        """
        return {
            "4": {
                "inputs": {"ckpt_name": "flux1-dev-fp8.safetensors"},
                "class_type": "CheckpointLoaderSimple",
                "_meta": {"title": "Load Checkpoint"},
            },
            "5": {
                "inputs": {
                    "width": width,
                    "height": height,
                    "batch_size": 1,
                },
                "class_type": "EmptyLatentImage",
                "_meta": {"title": "Empty Latent Image"},
            },
            "6": {
                "inputs": {"text": prompt, "clip": ["4", 1]},
                "class_type": "CLIPTextEncode",
                "_meta": {"title": "CLIP Text Encode (Prompt)"},
            },
            "7": {
                "inputs": {"text": "", "clip": ["4", 1]},
                "class_type": "CLIPTextEncode",
                "_meta": {"title": "CLIP Text Encode (Negative)"},
            },
            "3": {
                "inputs": {
                    "seed": seed,
                    "steps": steps,
                    "cfg": 1.0,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1,
                    "model": ["4", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["5", 0],
                },
                "class_type": "KSampler",
                "_meta": {"title": "KSampler"},
            },
            "8": {
                "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
                "class_type": "VAEDecode",
                "_meta": {"title": "VAE Decode"},
            },
            "9": {
                "inputs": {
                    "filename_prefix": "ComfyUI",
                    "images": ["8", 0],
                },
                "class_type": "SaveImage",
                "_meta": {"title": "Save Image"},
            },
        }

    def generate(
        self,
        prompt: str,
        aspect_ratio: str = "3:4",
        seed: int | None = None,
        reference_image_url: str | None = None,
    ) -> dict | None:
        """Submit a generation job to RunPod Serverless (ComfyUI workflow).

        Returns the result dict with image data, or None on failure.
        """
        defaults = self.image_config.get("defaults", {})
        width, height = _resolve_aspect_ratio(aspect_ratio, defaults)
        steps = defaults.get("num_inference_steps", 28)

        if seed is None:
            seed = random.randint(0, 2**32 - 1)

        workflow = self._build_workflow(prompt, width, height, steps, seed)
        payload = {"input": {"workflow": workflow}}

        try:
            # Submit job via /run (async)
            resp = requests.post(
                f"{self.base_url}/run",
                headers=self._headers(),
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            job = resp.json()
            job_id = job.get("id")

            if not job_id:
                logger.error("RunPod: no job ID in response: %s", job)
                return None

            logger.info("RunPod job submitted: %s", job_id)

            # If status is already COMPLETED (fast execution)
            if job.get("status") == "COMPLETED":
                return job.get("output")

            # Poll for result
            return self._poll_job(job_id)

        except requests.exceptions.Timeout:
            logger.error("RunPod API timeout on submit")
            return None
        except requests.exceptions.HTTPError as e:
            logger.error(
                "RunPod HTTP error: %s — %s",
                e,
                e.response.text if e.response else "",
            )
            return None
        except Exception as e:
            logger.error("RunPod generation failed: %s", e)
            return None

    def _poll_job(self, job_id: str, max_wait: int = 180) -> dict | None:
        """Poll RunPod for job completion."""
        url = f"{self.base_url}/status/{job_id}"
        start = time.time()

        while time.time() - start < max_wait:
            try:
                resp = requests.get(url, headers=self._headers(), timeout=10)
                resp.raise_for_status()
                data = resp.json()
                status = data.get("status")

                if status == "COMPLETED":
                    logger.info("RunPod job %s completed", job_id)
                    return data.get("output")
                elif status in ("FAILED", "CANCELLED", "TIMED_OUT"):
                    logger.error(
                        "RunPod job %s %s: %s",
                        job_id,
                        status,
                        data.get("error", "unknown"),
                    )
                    return None

                # IN_QUEUE or IN_PROGRESS — wait and retry
                time.sleep(3)
            except Exception as e:
                logger.warning("RunPod poll error: %s", e)
                time.sleep(5)

        logger.error("RunPod job %s timed out after %ds", job_id, max_wait)
        return None


class FalBackend:
    """Image generation via FAL.ai (Flux Pro / Kontext)."""

    FAL_FLUX_PRO_URL = "https://queue.fal.run/fal-ai/flux-pro/v1.1-ultra"
    FAL_FLUX_KONTEXT_URL = "https://queue.fal.run/fal-ai/flux-pro/kontext"

    def __init__(self, api_key: str, image_config: dict):
        self.api_key = api_key
        self.image_config = image_config

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Key {self.api_key}",
            "Content-Type": "application/json",
        }

    def generate(
        self,
        prompt: str,
        aspect_ratio: str = "3:4",
        seed: int | None = None,
        reference_image_url: str | None = None,
    ) -> dict | None:
        """Generate image via FAL.ai. Returns dict with image URL."""
        if reference_image_url:
            return self._generate_kontext(prompt, reference_image_url, aspect_ratio)
        return self._generate_flux_pro(prompt, aspect_ratio, seed)

    def _generate_flux_pro(
        self, prompt: str, aspect_ratio: str, seed: int | None
    ) -> dict | None:
        payload = {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "output_format": "jpeg",
            "safety_tolerance": "2",
        }
        if seed is not None:
            payload["seed"] = seed

        lora_path = self.image_config.get("lora", {}).get("model_path", "")
        if lora_path:
            lora_strength = self.image_config["lora"].get("strength", 0.8)
            payload["loras"] = [{"path": lora_path, "scale": lora_strength}]

        try:
            resp = requests.post(
                self.FAL_FLUX_PRO_URL,
                headers=self._headers(),
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            result = resp.json()

            image_url = self._extract_image_url(result)
            if not image_url:
                request_id = result.get("request_id")
                if request_id:
                    image_url = self._poll_result(
                        request_id, "fal-ai/flux-pro/v1.1-ultra"
                    )

            if image_url:
                return {"image_url": image_url}

            logger.error("No image URL in Flux Pro response")
            return None
        except Exception as e:
            logger.error("FAL.ai Flux Pro failed: %s", e)
            return None

    def _generate_kontext(
        self, prompt: str, reference_image_url: str, aspect_ratio: str
    ) -> dict | None:
        payload = {
            "prompt": prompt,
            "image_url": reference_image_url,
            "aspect_ratio": aspect_ratio,
            "output_format": "jpeg",
        }

        try:
            resp = requests.post(
                self.FAL_FLUX_KONTEXT_URL,
                headers=self._headers(),
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            result = resp.json()

            image_url = self._extract_image_url(result)
            if not image_url:
                request_id = result.get("request_id")
                if request_id:
                    image_url = self._poll_result(
                        request_id, "fal-ai/flux-pro/kontext"
                    )

            if image_url:
                return {"image_url": image_url}

            logger.error("No image URL in Kontext response")
            return None
        except Exception as e:
            logger.error("FAL.ai Kontext failed: %s", e)
            return None

    def _extract_image_url(self, result: dict) -> str | None:
        images = result.get("images", [])
        if images:
            return images[0].get("url")
        image = result.get("image")
        if isinstance(image, dict):
            return image.get("url")
        if isinstance(image, str):
            return image
        return None

    def _poll_result(
        self, request_id: str, model_path: str, max_wait: int = 120
    ) -> str | None:
        status_url = (
            f"https://queue.fal.run/{model_path}/requests/{request_id}/status"
        )
        result_url = f"https://queue.fal.run/{model_path}/requests/{request_id}"

        start = time.time()
        while time.time() - start < max_wait:
            try:
                resp = requests.get(
                    status_url, headers=self._headers(), timeout=10
                )
                resp.raise_for_status()
                status = resp.json()

                if status.get("status") == "COMPLETED":
                    resp = requests.get(
                        result_url, headers=self._headers(), timeout=10
                    )
                    resp.raise_for_status()
                    return self._extract_image_url(resp.json())
                elif status.get("status") == "FAILED":
                    logger.error(
                        "FAL.ai request failed: %s", status.get("error")
                    )
                    return None

                time.sleep(2)
            except Exception as e:
                logger.warning("FAL.ai poll error: %s", e)
                time.sleep(3)

        logger.error("FAL.ai polling timed out after %ds", max_wait)
        return None


class ImagePipeline:
    """Generate character-consistent images via RunPod (primary) or FAL.ai (fallback).

    Backend is selected via config.yaml system_e.image_provider:
      - "runpod" (default): RunPod Serverless with Flux.1 Dev + LoRA
      - "fal_ai": FAL.ai with Flux Pro
    """

    def __init__(self):
        self.config = load_character_config()
        self.system_config = load_system_config()
        self.character = self.config["character"]
        self.image_config = self.config["image_generation"]
        self.provider = self.system_config.get("system_e", {}).get(
            "image_provider", "runpod"
        )

        # Initialize backends
        self._runpod = RunPodBackend(
            endpoint_id=os.getenv("RUNPOD_ENDPOINT_ID", ""),
            api_key=os.getenv("RUNPOD_API_KEY", ""),
            image_config=self.image_config,
        )
        self._fal = FalBackend(
            api_key=os.getenv("FAL_API_KEY", ""),
            image_config=self.image_config,
        )

        IMAGE_DIR.mkdir(parents=True, exist_ok=True)
        GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    @property
    def enabled(self) -> bool:
        if self.provider == "runpod":
            return self._runpod.enabled
        return self._fal.enabled

    @property
    def _backend(self):
        if self.provider == "runpod":
            return self._runpod
        return self._fal

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

    def _save_from_result(self, result: dict, prefix: str) -> str | None:
        """Save image from backend result to local file.

        Handles both URL-based (FAL.ai) and base64-based (RunPod) responses.
        """
        try:
            now = datetime.now(JST)
            filename = f"{prefix}_{now.strftime('%Y%m%d_%H%M%S')}_{random.randint(1000, 9999)}.jpg"
            filepath = IMAGE_DIR / filename

            # URL-based result (FAL.ai or RunPod with URL output)
            image_url = result.get("image_url") or result.get("url")
            if image_url:
                resp = requests.get(image_url, timeout=30)
                resp.raise_for_status()
                filepath.write_bytes(resp.content)
                logger.info("Image saved: %s (%d bytes)", filepath, len(resp.content))
                return str(filepath)

            # Base64-based result (RunPod)
            image_b64 = result.get("image_base64") or result.get("image")
            if image_b64 and isinstance(image_b64, str) and len(image_b64) > 200:
                image_bytes = base64.b64decode(image_b64)
                filepath.write_bytes(image_bytes)
                logger.info("Image saved: %s (%d bytes)", filepath, len(image_bytes))
                return str(filepath)

            # Images array (ComfyUI worker v5+ output)
            # Format: [{"type": "base64", "data": "..."}, ...] or
            #         [{"type": "s3_url", "data": "https://..."}, ...]
            images = result.get("images", [])
            if images:
                first = images[0]
                if isinstance(first, dict):
                    # ComfyUI worker format
                    img_type = first.get("type", "")
                    img_data = first.get("data", "")
                    if img_type == "base64" and img_data:
                        return self._save_from_result({"image_base64": img_data}, prefix)
                    if img_type == "s3_url" and img_data:
                        return self._save_from_result({"image_url": img_data}, prefix)
                    # Fallback: try nested recursion
                    return self._save_from_result(first, prefix)
                if isinstance(first, str):
                    if first.startswith("http"):
                        return self._save_from_result({"image_url": first}, prefix)
                    return self._save_from_result({"image_base64": first}, prefix)

            logger.error("No image data in result: %s", list(result.keys()))
            return None
        except Exception as e:
            logger.error("Image save failed: %s", e)
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
            reference_image_url: If provided, uses IP-Adapter/Kontext for consistency.

        Returns:
            Path to saved image file, or None on failure.
        """
        prompt = self._build_character_prompt(scene, extra_prompt)
        logger.info(
            "Generating scene=%s provider=%s prompt=%s",
            scene,
            self.provider,
            prompt[:100],
        )

        result = self._backend.generate(
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            reference_image_url=reference_image_url,
        )

        if result:
            prefix = f"{self.provider}_{scene}"
            return self._save_from_result(result, prefix)

        logger.error("Image generation returned no result (provider=%s)", self.provider)
        return None

    def generate_batch(
        self,
        scenes: list[dict],
        reference_image_url: str | None = None,
    ) -> list[dict]:
        """Generate a batch of images for multiple scenes.

        Args:
            scenes: List of dicts with 'scene', 'extra_prompt', 'aspect_ratio'.
            reference_image_url: Reference image for character consistency.

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
                "provider": self.provider,
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
        print(f"Provider: {pipeline.provider}")
        result = pipeline.generate_for_scene("morning_routine")
        print(f"Generated: {result}")
    else:
        print(
            "Image pipeline not configured.\n"
            "  RunPod: set RUNPOD_API_KEY + RUNPOD_ENDPOINT_ID\n"
            "  FAL.ai: set FAL_API_KEY"
        )
