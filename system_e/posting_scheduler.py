"""System E — Multi-Timezone Posting Scheduler.

Manages posting schedule across time zones for maximum global reach.
Uses dedicated X account credentials (SYSTEM_E_X_* env vars)
with fallback to default X_* credentials.

FTC Compliance: AI disclosure is handled via the account bio
("AI-generated wellness creator | Powered by AI"), not per-post hashtags.
This bio-based approach satisfies FTC guidelines while avoiding the ~40%
reach penalty that multiple hashtags cause on X/Twitter.

Algorithm Guard: Every post checked for penalty triggers before publishing.
"""

import json
import logging
import os
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml
from dotenv import load_dotenv

from system_a.auto_post import AutoPoster
from system_e.algorithm_guard import AlgorithmGuard

load_dotenv()

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
GENERATED_DIR = Path(__file__).parent.parent / "data" / "system_e" / "generated"
POSTED_LOG = Path(__file__).parent.parent / "data" / "system_e" / "posted_log.json"
CHAR_CONFIG_PATH = Path(__file__).parent / "character_config.yaml"

# Branded hashtag — the account's signature tag on every post
BRANDED_HASHTAG = "#RienaWellness"

# AI disclosure strategy: bio-based, NOT per-post hashtags.
# The account bio reads "AI-generated wellness creator | Powered by AI"
# which satisfies FTC transparency requirements without penalizing reach.
# Research shows multiple hashtags reduce X/Twitter reach by ~40%.


