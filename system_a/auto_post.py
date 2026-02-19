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

    def _get_oauth1_session(self):
        """Create OAuth1 session for X API v2."""
        from requests_oauthlib import OAuth1

        return OAuth1(
            self.api_key,
            client_secret=self.api_secret,
            resource_owner_key=self.access_token,
            resource_owner_secret=self.access_secret,
        )

    def post_tweet(self, text: str) -> dict:
        """Post a single tweet."""
        url = "https://api.x.com/2/tweets"
        auth = self._get_oauth1_session()
        payload = {"text": text}

        try:
            resp = requests.post(url, json=payload, auth=auth, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            logger.info("Tweet posted: %s", data.get("data", {}).get("id"))
            return data
        except Exception as e:
            logger.error("Failed to post tweet: %s", e)
            raise

    def post_thread(self, texts: list) -> list:
        """Post a thread of tweets."""
        results = []
        reply_to = None

        for text in texts:
            url = "https://api.x.com/2/tweets"
            auth = self._get_oauth1_session()
            payload = {"text": text}
            if reply_to:
                payload["reply"] = {"in_reply_to_tweet_id": reply_to}

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
        """Post a tweet/thread and record to Google Sheets."""
        text = post.get("text", "")
        is_thread = isinstance(text, list)

        if is_thread:
            result = self.post_thread(text)
        else:
            result = self.post_tweet(text)

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

    def execute_scheduled(self, posts: list) -> None:
        """Execute scheduled posts at their designated times."""
        now = datetime.now(JST)
        current_time = now.strftime("%H:%M")

        for post in posts:
            scheduled = post.get("scheduled_time", "")
            if scheduled == current_time:
                logger.info("Posting scheduled tweet at %s", scheduled)
                self.post_and_record(post)

                # Notify 30 min later
                self.notifier.send_line(
                    f"投稿完了（{scheduled}）。リプ返信推奨。\n"
                    f"柱{post.get('pillar', '?')} / {post.get('pipeline', '?')}"
                )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    poster = AutoPoster()
    # Example usage: poster.post_tweet("テスト投稿です")
