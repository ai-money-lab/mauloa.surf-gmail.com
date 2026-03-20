"""System E — AI Character Video Generation Pipeline.

Generates short-form and long-form video content for maximum CPM and engagement.
Uses image-to-video AI models (Runway Gen-3, Kling, Minimax) with the existing
image pipeline as the source frame generator.

Video CPM hierarchy (why video wins):
  - YouTube long-form:  $10-30 CPM
  - YouTube Shorts:     $3-8 CPM
  - TikTok:             $2-5 CPM
  - Instagram Reels:    $2-6 CPM
  - X Video:            $1-3 CPM
  - Static image post:  $0.5-1.5 CPM

Revenue strategy:
  1. Generate character-consistent source frames via image_pipeline
  2. Animate frames with image-to-video models
  3. Add voiceover via TTS (ElevenLabs/Fish Audio)
  4. Distribute across platforms with platform-specific edits
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
VIDEO_DIR = Path(__file__).parent.parent / "data" / "system_e" / "videos"
SCRIPTS_DIR = Path(__file__).parent.parent / "data" / "system_e" / "video_scripts"


class VideoFormat(Enum):
    """Platform-optimized video formats."""

    SHORT_VERTICAL = "short_vertical"  # 9:16, 15-60s (Shorts/Reels/TikTok)
    SHORT_HORIZONTAL = "short_horizontal"  # 16:9, 15-60s (X/YouTube clips)
    LONG_HORIZONTAL = "long_horizontal"  # 16:9, 2-15min (YouTube)
    STORY = "story"  # 9:16, 15s (IG/X Stories)
    FANVUE = "fanvue"  # 9:16, 30-120s (Fanvue exclusive)


# Platform specs for video encoding
PLATFORM_SPECS = {
    VideoFormat.SHORT_VERTICAL: {
        "width": 1080,
        "height": 1920,
        "aspect": "9:16",
        "max_duration_s": 60,
        "min_duration_s": 15,
        "fps": 30,
        "platforms": ["youtube_shorts", "tiktok", "reels"],
    },
    VideoFormat.SHORT_HORIZONTAL: {
        "width": 1920,
        "height": 1080,
        "aspect": "16:9",
        "max_duration_s": 60,
        "min_duration_s": 15,
        "fps": 30,
        "platforms": ["x", "youtube_clip"],
    },
    VideoFormat.LONG_HORIZONTAL: {
        "width": 1920,
        "height": 1080,
        "aspect": "16:9",
        "max_duration_s": 900,
        "min_duration_s": 120,
        "fps": 30,
        "platforms": ["youtube"],
    },
    VideoFormat.STORY: {
        "width": 1080,
        "height": 1920,
        "aspect": "9:16",
        "max_duration_s": 15,
        "min_duration_s": 5,
        "fps": 30,
        "platforms": ["instagram_story", "x_story"],
    },
    VideoFormat.FANVUE: {
        "width": 1080,
        "height": 1920,
        "aspect": "9:16",
        "max_duration_s": 120,
        "min_duration_s": 30,
        "fps": 30,
        "platforms": ["fanvue"],
    },
}


# ─── Video Generation Backends ───


class RunwayBackend:
    """Image-to-video via Runway Gen-3 Alpha Turbo API.

    Best quality for character animation. ~$0.25/5s clip.
    """

    BASE_URL = "https://api.dev.runwayml.com/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Runway-Version": "2024-11-06",
        }

    def generate(
        self,
        image_url: str,
        prompt: str,
        duration_s: int = 5,
        aspect_ratio: str = "9:16",
    ) -> dict | None:
        """Generate video from image + motion prompt.

        Args:
            image_url: URL of source frame image.
            prompt: Motion/action description.
            duration_s: Duration in seconds (5 or 10).
            aspect_ratio: Output aspect ratio.

        Returns:
            Dict with video URL, or None on failure.
        """
        payload = {
            "promptImage": image_url,
            "promptText": prompt,
            "model": "gen3a_turbo",
            "duration": min(10, max(5, duration_s)),
            "ratio": aspect_ratio.replace(":", ":"),
        }

        try:
            resp = requests.post(
                f"{self.BASE_URL}/image_to_video",
                headers=self._headers(),
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            task = resp.json()
            task_id = task.get("id")

            if not task_id:
                logger.error("Runway: no task ID in response: %s", task)
                return None

            logger.info("Runway task submitted: %s", task_id)
            return self._poll_task(task_id)

        except requests.exceptions.HTTPError as e:
            logger.error(
                "Runway HTTP error: %s — %s", e, e.response.text if e.response else ""
            )
            return None
        except Exception as e:
            logger.error("Runway generation failed: %s", e)
            return None

    def _poll_task(self, task_id: str, max_wait: int = 300) -> dict | None:
        """Poll Runway for task completion."""
        url = f"{self.BASE_URL}/tasks/{task_id}"
        start = time.time()

        while time.time() - start < max_wait:
            try:
                resp = requests.get(url, headers=self._headers(), timeout=10)
                resp.raise_for_status()
                data = resp.json()
                status = data.get("status")

                if status == "SUCCEEDED":
                    output = data.get("output", [])
                    if output:
                        logger.info("Runway task %s completed", task_id)
                        return {"video_url": output[0]}
                    return None
                elif status in ("FAILED", "CANCELLED"):
                    logger.error(
                        "Runway task %s %s: %s", task_id, status, data.get("failure")
                    )
                    return None

                time.sleep(5)
            except Exception as e:
                logger.warning("Runway poll error: %s", e)
                time.sleep(5)

        logger.error("Runway task %s timed out after %ds", task_id, max_wait)
        return None


class KlingBackend:
    """Image-to-video via Kling AI API.

    Good quality, cheaper than Runway. ~$0.10/5s clip.
    """

    BASE_URL = "https://api.klingai.com/v1"

    def __init__(self, access_key: str, secret_key: str):
        self.access_key = access_key
        self.secret_key = secret_key

    @property
    def enabled(self) -> bool:
        return bool(self.access_key and self.secret_key)

    def _get_token(self) -> str | None:
        """Generate JWT token locally for Kling API authentication."""
        import jwt

        now = int(time.time())
        payload = {
            "iss": self.access_key,
            "exp": now + 1800,
            "nbf": now - 5,
        }
        try:
            return jwt.encode(payload, self.secret_key, algorithm="HS256")
        except Exception as e:
            logger.error("Kling JWT generation failed: %s", e)
            return None

    def _headers(self, token: str) -> dict:
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _resolve_image(image_input: str) -> str:
        """Accept URL, file path, or base64. Returns URL or raw base64 string."""
        if image_input.startswith(("http://", "https://")):
            return image_input
        # Strip data URI prefix if already provided
        if image_input.startswith("data:"):
            return image_input.split(",", 1)[-1]
        # Local file path → raw base64 string
        import base64

        path = Path(image_input)
        if path.is_file():
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode()
        return image_input  # assume URL if not a file

    def generate(
        self,
        image_url: str,
        prompt: str,
        duration_s: int = 5,
        aspect_ratio: str = "9:16",
    ) -> dict | None:
        """Generate video from image via Kling.

        Args:
            image_url: Public URL, local file path, or base64 data URI.
            prompt: Motion/scene description.
            duration_s: 5 or 10 seconds.
            aspect_ratio: e.g. "9:16", "16:9", "1:1".
        """
        token = self._get_token()
        if not token:
            return None

        image = self._resolve_image(image_url)
        payload = {
            "model_name": "kling-v1",
            "image": image,
            "prompt": prompt,
            "duration": str(min(10, max(5, duration_s))),
            "aspect_ratio": aspect_ratio,
            "mode": "std",  # std=free tier friendly, pro=higher quality
        }

        try:
            resp = requests.post(
                f"{self.BASE_URL}/videos/image2video",
                headers=self._headers(token),
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
            task_id = data.get("task_id")

            if not task_id:
                logger.error("Kling: no task_id: %s", data)
                return None

            logger.info("Kling task submitted: %s", task_id)
            return self._poll_task(task_id, token)

        except requests.HTTPError as e:
            body = ""
            if e.response is not None:
                body = e.response.text[:500]
            logger.error("Kling generation failed: %s — %s", e, body)
            return None
        except Exception as e:
            logger.error("Kling generation failed: %s", e)
            return None

    def _poll_task(self, task_id: str, token: str, max_wait: int = 300) -> dict | None:
        """Poll Kling for task completion."""
        url = f"{self.BASE_URL}/videos/image2video/{task_id}"
        start = time.time()

        while time.time() - start < max_wait:
            try:
                resp = requests.get(url, headers=self._headers(token), timeout=10)
                resp.raise_for_status()
                data = resp.json().get("data", {})
                status = data.get("task_status")

                if status == "succeed":
                    videos = data.get("task_result", {}).get("videos", [])
                    if videos:
                        logger.info("Kling task %s completed", task_id)
                        return {"video_url": videos[0].get("url")}
                    return None
                elif status == "failed":
                    logger.error(
                        "Kling task %s failed: %s", task_id, data.get("task_status_msg")
                    )
                    return None

                time.sleep(5)
            except Exception as e:
                logger.warning("Kling poll error: %s", e)
                time.sleep(5)

        logger.error("Kling task %s timed out", task_id)
        return None


class MinimaxBackend:
    """Image-to-video via Minimax (Hailuo) API.

    Budget option, decent quality. ~$0.05/5s clip.
    """

    BASE_URL = "https://api.minimaxi.chat/v1"

    def __init__(self, api_key: str, group_id: str):
        self.api_key = api_key
        self.group_id = group_id

    @property
    def enabled(self) -> bool:
        return bool(self.api_key and self.group_id)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def generate(
        self,
        image_url: str,
        prompt: str,
        duration_s: int = 5,
        aspect_ratio: str = "9:16",
    ) -> dict | None:
        """Generate video from image via Minimax."""
        payload = {
            "model": "video-01",
            "first_frame_image": image_url,
            "prompt": prompt,
        }

        try:
            resp = requests.post(
                f"{self.BASE_URL}/video_generation?GroupId={self.group_id}",
                headers=self._headers(),
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            task_id = resp.json().get("task_id")

            if not task_id:
                logger.error("Minimax: no task_id")
                return None

            logger.info("Minimax task submitted: %s", task_id)
            return self._poll_task(task_id)

        except Exception as e:
            logger.error("Minimax generation failed: %s", e)
            return None

    def _poll_task(self, task_id: str, max_wait: int = 300) -> dict | None:
        """Poll Minimax for task completion."""
        url = (
            f"{self.BASE_URL}/query/video_generation"
            f"?GroupId={self.group_id}&task_id={task_id}"
        )
        start = time.time()

        while time.time() - start < max_wait:
            try:
                resp = requests.get(url, headers=self._headers(), timeout=10)
                resp.raise_for_status()
                data = resp.json()
                status = data.get("status")

                if status == "Success":
                    file_id = data.get("file_id")
                    if file_id:
                        video_url = self._get_download_url(file_id)
                        if video_url:
                            logger.info("Minimax task %s completed", task_id)
                            return {"video_url": video_url}
                    return None
                elif status == "Failed":
                    logger.error("Minimax task %s failed", task_id)
                    return None

                time.sleep(5)
            except Exception as e:
                logger.warning("Minimax poll error: %s", e)
                time.sleep(5)

        logger.error("Minimax task %s timed out", task_id)
        return None

    def _get_download_url(self, file_id: str) -> str | None:
        """Get download URL for completed video."""
        try:
            resp = requests.get(
                f"{self.BASE_URL}/files/retrieve"
                f"?GroupId={self.group_id}&file_id={file_id}",
                headers=self._headers(),
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json().get("file", {}).get("download_url")
        except Exception as e:
            logger.error("Minimax download URL failed: %s", e)
            return None


# ─── TTS Backend ───


class EdgeTTS:
    """Text-to-speech via Microsoft Edge TTS — completely free, no API key.

    Uses the edge-tts Python package (pip install edge-tts).
    Quality is surprisingly good for free. Supports multiple voices and languages.

    Riena voice: en-US-AnaNeural (young female, warm, natural)
    Japanese fallback: ja-JP-NanamiNeural
    """

    # Best free voices for Riena's character
    VOICE_EN = "en-US-AnaNeural"  # Young female, warm, natural
    VOICE_JA = "ja-JP-NanamiNeural"  # Japanese content
    VOICE_ALTERNATIVES = [
        "en-US-AriaNeural",  # Slightly more mature
        "en-US-JennyNeural",  # Professional, clear
        "en-GB-SoniaNeural",  # British accent option
    ]

    def __init__(self, voice: str = ""):
        self.voice = voice or self.VOICE_EN

    @property
    def enabled(self) -> bool:
        try:
            import edge_tts  # noqa: F401

            return True
        except ImportError:
            return False

    def synthesize(self, text: str, output_path: Path) -> bool:
        """Generate speech audio file using Edge TTS (free).

        Args:
            text: Text to speak.
            output_path: Path to save MP3 file.

        Returns:
            True if successful.
        """
        try:
            import asyncio

            import edge_tts

            async def _generate():
                communicate = edge_tts.Communicate(text, self.voice)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                await communicate.save(str(output_path))

            # Run async in sync context
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                # Already in async context — use nest_asyncio or thread
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    pool.submit(lambda: asyncio.run(_generate())).result(timeout=30)
            else:
                asyncio.run(_generate())

            logger.info(
                "Edge TTS audio saved: %s (%d bytes)",
                output_path,
                output_path.stat().st_size,
            )
            return True
        except ImportError:
            logger.error("edge-tts not installed. Run: pip install edge-tts")
            return False
        except Exception as e:
            logger.error("Edge TTS failed: %s", e)
            return False


class ElevenLabsTTS:
    """Text-to-speech via ElevenLabs for voiceover (paid, higher quality).

    Riena's voice: young female, warm, slightly nerdy, English with
    subtle Japanese accent.
    """

    BASE_URL = "https://api.elevenlabs.io/v1"

    def __init__(self, api_key: str, voice_id: str):
        self.api_key = api_key
        self.voice_id = voice_id

    @property
    def enabled(self) -> bool:
        return bool(self.api_key and self.voice_id)

    def _headers(self) -> dict:
        return {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
        }

    def synthesize(self, text: str, output_path: Path) -> bool:
        """Generate speech audio file.

        Args:
            text: Text to speak.
            output_path: Path to save MP3 file.

        Returns:
            True if successful.
        """
        payload = {
            "text": text,
            "model_id": "eleven_turbo_v2_5",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.3,
            },
        }

        try:
            resp = requests.post(
                f"{self.BASE_URL}/text-to-speech/{self.voice_id}",
                headers=self._headers(),
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(resp.content)
            logger.info(
                "TTS audio saved: %s (%d bytes)", output_path, len(resp.content)
            )
            return True
        except Exception as e:
            logger.error("ElevenLabs TTS failed: %s", e)
            return False


# ─── Video Script Types ───


VIDEO_CONTENT_TEMPLATES = {
    # Short-form templates (15-60s)
    "morning_routine_short": {
        "format": VideoFormat.SHORT_VERTICAL,
        "scenes": [
            {"action": "waking up, stretching in bed", "duration_s": 5},
            {"action": "making matcha in kitchen, calm movements", "duration_s": 5},
            {"action": "sipping matcha by window, morning light", "duration_s": 5},
        ],
        "voiceover_template": (
            "My morning non-negotiable: matcha before anything else. "
            "{tip} Small steps, big changes."
        ),
        "cpm_range": [3, 8],
    },
    "workout_short": {
        "format": VideoFormat.SHORT_VERTICAL,
        "scenes": [
            {"action": "gym warm-up, dynamic stretching", "duration_s": 5},
            {"action": "main exercise, focused form, real sweat", "duration_s": 5},
            {"action": "post-workout stretch, satisfied expression", "duration_s": 5},
        ],
        "voiceover_template": (
            "Today's focus: {exercise}. Form over ego, always. {tip}"
        ),
        "cpm_range": [4, 10],
    },
    "wellness_tip_short": {
        "format": VideoFormat.SHORT_VERTICAL,
        "scenes": [
            {"action": "talking to camera, animated expression", "duration_s": 5},
            {"action": "demonstrating the tip, hands visible", "duration_s": 5},
            {"action": "smiling, nodding, warm close-up", "duration_s": 5},
        ],
        "voiceover_template": (
            "Okay so I've been geeking out over this: {topic}. "
            "{explanation} The data doesn't lie."
        ),
        "cpm_range": [3, 8],
    },
    "day_in_life_short": {
        "format": VideoFormat.SHORT_VERTICAL,
        "scenes": [
            {"action": "morning routine, getting ready", "duration_s": 5},
            {"action": "working at desk, laptop open, cat nearby", "duration_s": 5},
            {"action": "cooking healthy meal", "duration_s": 5},
            {"action": "evening wind-down, journaling", "duration_s": 5},
        ],
        "voiceover_template": (
            "A real day in my life — not the highlight reel. "
            "{honest_detail} Progress over perfection."
        ),
        "cpm_range": [5, 12],
    },
    # Fanvue exclusive (higher value)
    "behind_scenes_fanvue": {
        "format": VideoFormat.FANVUE,
        "scenes": [
            {"action": "casual apartment setting, talking naturally", "duration_s": 10},
            {"action": "showing something personal, close-up", "duration_s": 5},
            {"action": "candid moment, laughing or thoughtful", "duration_s": 5},
        ],
        "voiceover_template": (
            "Something I don't usually share... {personal_detail} "
            "You guys make me feel safe enough to be real."
        ),
        "cpm_range": [0, 0],  # Direct subscription revenue
    },
    # Story format (15s)
    "quick_update_story": {
        "format": VideoFormat.STORY,
        "scenes": [
            {"action": "selfie-style, casual, talking to camera", "duration_s": 5},
            {"action": "showing what she's doing, natural movement", "duration_s": 5},
            {"action": "wave or peace sign, warm smile", "duration_s": 5},
        ],
        "voiceover_template": "Currently: {activity}. How's your {time_of_day} going?",
        "cpm_range": [1, 3],
    },
}


# ─── Main Pipeline ───


class VideoPipeline:
    """Orchestrates end-to-end video content generation.

    Flow:
    1. Generate source frame(s) via ImagePipeline
    2. Create motion prompt for each scene
    3. Generate video clips via i2v backend (Runway/Kling/Minimax)
    4. Generate voiceover via TTS
    5. Return clips + audio for assembly (ffmpeg post-processing)
    """

    def __init__(self):
        self.video_provider = os.getenv("VIDEO_PROVIDER", "runway")

        # Initialize video generation backends
        self._runway = RunwayBackend(
            api_key=os.getenv("RUNWAY_API_KEY", ""),
        )
        self._kling = KlingBackend(
            access_key=os.getenv("KLING_ACCESS_KEY", ""),
            secret_key=os.getenv("KLING_SECRET_KEY", ""),
        )
        self._minimax = MinimaxBackend(
            api_key=os.getenv("MINIMAX_API_KEY", ""),
            group_id=os.getenv("MINIMAX_GROUP_ID", ""),
        )

        # TTS backends: ElevenLabs (paid, premium) → Edge-TTS (free, default)
        self._tts_elevenlabs = ElevenLabsTTS(
            api_key=os.getenv("ELEVENLABS_API_KEY", ""),
            voice_id=os.getenv("RIENA_VOICE_ID", ""),
        )
        self._tts_edge = EdgeTTS(
            voice=os.getenv("EDGE_TTS_VOICE", EdgeTTS.VOICE_EN),
        )
        # Auto-select: paid if configured, free otherwise
        self._tts = (
            self._tts_elevenlabs if self._tts_elevenlabs.enabled else self._tts_edge
        )

        VIDEO_DIR.mkdir(parents=True, exist_ok=True)
        SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

    @property
    def enabled(self) -> bool:
        return self._backend.enabled

    @property
    def _backend(self):
        if self.video_provider == "kling" and self._kling.enabled:
            return self._kling
        if self.video_provider == "minimax" and self._minimax.enabled:
            return self._minimax
        return self._runway

    def generate_video_clip(
        self,
        image_url: str,
        motion_prompt: str,
        duration_s: int = 5,
        aspect_ratio: str = "9:16",
    ) -> dict | None:
        """Generate a single video clip from a source image.

        Args:
            image_url: URL of the source frame.
            motion_prompt: Description of desired motion/animation.
            duration_s: Clip duration in seconds.
            aspect_ratio: Output aspect ratio.

        Returns:
            Dict with video_url, or None on failure.
        """
        backend = self._backend
        logger.info(
            "Generating video clip: provider=%s, duration=%ds, ratio=%s",
            self.video_provider,
            duration_s,
            aspect_ratio,
        )

        result = backend.generate(
            image_url=image_url,
            prompt=motion_prompt,
            duration_s=duration_s,
            aspect_ratio=aspect_ratio,
        )

        if result and result.get("video_url"):
            # Download and save locally
            local_path = self._download_video(result["video_url"])
            if local_path:
                result["local_path"] = str(local_path)
            return result

        # Fallback to next available backend
        fallback = self._get_fallback_backend()
        if fallback:
            logger.info("Falling back to %s", type(fallback).__name__)
            result = fallback.generate(
                image_url=image_url,
                prompt=motion_prompt,
                duration_s=duration_s,
                aspect_ratio=aspect_ratio,
            )
            if result and result.get("video_url"):
                local_path = self._download_video(result["video_url"])
                if local_path:
                    result["local_path"] = str(local_path)
                return result

        logger.error("All video backends failed")
        return None

    def generate_voiceover(self, text: str, clip_id: str) -> Path | None:
        """Generate voiceover audio for a video clip.

        Args:
            text: Voiceover text.
            clip_id: Identifier for the clip (used in filename).

        Returns:
            Path to audio file, or None.
        """
        if not self._tts.enabled:
            logger.warning(
                "TTS not configured. Install edge-tts (free): pip install edge-tts"
            )
            return None

        output_path = VIDEO_DIR / f"vo_{clip_id}.mp3"
        if self._tts.synthesize(text, output_path):
            return output_path
        return None

    def generate_from_template(
        self,
        template_name: str,
        image_urls: list[str],
        script_vars: dict | None = None,
    ) -> dict:
        """Generate a complete video from a template.

        This is the main entry point for video content generation.

        Args:
            template_name: Key from VIDEO_CONTENT_TEMPLATES.
            image_urls: Source frame URLs (one per scene).
            script_vars: Variables to fill in voiceover template.

        Returns:
            Dict with clips, voiceover_path, template info, and metadata.
        """
        template = VIDEO_CONTENT_TEMPLATES.get(template_name)
        if not template:
            return {"error": f"Unknown template: {template_name}"}

        fmt = template["format"]
        specs = PLATFORM_SPECS[fmt]
        scenes = template["scenes"]
        script_vars = script_vars or {}

        now = datetime.now(JST)
        job_id = f"{template_name}_{now.strftime('%Y%m%d_%H%M%S')}"

        logger.info(
            "Generating video: template=%s, scenes=%d, format=%s",
            template_name,
            len(scenes),
            fmt.value,
        )

        # Generate video clips for each scene
        clips = []
        for i, scene in enumerate(scenes):
            image_url = image_urls[i] if i < len(image_urls) else image_urls[-1]

            clip_result = self.generate_video_clip(
                image_url=image_url,
                motion_prompt=scene["action"],
                duration_s=scene["duration_s"],
                aspect_ratio=specs["aspect"],
            )

            clips.append(
                {
                    "scene_index": i,
                    "action": scene["action"],
                    "duration_s": scene["duration_s"],
                    "result": clip_result,
                    "success": clip_result is not None,
                }
            )

            # Rate limiting between clips
            if i < len(scenes) - 1:
                time.sleep(2)

        # Generate voiceover
        voiceover_text = template["voiceover_template"].format_map(
            _SafeFormatDict(script_vars)
        )
        voiceover_path = self.generate_voiceover(voiceover_text, job_id)

        # Save script/metadata
        result = {
            "job_id": job_id,
            "template": template_name,
            "format": fmt.value,
            "specs": specs,
            "clips": clips,
            "voiceover_text": voiceover_text,
            "voiceover_path": str(voiceover_path) if voiceover_path else None,
            "clips_succeeded": sum(1 for c in clips if c["success"]),
            "clips_total": len(clips),
            "platforms": specs["platforms"],
            "cpm_range": template["cpm_range"],
            "generated_at": now.isoformat(),
        }

        script_file = SCRIPTS_DIR / f"{job_id}.json"
        script_file.parent.mkdir(parents=True, exist_ok=True)
        script_file.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

        success_rate = result["clips_succeeded"] / max(1, result["clips_total"])
        logger.info(
            "Video generation complete: %s — %d/%d clips (%.0f%%)",
            job_id,
            result["clips_succeeded"],
            result["clips_total"],
            success_rate * 100,
        )

        return result

    def generate_daily_video_plan(self) -> list[dict]:
        """Generate a day's worth of video content.

        Optimal daily mix:
        - 2x short-form vertical (Shorts/Reels/TikTok)
        - 1x story
        - 1x Fanvue exclusive (if premium day)

        Returns:
            List of video generation results.
        """
        day = datetime.now(JST).day

        daily_templates = [
            # Morning short
            "morning_routine_short" if day % 3 == 0 else "wellness_tip_short",
            # Afternoon short
            "workout_short" if day % 2 == 0 else "day_in_life_short",
            # Story
            "quick_update_story",
        ]

        # Add Fanvue exclusive on premium days (every 3rd day)
        if day % 3 == 0:
            daily_templates.append("behind_scenes_fanvue")

        results = []
        for template_name in daily_templates:
            logger.info("Generating video: %s", template_name)
            # Note: image_urls would come from ImagePipeline in production
            # Here we return the plan for the orchestrator to fill in
            results.append(
                {
                    "template": template_name,
                    "format": VIDEO_CONTENT_TEMPLATES[template_name]["format"].value,
                    "platforms": PLATFORM_SPECS[
                        VIDEO_CONTENT_TEMPLATES[template_name]["format"]
                    ]["platforms"],
                    "scenes_needed": len(
                        VIDEO_CONTENT_TEMPLATES[template_name]["scenes"]
                    ),
                    "cpm_range": VIDEO_CONTENT_TEMPLATES[template_name]["cpm_range"],
                    "status": "planned",
                }
            )

        return results

    def estimate_daily_revenue(self, views_per_video: int = 1000) -> dict:
        """Estimate daily revenue from video content.

        Args:
            views_per_video: Average views per video.

        Returns:
            Revenue estimates by platform.
        """
        plan = self.generate_daily_video_plan()
        estimates = {}
        total_low = 0.0
        total_high = 0.0

        for item in plan:
            cpm_low, cpm_high = item["cpm_range"]
            if cpm_low == 0 and cpm_high == 0:
                # Fanvue — direct subscription revenue
                estimates[item["template"]] = {
                    "type": "subscription",
                    "note": "Drives Fanvue subscriptions (not ad CPM)",
                }
                continue

            rev_low = views_per_video * cpm_low / 1000
            rev_high = views_per_video * cpm_high / 1000
            total_low += rev_low
            total_high += rev_high

            estimates[item["template"]] = {
                "platforms": item["platforms"],
                "cpm_range": [cpm_low, cpm_high],
                "estimated_revenue": [round(rev_low, 2), round(rev_high, 2)],
            }

        return {
            "daily_videos": len(plan),
            "views_assumption": views_per_video,
            "daily_revenue_range": [round(total_low, 2), round(total_high, 2)],
            "monthly_revenue_range": [
                round(total_low * 30, 2),
                round(total_high * 30, 2),
            ],
            "breakdown": estimates,
        }

    # ─── Helpers ───

    def _download_video(self, url: str) -> Path | None:
        """Download video from URL to local storage."""
        try:
            resp = requests.get(url, timeout=60, stream=True)
            resp.raise_for_status()

            now = datetime.now(JST)
            filename = f"clip_{now.strftime('%Y%m%d_%H%M%S')}_{id(resp) % 10000}.mp4"
            filepath = VIDEO_DIR / filename

            with open(filepath, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.info("Video downloaded: %s", filepath)
            return filepath
        except Exception as e:
            logger.error("Video download failed: %s", e)
            return None

    def _get_fallback_backend(self):
        """Get the next available backend as fallback."""
        backends = [
            ("runway", self._runway),
            ("kling", self._kling),
            ("minimax", self._minimax),
        ]
        for name, backend in backends:
            if name != self.video_provider and backend.enabled:
                return backend
        return None


class _SafeFormatDict(dict):
    """Dict that returns placeholder for missing keys in str.format_map."""

    def __missing__(self, key: str) -> str:
        return f"[{key}]"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    pipeline = VideoPipeline()

    print("=== Daily Video Plan ===")
    plan = pipeline.generate_daily_video_plan()
    for item in plan:
        print(f"  {item['template']}: {item['format']} → {item['platforms']}")

    print("\n=== Revenue Estimate (1K views/video) ===")
    est = pipeline.estimate_daily_revenue(views_per_video=1000)
    print(
        f"  Daily:   ${est['daily_revenue_range'][0]}-${est['daily_revenue_range'][1]}"
    )
    print(
        f"  Monthly: ${est['monthly_revenue_range'][0]}-${est['monthly_revenue_range'][1]}"
    )

    # TTS status
    tts_type = type(pipeline._tts).__name__
    tts_ok = pipeline._tts.enabled
    print(f"\nTTS: {tts_type} ({'ready' if tts_ok else 'not available'})")
    if not tts_ok:
        print("  Free TTS: pip install edge-tts")
        print("  Paid TTS: set ELEVENLABS_API_KEY + RIENA_VOICE_ID")

    if pipeline.enabled:
        print(f"Video provider: {pipeline.video_provider}")
    else:
        print(
            "\nVideo backends (set one):\n"
            "  Free:  Kling free tier (KLING_ACCESS_KEY + KLING_SECRET_KEY)\n"
            "  Free:  Minimax free tier (MINIMAX_API_KEY + MINIMAX_GROUP_ID)\n"
            "  Paid:  Runway (RUNWAY_API_KEY)"
        )