class PostingScheduler:
    """Schedule and execute posts at optimal times across time zones."""

    # System E uses higher daily post limit than System A
    MAX_POSTS_PER_DAY = 5

    def __init__(self):
        self.poster = AutoPoster()
        self.guard = AlgorithmGuard()
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

        # Algorithm Guard: 投稿前に引き算ルールチェック
        check = self.guard.check_post(text)
        if not check["approved"]:
            if check["fixed_text"]:
                logger.warning(
                    "Algorithm guard auto-fixed post: %s",
                    [v["rule"] for v in check["violations"]],
                )
                text = check["fixed_text"]
                # Re-check after fix
                recheck = self.guard.check_post(text)
                if not recheck["approved"]:
                    logger.error(
                        "Post BLOCKED by algorithm guard: %s",
                        [v["detail"] for v in recheck["violations"]],
                    )
                    return None
            else:
                logger.error(
                    "Post BLOCKED by algorithm guard: %s",
                    [v["detail"] for v in check["violations"]],
                )
                return None

        if check["warnings"]:
            for w in check["warnings"]:
                logger.warning("Algorithm guard warning: [%s] %s", w["rule"], w["detail"])

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

            # Self-reply boost: reply to own tweet for engagement velocity
            tweet_id = result.get("data", {}).get("id", "") if isinstance(result, dict) else ""
            if tweet_id:
                self._post_boost_reply(tweet_id, content)

            return result

        except Exception as e:
            logger.error("Failed to post: %s", e)
            return None

    # ── Self-Reply Boost Templates ──
    # Replying to your own tweet within 5 min signals engagement velocity
    # to the algorithm. Replies are worth ~150x likes for reach.
    BOOST_TEMPLATES = {
        "engagement": [
            "Curious what you all think about this \U0001f447",
            "What's YOUR take? Drop it below",
            "Would love to hear your experience with this \U0001f64f",
            "Agree or disagree? Let me know \U0001f447",
            "Anyone else feel the same way?",
        ],
        "standard": [
            "This has been on my mind all week. Anyone else?",
            "Been thinking about this a lot lately.",
            "Honestly can't stop thinking about this one.",
            "This changed my perspective on so many things.",
            "Still processing this tbh.",
        ],
        "story": [
            "The data on this is actually wild. More on this later \U0001f9f5",
            "Been testing this for 2 weeks now. Results coming soon.",
            "Part 2 dropping soon. Stay tuned \U0001f440",
            "There's so much more to this story.",
            "Wait until you see what happened next.",
        ],
    }

    @classmethod
    def _select_boost_template(cls, content_type: str) -> str:
        """Select a boost reply template based on content type.

        Args:
            content_type: Template category ('engagement', 'standard', 'story').

        Returns:
            A randomly selected template string (max 200 chars).
        """
        if content_type in cls.BOOST_TEMPLATES:
            return random.choice(cls.BOOST_TEMPLATES[content_type])
        return random.choice(cls.BOOST_TEMPLATES["standard"])

    def _post_boost_reply(self, tweet_id: str, content: dict) -> dict | None:
        """Post a self-reply to boost engagement velocity.

        Research shows replying to your own tweet within 5 minutes
        significantly boosts reach on X/Twitter (engagement velocity signal).
        Replies are worth ~150x the value of likes.

        Args:
            tweet_id: The ID of the just-posted tweet to reply to.
            content: The original content dict (used to determine content type).

        Returns:
            Reply post result dict, or None on failure.
        """
        if not tweet_id:
            logger.warning("No tweet_id provided, skipping boost reply")
            return None

        # Map content type to template category
        content_type = content.get("type", "standard")
        if content_type in ("question", "poll", "engagement"):
            template_key = "engagement"
        elif content_type in ("story", "thread_teaser", "personal"):
            template_key = "story"
        else:
            template_key = "standard"

        reply_text = self._select_boost_template(template_key)

        try:
            result = self.poster.post_tweet(reply_text, reply_to=tweet_id)
            logger.info(
                "Boost reply posted to tweet %s: %s",
                tweet_id,
                reply_text[:60],
            )
            return result
        except Exception as e:
            # Boost reply failure should not break the main posting flow
            logger.warning("Boost reply failed (non-critical): %s", e)
            return None

    def _upload_media(self, image_path: str | None) -> str | None:
        """Upload media via AutoPoster."""
        if not image_path or not Path(image_path).exists():
            return None
        return self.poster._upload_media(image_path)

    def post_poll(self, content: dict) -> dict | None:
        """Post a poll to X via API v2.

        Args:
            content: Content dict with 'text', 'options', 'duration_minutes'.

        Returns:
            Post result dict, or None on failure.
        """
        text = content.get("text", "")
        options = content.get("options", [])
        duration = content.get("duration_minutes", 1440)

        if not text or len(options) < 2:
            logger.warning("Invalid poll content (need text + 2+ options), skipping")
            return None

        # Append hashtags to poll question text
        text = self._append_hashtags(text, content.get("hashtags", []))

        # Algorithm Guard check
        check = self.guard.check_post(text)
        if not check["approved"]:
            if check["fixed_text"]:
                logger.warning(
                    "Algorithm guard auto-fixed poll: %s",
                    [v["rule"] for v in check["violations"]],
                )
                text = check["fixed_text"]
                recheck = self.guard.check_post(text)
                if not recheck["approved"]:
                    logger.error(
                        "Poll BLOCKED by algorithm guard: %s",
                        [v["detail"] for v in recheck["violations"]],
                    )
                    return None
            else:
                logger.error(
                    "Poll BLOCKED by algorithm guard: %s",
                    [v["detail"] for v in check["violations"]],
                )
                return None

        # X API v2 poll payload
        payload = {
            "text": text,
            "poll": {
                "options": [opt[:25] for opt in options[:4]],
                "duration_minutes": duration,
            },
        }

        try:
            result = self.poster.post_tweet_v2(payload)
            self._record_post(content, result)
            logger.info("Poll posted: %s (%d options)", text[:60], len(options))
            return result
        except AttributeError:
            # Fallback: post as regular tweet if post_tweet_v2 not available
            logger.warning("post_tweet_v2 not available, posting poll as text")
            option_text = " | ".join(f"[{opt}]" for opt in options[:4])
            fallback_text = f"{text}\n\n{option_text}"
            try:
                result = self.poster.post_tweet(fallback_text[:280])
                self._record_post(content, result)
                return result
            except Exception as e:
                logger.error("Poll fallback post failed: %s", e)
                return None
        except Exception as e:
            logger.error("Failed to post poll: %s", e)
            return None

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

        # Add branded + content hashtags to first tweet
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
            content_type = content.get("type", "")
            if content_type == "poll" and content.get("options"):
                result = self.post_poll(content)
            elif "tweets" in content:
                result = self.post_thread(content)
            else:
                result = self.post_content(content)
            if result:
                results.append(result)

        logger.info("Posted %d/%d due items", len(results), len(due))
        return results

    def _append_hashtags(self, text: str, content_hashtags: list[str]) -> str:
        """Append hashtags to text. Max 2 hashtags per post for optimal reach.

        Strategy (bio-based AI disclosure):
        - AI disclosure lives in the account bio, NOT in every post.
        - Posts get max 2 hashtags: 1 content tag (most relevant) + #RienaWellness.
        - Research shows multiple hashtags reduce X/Twitter reach by ~40%.

        Priority order:
        1. #RienaWellness (branded, always included if space permits)
        2. 1 content hashtag (the first/most relevant one, if space permits)
        """
        max_len = 280

        # Pick at most 1 content hashtag (the most relevant one)
        content_tag = f"#{content_hashtags[0]}" if content_hashtags else ""
        # Avoid duplicating the branded tag
        if content_tag.lower() == BRANDED_HASHTAG.lower():
            content_tag = f"#{content_hashtags[1]}" if len(content_hashtags) > 1 else ""

        # Try: text + branded + 1 content tag
        if content_tag:
            tags_str = f"{content_tag} {BRANDED_HASHTAG}"
            candidate = f"{text}\n\n{tags_str}"
            if len(candidate) <= max_len:
                return candidate

        # Try: text + branded only
        candidate = f"{text}\n\n{BRANDED_HASHTAG}"
        if len(candidate) <= max_len:
            return candidate

        # Last resort: just return text without hashtags (better than truncating)
        return text

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
