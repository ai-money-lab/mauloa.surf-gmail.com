"""System E — Multi-Timezone Posting Scheduler.

Manages posting schedule across time zones for maximum global reach.
Uses dedicated X account credentials (SYSTEM_E_X_* env vars)
with fallback to default X_* credentials.

FTC Compliance: Every post automatically includes #AICreator disclosure.
"""

import json
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml
from dotenv import load_dotenv

from system_a.auto_post import AutoPoster

load_dotenv()

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
GENERATED_DIR = Path(__file__).parent.parent / "data" / "system_e" / "generated"
POSTED_LOG = Path(__file__).parent.parent / "data" / "system_e" / "posted_log.json"
CHAR_CONFIG_PATH = Path(__file__).parent / "character_config.yaml"

# FTC-required AI disclosure hashtags — loaded from config, hardcoded fallback
_DISCLOSURE_TAGS_FALLBACK = ["#AICreator", "#AIGenerated"]


def _load_disclosure_tags() -> list[str]:
    """Load mandatory AI disclosure hashtags from character config."""
    try:
        with open(CHAR_CONFIG_PATH, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        tags = config.get("disclosure", {}).get("post_hashtags", [])
        return tags if tags else _DISCLOSURE_TAGS_FALLBACK
    except Exception:
        return _DISCLOSURE_TAGS_FALLBACK


class PostingScheduler:
    """Schedule and execute posts at optimal times across time zones."""

    # System E uses higher daily post limit than System A
    MAX_POSTS_PER_DAY = 5

    def __init__(self):
        self.poster = AutoPoster()
        self.disclosure_tags = _load_disclosure_tags()
        # Use System E dedicated X account if configured, else fall back to default
        se_api_key = os.getenv("SYSTEM_E_X_API_KEY", "")
        se_access_token = os.getenv("SYSTEM_E_X_ACCESS_TOKEN", "")
        if se_api_key and se_access_token:
            self.poster.api_key = se_api_key
            self.poster.api_secret = os.getenv("SYSTEM_E_X_API_SECRET_KEY", "")
            self.poster.access_token = se_access_token
            self.poster.access_secret = os.getenv("SYSTEM_E_X_ACCESS_TOKEN_SECRET", "")
            self.poster.bearer_token = os.getenv("SYSTEM_E_X_BEARER_TOKEN", "")
            logger.info("Using dedicated System E X account credentials")
        else:
            logger.info("Using default X account credentials (SYSTEM_E_X_* not set)")

    def get_pending_posts(self, date: str | None = None) -> list[dict]:
        """Get posts scheduled for today that haven't been posted yet.

        Args:
            date: Target date (YYYY-MM-DD). Defaults to today.

        Returns:
            List of pending content items.
        """
        if not date:
            date = datetime.now(JST).strftime("%Y-%m-%d")

        plan_file = GENERATED_DIR / f"content_plan_{date}.json"
        if not plan_file.exists():
            logger.warning("No content plan found for %s", date)
            return []

        plan = json.loads(plan_file.read_text(encoding="utf-8"))
        posted_ids = self._get_posted_ids(date)

        pending = []
        for item in plan:
            item_id = f"{date}_{item.get('scheduled_time_jst', '')}"
            if item_id not in posted_ids and item.get("text"):
                item["_post_id"] = item_id
                pending.append(item)

        return pending

    def get_due_posts(self) -> list[dict]:
        """Get posts that are due to be posted now (within 15-minute window).

        Returns:
            List of content items due for posting.
        """
        now = datetime.now(JST)
        today = now.strftime("%Y-%m-%d")
        current_time = now.strftime("%H:%M")

        pending = self.get_pending_posts(today)
        due = []

        for item in pending:
            scheduled = item.get("scheduled_time_jst", "")
            if not scheduled:
                continue

            # Check if within 15-minute posting window
            try:
                sched_h, sched_m = map(int, scheduled.split(":"))
                cur_h, cur_m = map(int, current_time.split(":"))
                sched_mins = sched_h * 60 + sched_m
                cur_mins = cur_h * 60 + cur_m
                diff = cur_mins - sched_mins

                if 0 <= diff <= 15:
                    due.append(item)
            except ValueError:
                logger.warning("Invalid time format: %s", scheduled)

        return due

    def post_content(self, content: dict) -> dict | None:
        """Post a single content item to X.

        Args:
            content: Content dict with 'text', 'hashtags', 'image_path' etc.

        Returns:
            Post result dict, or None on failure.
        """
        text = content.get("text", "")
        if not text:
            logger.warning("Empty text in content, skipping")
            return None

        text = self._append_hashtags(text, content.get("hashtags", []))

        # Build post dict compatible with AutoPoster
        post = {
            "text": text,
            "pipeline": "system_e",
            "pillar": content.get("scene", ""),
            "quality_score": content.get("hook_quality", ""),
        }

        # Attach image if available
        image_path = content.get("image_path")
        if image_path and Path(image_path).exists():
            post["image_path"] = image_path

        try:
            result = self.poster.post_tweet(
                text,
                media_id=self._upload_media(image_path) if image_path else None,
            )

            # Record
            self._record_post(content, result)
            logger.info(
                "Posted [%s]: %s",
                content.get("scheduled_time_jst", "?"),
                text[:60],
            )
            return result

        except Exception as e:
            logger.error("Failed to post: %s", e)
            return None

    def _upload_media(self, image_path: str | None) -> str | None:
        """Upload media via AutoPoster."""
        if not image_path or not Path(image_path).exists():
            return None
        return self.poster._upload_media(image_path)

    def post_thread(self, content: dict) -> list[dict]:
        """Post a thread to X.

        Args:
            content: Content dict with 'tweets' list.

        Returns:
            List of post results.
        """
        tweets = content.get("tweets", [])
        if not tweets:
            return []

        # Number the tweets
        numbered = [f"{i+1}/{len(tweets)} {t}" for i, t in enumerate(tweets)]

        # Add disclosure + content hashtags to first tweet
        if numbered:
            numbered[0] = self._append_hashtags(
                numbered[0], content.get("hashtags", [])
            )

        try:
            results = self.poster.post_thread(numbered)
            self._record_post(content, results)
            return results
        except Exception as e:
            logger.error("Thread post failed: %s", e)
            return []

    def run_due_posts(self) -> list[dict]:
        """Post all content that is currently due.

        This is the main method called by the scheduler/cron.
        """
        due = self.get_due_posts()
        if not due:
            logger.info("No posts due at this time")
            return []

        results = []
        for content in due:
            if "tweets" in content:
                result = self.post_thread(content)
            else:
                result = self.post_content(content)
            if result:
                results.append(result)

        logger.info("Posted %d/%d due items", len(results), len(due))
        return results

    def _append_hashtags(self, text: str, content_hashtags: list[str]) -> str:
        """Append hashtags to text, ensuring AI disclosure tags are always included.

        Priority order:
        1. AI disclosure tags (mandatory — #AICreator, #AIGenerated)
        2. Content hashtags (optional, space permitting)

        If even disclosure tags don't fit, truncate text to make room.
        """
        max_len = 280
        # Build disclosure string (always included)
        disclosure_str = " ".join(self.disclosure_tags)

        # Build optional content tags (deduplicate against disclosure)
        disclosure_lower = {t.lower() for t in self.disclosure_tags}
        extra_tags = [
            f"#{tag}" for tag in content_hashtags[:5]
            if f"#{tag}".lower() not in disclosure_lower
        ]

        # Try: text + disclosure + content tags
        full_tags = f"{disclosure_str} {' '.join(extra_tags)}".strip() if extra_tags else disclosure_str
        candidate = f"{text}\n\n{full_tags}"
        if len(candidate) <= max_len:
            return candidate

        # Try: text + disclosure only
        candidate = f"{text}\n\n{disclosure_str}"
        if len(candidate) <= max_len:
            return candidate

        # Last resort: truncate text to fit disclosure
        available = max_len - len(f"\n\n{disclosure_str}")
        truncated = text[:available - 1] + "…"
        logger.warning("Text truncated to fit AI disclosure tags")
        return f"{truncated}\n\n{disclosure_str}"

    def _get_posted_ids(self, date: str) -> set:
        """Get IDs of already-posted content for a date."""
        if not POSTED_LOG.exists():
            return set()
        try:
            records = json.loads(POSTED_LOG.read_text(encoding="utf-8"))
            return {r["post_id"] for r in records if r.get("date") == date}
        except Exception:
            return set()

    def _record_post(self, content: dict, result) -> None:
        """Record a posted item to the log."""
        existing = []
        if POSTED_LOG.exists():
            try:
                existing = json.loads(POSTED_LOG.read_text(encoding="utf-8"))
            except Exception:
                existing = []

        now = datetime.now(JST)
        record = {
            "post_id": content.get("_post_id", now.isoformat()),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "type": content.get("type", "standard"),
            "scene": content.get("scene", ""),
            "text": content.get("text", "")[:140],
            "posted_at": now.isoformat(),
        }

        # Extract tweet ID from result
        if isinstance(result, dict):
            record["tweet_id"] = result.get("data", {}).get("id", "")
        elif isinstance(result, list) and result:
            record["tweet_id"] = result[0].get("data", {}).get("id", "")

        existing.append(record)
        POSTED_LOG.parent.mkdir(parents=True, exist_ok=True)
        POSTED_LOG.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    scheduler = PostingScheduler()
    due = scheduler.get_due_posts()
    print(f"Due posts: {len(due)}")
    for post in due:
        print(f"  [{post.get('scheduled_time_jst')}] {post.get('text', '')[:60]}")
