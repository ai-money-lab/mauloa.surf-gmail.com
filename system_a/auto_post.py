"""Auto-post to X (Twitter) via MCP Server or TwitterAPI.io."""

import json
import logging
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

from core.sheets_client import SheetsClient
from core.notifier import Notifier
from core.image_generator import ImageGenerator

load_dotenv()

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
POSTED_LOG_PATH = Path(__file__).parent.parent / "data" / "system_a" / "posted_tweets.json"


class AutoPoster:
    """Post tweets to X automatically."""

    def __init__(self):
        self.api_key = os.getenv("X_API_KEY", "")
        self.api_secret = os.getenv("X_API_SECRET_KEY", "")
        self.access_token = os.getenv("X_ACCESS_TOKEN", "")
        self.access_secret = os.getenv("X_ACCESS_TOKEN_SECRET", "")
        self.bearer_token = os.getenv("X_BEARER_TOKEN", "")
        self.sheets = SheetsClient()
        self.notifier = Notifier()
        self.image_generator = ImageGenerator()

    def _get_oauth1_session(self):
        """Create OAuth1 session for X API v2."""
        from requests_oauthlib import OAuth1

        return OAuth1(
            self.api_key,
            client_secret=self.api_secret,
            resource_owner_key=self.access_token,
            resource_owner_secret=self.access_secret,
        )

    def _upload_media(self, image_path: str) -> str | None:
        """Upload an image to X and return the media_id.

        Uses X API v1.1 media/upload endpoint (chunked INIT/APPEND/FINALIZE).
        """
        filepath = Path(image_path)
        if not filepath.exists():
            logger.error("Image file not found: %s", image_path)
            return None

        file_size = filepath.stat().st_size
        mime = "image/png" if filepath.suffix == ".png" else "image/jpeg"
        auth = self._get_oauth1_session()
        upload_url = "https://upload.twitter.com/1.1/media/upload.json"

        try:
            # INIT
            resp = requests.post(
                upload_url,
                data={
                    "command": "INIT",
                    "total_bytes": file_size,
                    "media_type": mime,
                },
                auth=auth,
                timeout=30,
            )
            resp.raise_for_status()
            media_id = resp.json()["media_id_string"]

            # APPEND
            with open(filepath, "rb") as f:
                resp = requests.post(
                    upload_url,
                    data={"command": "APPEND", "media_id": media_id, "segment_index": 0},
                    files={"media_data": f},
                    auth=auth,
                    timeout=60,
                )
                resp.raise_for_status()

            # FINALIZE
            resp = requests.post(
                upload_url,
                data={"command": "FINALIZE", "media_id": media_id},
                auth=auth,
                timeout=30,
            )
            resp.raise_for_status()
            logger.info("Media uploaded: media_id=%s", media_id)
            return media_id

        except Exception as e:
            logger.error("Media upload failed: %s", e)
            return None

    def post_tweet(self, text: str, media_id: str | None = None) -> dict:
        """Post a single tweet, optionally with an image."""
        url = "https://api.x.com/2/tweets"
        auth = self._get_oauth1_session()
        payload = {"text": text}
        if media_id:
            payload["media"] = {"media_ids": [media_id]}

        try:
            resp = requests.post(url, json=payload, auth=auth, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            logger.info("Tweet posted: %s", data.get("data", {}).get("id"))
            return data
        except Exception as e:
            logger.error("Failed to post tweet: %s", e)
            raise

    def post_tweet_with_image(self, text: str, image_path: str) -> dict:
        """Post a tweet with an attached image.

        Uploads the image first, then posts the tweet with the media_id.
        Falls back to text-only if upload fails.
        """
        media_id = self._upload_media(image_path)
        if not media_id:
            logger.warning("Image upload failed, posting text-only")
        return self.post_tweet(text, media_id=media_id)

    def post_thread(self, texts: list, media_id: str | None = None) -> list:
        """Post a thread of tweets. First tweet can have an image."""
        results = []
        reply_to = None

        for i, text in enumerate(texts):
            url = "https://api.x.com/2/tweets"
            auth = self._get_oauth1_session()
            payload = {"text": text}
            if reply_to:
                payload["reply"] = {"in_reply_to_tweet_id": reply_to}
            # Attach image only to the first tweet in the thread
            if i == 0 and media_id:
                payload["media"] = {"media_ids": [media_id]}

            try:
                resp = requests.post(url, json=payload, auth=auth, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                tweet_id = data.get("data", {}).get("id")
                reply_to = tweet_id
                results.append(data)
                time.sleep(2)  # Avoid rate limits
            except Exception as e:
                logger.error("Thread post failed at tweet %d: %s", len(results) + 1, e)
                break

        return results

    def post_and_record(self, post: dict) -> dict:
        """Post a tweet/thread and record to Google Sheets.

        If post contains 'image_path', uploads the image and attaches it.
        """
        text = post.get("text", "")
        image_path = post.get("image_path")
        is_thread = isinstance(text, list)

        # Upload image if provided
        media_id = None
        if image_path:
            media_id = self._upload_media(image_path)
            if not media_id:
                logger.warning("Image upload failed for post, continuing text-only")

        if is_thread:
            result = self.post_thread(text, media_id=media_id)
        else:
            result = self.post_tweet(text, media_id=media_id)

        # Build record
        now = datetime.now(JST)
        tweet_id = ""
        if isinstance(result, dict):
            tweet_id = result.get("data", {}).get("id", "")
        elif isinstance(result, list) and result:
            tweet_id = result[0].get("data", {}).get("id", "")

        record = {
            "datetime": now.isoformat(),
            "tweet_id": tweet_id,
            "pillar": str(post.get("pillar", "")),
            "pipeline": post.get("pipeline", ""),
            "pattern": post.get("pattern", ""),
            "text": text if isinstance(text, str) else " | ".join(text),
            "quality_score": post.get("quality_score", ""),
            "image_path": image_path or "",
            "has_image": bool(media_id),
            "status": "posted",
        }

        # Save to local log
        self._save_to_local_log(record)

        # Record to Sheets
        try:
            self.sheets.record_post(record)
        except Exception as e:
            logger.warning("Failed to record to Sheets: %s", e)

        return result

    def _save_to_local_log(self, record: dict) -> None:
        """Append a posted tweet record to the local JSON log."""
        existing = []
        if POSTED_LOG_PATH.exists():
            try:
                existing = json.loads(POSTED_LOG_PATH.read_text(encoding="utf-8"))
            except Exception:
                existing = []

        existing.append(record)
        POSTED_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        POSTED_LOG_PATH.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
        )

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    poster = AutoPoster()
    # Example usage: poster.post_tweet("テスト投稿です")
