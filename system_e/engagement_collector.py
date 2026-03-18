"""System E — Engagement Collector.

Polls the X API for tweet metrics and mentions, then feeds them into Analytics.
Designed to run on a schedule (e.g., every 2 hours via GitHub Actions).
"""

import json
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

from system_e.analytics import Analytics

load_dotenv()

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
POSTED_LOG = Path(__file__).parent.parent / "data" / "system_e" / "posted_log.json"
MENTIONS_DIR = Path(__file__).parent.parent / "data" / "system_e" / "mentions"


class EngagementCollector:
    """Fetch engagement metrics and mentions from X API v2."""

    def __init__(self):
        self.bearer_token = (
            os.getenv("SYSTEM_E_X_BEARER_TOKEN")
            or os.getenv("X_BEARER_TOKEN", "")
        )
        self.analytics = Analytics()
        MENTIONS_DIR.mkdir(parents=True, exist_ok=True)

    @property
    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.bearer_token}"}

    # ─── Tweet Metrics ───

    def collect_tweet_metrics(self) -> int:
        """Fetch engagement metrics for recent tweets and record them.

        Returns:
            Number of tweets updated.
        """
        if not self.bearer_token:
            logger.warning("No bearer token — skipping metrics collection")
            return 0

        tweet_ids = self._get_recent_tweet_ids(days=3)
        if not tweet_ids:
            logger.info("No recent tweet IDs to collect metrics for")
            return 0

        # X API v2 allows up to 100 tweet IDs per request
        updated = 0
        for batch in _chunks(tweet_ids, 100):
            metrics = self._fetch_tweet_metrics(batch)
            for tweet_id, data in metrics.items():
                self.analytics.record_engagement(tweet_id, data)
                updated += 1

        logger.info("Collected metrics for %d tweets", updated)
        return updated

    def _fetch_tweet_metrics(self, tweet_ids: list[str]) -> dict[str, dict]:
        """Fetch public metrics for a batch of tweet IDs."""
        url = "https://api.x.com/2/tweets"
        params = {
            "ids": ",".join(tweet_ids),
            "tweet.fields": "public_metrics,created_at",
        }

        try:
            resp = requests.get(url, headers=self._headers, params=params, timeout=15)
            resp.raise_for_status()
            result = {}
            for tweet in resp.json().get("data", []):
                pm = tweet.get("public_metrics", {})
                result[tweet["id"]] = {
                    "likes": pm.get("like_count", 0),
                    "retweets": pm.get("retweet_count", 0),
                    "replies": pm.get("reply_count", 0),
                    "impressions": pm.get("impression_count", 0),
                    "quotes": pm.get("quote_count", 0),
                    "bookmarks": pm.get("bookmark_count", 0),
                }
            return result
        except Exception as e:
            logger.error("Failed to fetch tweet metrics: %s", e)
            return {}

    def _get_recent_tweet_ids(self, days: int = 3) -> list[str]:
        """Get tweet IDs from posted_log for the last N days."""
        if not POSTED_LOG.exists():
            return []
        try:
            records = json.loads(POSTED_LOG.read_text(encoding="utf-8"))
        except Exception:
            return []

        cutoff = (datetime.now(JST) - timedelta(days=days)).strftime("%Y-%m-%d")
        ids = []
        for r in records:
            if r.get("date", "") >= cutoff and r.get("tweet_id"):
                ids.append(r["tweet_id"])
        return ids

    # ─── Mentions ───

    def collect_mentions(self, user_id: str | None = None) -> list[dict]:
        """Fetch recent mentions of the account.

        Args:
            user_id: X user ID. If not set, attempts to look it up.

        Returns:
            List of new mention dicts.
        """
        if not self.bearer_token:
            logger.warning("No bearer token — skipping mentions collection")
            return []

        if not user_id:
            user_id = self._get_own_user_id()
            if not user_id:
                return []

        since_id = self._get_last_mention_id()
        mentions = self._fetch_mentions(user_id, since_id)

        if mentions:
            self._save_mentions(mentions)
            logger.info("Collected %d new mentions", len(mentions))

        return mentions

    def _fetch_mentions(
        self, user_id: str, since_id: str | None = None
    ) -> list[dict]:
        """Fetch mentions from X API v2 user timeline mentions."""
        url = f"https://api.x.com/2/users/{user_id}/mentions"
        params = {
            "max_results": 50,
            "tweet.fields": "author_id,created_at,conversation_id,in_reply_to_user_id,text",
            "expansions": "author_id",
            "user.fields": "username,name",
        }
        if since_id:
            params["since_id"] = since_id

        try:
            resp = requests.get(url, headers=self._headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            # Build username lookup
            users_map = {}
            for user in data.get("includes", {}).get("users", []):
                users_map[user["id"]] = user.get("username", "")

            mentions = []
            for tweet in data.get("data", []):
                mentions.append({
                    "tweet_id": tweet["id"],
                    "text": tweet["text"],
                    "author_id": tweet["author_id"],
                    "author_username": users_map.get(tweet["author_id"], ""),
                    "conversation_id": tweet.get("conversation_id", ""),
                    "in_reply_to": tweet.get("in_reply_to_user_id", ""),
                    "created_at": tweet.get("created_at", ""),
                    "collected_at": datetime.now(JST).isoformat(),
                    "replied": False,
                })
            return mentions

        except Exception as e:
            logger.error("Failed to fetch mentions: %s", e)
            return []

    def _get_own_user_id(self) -> str | None:
        """Look up the authenticated user's ID."""
        url = "https://api.x.com/2/users/me"
        try:
            resp = requests.get(url, headers=self._headers, timeout=10)
            resp.raise_for_status()
            return resp.json().get("data", {}).get("id")
        except Exception as e:
            logger.error("Failed to get own user ID: %s", e)
            return None

    def get_unreplied_mentions(self) -> list[dict]:
        """Get mentions that haven't been replied to yet."""
        mentions_file = self._today_mentions_file()
        if not mentions_file.exists():
            return []
        try:
            mentions = json.loads(mentions_file.read_text(encoding="utf-8"))
            return [m for m in mentions if not m.get("replied")]
        except Exception:
            return []

    def mark_mention_replied(self, tweet_id: str) -> None:
        """Mark a mention as replied in today's file."""
        mentions_file = self._today_mentions_file()
        if not mentions_file.exists():
            return
        try:
            mentions = json.loads(mentions_file.read_text(encoding="utf-8"))
            for m in mentions:
                if m["tweet_id"] == tweet_id:
                    m["replied"] = True
                    m["replied_at"] = datetime.now(JST).isoformat()
            mentions_file.write_text(
                json.dumps(mentions, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception as e:
            logger.error("Failed to mark mention replied: %s", e)

    # ─── Helpers ───

    def _today_mentions_file(self) -> Path:
        today = datetime.now(JST).strftime("%Y-%m-%d")
        return MENTIONS_DIR / f"mentions_{today}.json"

    def _save_mentions(self, mentions: list[dict]) -> None:
        mentions_file = self._today_mentions_file()
        existing = []
        if mentions_file.exists():
            try:
                existing = json.loads(mentions_file.read_text(encoding="utf-8"))
            except Exception:
                existing = []

        seen_ids = {m["tweet_id"] for m in existing}
        for m in mentions:
            if m["tweet_id"] not in seen_ids:
                existing.append(m)

        mentions_file.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _get_last_mention_id(self) -> str | None:
        """Get the most recent mention ID to paginate from."""
        mentions_file = self._today_mentions_file()
        if not mentions_file.exists():
            return None
        try:
            mentions = json.loads(mentions_file.read_text(encoding="utf-8"))
            if mentions:
                return max(m["tweet_id"] for m in mentions)
        except Exception:
            pass
        return None


def _chunks(lst: list, n: int):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    collector = EngagementCollector()
    count = collector.collect_tweet_metrics()
    print(f"Updated metrics for {count} tweets")
    mentions = collector.collect_mentions()
    print(f"Collected {len(mentions)} new mentions")
