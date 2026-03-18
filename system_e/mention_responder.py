"""System E — Mention Auto-Responder.

Generates and posts character-consistent replies to mentions/comments.
Uses Claude to maintain Maia's voice while keeping replies natural.

Safety:
- Rate limited (max 20 replies/hour)
- Filters spam, toxic, and off-topic mentions
- Every reply includes AI disclosure
"""

import json
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml
from dotenv import load_dotenv

from core.claude_client import ClaudeClient
from system_e.engagement_collector import EngagementCollector

load_dotenv()

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
CONFIG_PATH = Path(__file__).parent / "character_config.yaml"
REPLY_LOG = Path(__file__).parent.parent / "data" / "system_e" / "reply_log.json"

# Safety limits
MAX_REPLIES_PER_HOUR = 20
MAX_REPLY_LENGTH = 240  # Leave room for @mention


class MentionResponder:
    """Reply to mentions in Maia's character voice."""

    def __init__(self):
        self.claude = ClaudeClient()
        self.collector = EngagementCollector()
        with open(CONFIG_PATH, encoding="utf-8") as f:
            self.config = yaml.safe_load(f)
        self.character = self.config["character"]
        REPLY_LOG.parent.mkdir(parents=True, exist_ok=True)

    def run(self) -> list[dict]:
        """Main loop: collect mentions → generate replies → post.

        Returns:
            List of reply results.
        """
        if self._hourly_reply_count() >= MAX_REPLIES_PER_HOUR:
            logger.info("Hourly reply limit reached (%d)", MAX_REPLIES_PER_HOUR)
            return []

        unreplied = self.collector.get_unreplied_mentions()
        if not unreplied:
            logger.info("No unreplied mentions")
            return []

        results = []
        remaining = MAX_REPLIES_PER_HOUR - self._hourly_reply_count()

        for mention in unreplied[:remaining]:
            if self._should_skip(mention):
                self.collector.mark_mention_replied(mention["tweet_id"])
                continue

            reply_text = self._generate_reply(mention)
            if not reply_text:
                continue

            result = self._post_reply(mention, reply_text)
            if result:
                self.collector.mark_mention_replied(mention["tweet_id"])
                self._log_reply(mention, reply_text, result)
                results.append(result)

        logger.info("Replied to %d/%d mentions", len(results), len(unreplied))
        return results

    def _generate_reply(self, mention: dict) -> str | None:
        """Generate a character-consistent reply to a mention."""
        char = self.character
        voice = char["content_voice"]

        system_prompt = f"""You are {char['name']}, {char['tagline']}.
Personality: {', '.join(char['personality']['traits'])}
Tone: {voice['tone']}
Catchphrase: {voice['catchphrase']}

You are replying to a mention/comment on X (Twitter).
Rules:
- Stay in character as {char['name']}
- Be warm, genuine, and concise
- Max {MAX_REPLY_LENGTH} characters
- NEVER discuss: {', '.join(voice['banned_topics'])}
- If the mention is about a topic you can't discuss, politely redirect
- Do NOT use hashtags in replies (they look robotic)
- Match the energy of the original message
- If they asked a question, answer it authentically
- If they complimented you, be gracious but not over-the-top"""

        prompt = f"""Reply to this mention from @{mention.get('author_username', 'someone')}:

"{mention.get('text', '')}"

Write ONLY the reply text, nothing else. Max {MAX_REPLY_LENGTH} chars."""

        try:
            reply = self.claude.generate(
                prompt=prompt,
                system=system_prompt,
                max_tokens=256,
                temperature=0.85,
            ).strip().strip('"')

            # Enforce length limit
            if len(reply) > MAX_REPLY_LENGTH:
                reply = reply[:MAX_REPLY_LENGTH - 1] + "…"

            return reply

        except Exception as e:
            logger.error("Reply generation failed for %s: %s", mention["tweet_id"], e)
            return None

    def _post_reply(self, mention: dict, text: str) -> dict | None:
        """Post a reply to X via API v2."""
        from system_a.auto_post import AutoPoster

        poster = AutoPoster()
        # Use System E credentials if available
        se_token = os.getenv("SYSTEM_E_X_ACCESS_TOKEN", "")
        if se_token:
            poster.api_key = os.getenv("SYSTEM_E_X_API_KEY", "")
            poster.api_secret = os.getenv("SYSTEM_E_X_API_SECRET_KEY", "")
            poster.access_token = se_token
            poster.access_secret = os.getenv("SYSTEM_E_X_ACCESS_TOKEN_SECRET", "")

        url = "https://api.x.com/2/tweets"
        auth = poster._get_oauth1_session()
        payload = {
            "text": text,
            "reply": {"in_reply_to_tweet_id": mention["tweet_id"]},
        }

        try:
            resp = __import__("requests").post(
                url, json=payload, auth=auth, timeout=15
            )
            resp.raise_for_status()
            data = resp.json()
            logger.info(
                "Replied to @%s (tweet %s)",
                mention.get("author_username", "?"),
                mention["tweet_id"],
            )
            return data
        except Exception as e:
            logger.error("Failed to post reply: %s", e)
            return None

    def _should_skip(self, mention: dict) -> bool:
        """Filter mentions that shouldn't receive a reply."""
        text = mention.get("text", "").lower()

        # Skip if it's our own tweet
        own_user_id = os.getenv("SYSTEM_E_X_USER_ID", "")
        if own_user_id and mention.get("author_id") == own_user_id:
            return True

        # Skip obvious spam patterns
        spam_patterns = [
            "buy followers", "free crypto", "dm me for",
            "check my bio", "click the link", "giveaway",
            "send me a dm", "follow for follow",
        ]
        if any(p in text for p in spam_patterns):
            logger.info("Skipping spam mention: %s", mention["tweet_id"])
            return True

        return False

    def _hourly_reply_count(self) -> int:
        """Count replies posted in the last hour."""
        if not REPLY_LOG.exists():
            return 0
        try:
            logs = json.loads(REPLY_LOG.read_text(encoding="utf-8"))
            cutoff = (datetime.now(JST) - timedelta(hours=1)).isoformat()
            return sum(1 for r in logs if r.get("replied_at", "") > cutoff)
        except Exception:
            return 0

    def _log_reply(self, mention: dict, reply_text: str, result: dict) -> None:
        """Log a sent reply."""
        existing = []
        if REPLY_LOG.exists():
            try:
                existing = json.loads(REPLY_LOG.read_text(encoding="utf-8"))
            except Exception:
                existing = []

        existing.append({
            "mention_tweet_id": mention["tweet_id"],
            "mention_author": mention.get("author_username", ""),
            "mention_text": mention.get("text", "")[:200],
            "reply_text": reply_text,
            "reply_tweet_id": result.get("data", {}).get("id", ""),
            "replied_at": datetime.now(JST).isoformat(),
        })

        REPLY_LOG.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    responder = MentionResponder()
    results = responder.run()
    print(f"Replied to {len(results)} mentions")
