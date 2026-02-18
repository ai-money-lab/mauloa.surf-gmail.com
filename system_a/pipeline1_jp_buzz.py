"""Pipeline 1: Japanese Buzz Structure Import.

Collects viral Japanese tweets, analyzes their structure,
and rewrites them from HIROKI's perspective.
"""

import json
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

from core.claude_client import ClaudeClient
from core.quality_checker import QualityChecker

load_dotenv()

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data" / "system_a" / "pipeline1"
PROMPTS_DIR = BASE_DIR / "prompts"


class Pipeline1JpBuzz:
    """Collect viral JP tweets, analyze structure, rewrite as HIROKI."""

    def __init__(self):
        self.api_key = os.getenv("TWITTERAPI_IO_KEY", "")
        self.claude = ClaudeClient()
        self.quality_checker = QualityChecker(self.claude)
        self.min_likes = 10000
        self.lookback_hours = 72
        self.max_results = 30

    def collect_buzz_tweets(self) -> list:
        """Collect viral Japanese tweets via TwitterAPI.io."""
        if not self.api_key:
            logger.warning("TWITTERAPI_IO_KEY not set, skipping collection")
            return []

        url = "https://api.twitterapi.io/twitter/tweet/advanced_search"
        query = "min_faves:10000 lang:ja -is:reply -is:quote"

        headers = {"X-API-Key": self.api_key}
        params = {"query": query, "queryType": "Latest", "cursor": ""}

        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            tweets = data.get("tweets", [])
        except Exception as e:
            logger.error("Failed to collect tweets: %s", e)
            return []

        # Filter and score
        scored = []
        for tweet in tweets[:self.max_results]:
            likes = tweet.get("likeCount", 0)
            rts = tweet.get("retweetCount", 0)
            replies = tweet.get("replyCount", 0)
            followers = tweet.get("author", {}).get("followersCount", 1)
            engagement_rate = (likes + rts + replies) / max(followers, 1)

            scored.append({
                "id": tweet.get("id", ""),
                "text": tweet.get("text", ""),
                "likes": likes,
                "retweets": rts,
                "replies": replies,
                "followers": followers,
                "engagement_rate": round(engagement_rate, 4),
                "author": tweet.get("author", {}).get("userName", ""),
                "created_at": tweet.get("createdAt", ""),
            })

        # Sort by engagement rate
        scored.sort(key=lambda x: x["engagement_rate"], reverse=True)
        top30 = scored[:30]

        # Save
        today = datetime.now(JST).strftime("%Y-%m-%d")
        out_dir = DATA_DIR / "collected"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{today}.json"
        out_path.write_text(json.dumps(top30, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Collected %d buzz tweets -> %s", len(top30), out_path)
        return top30

    def analyze_structure(self, tweets: list) -> list:
        """Analyze viral structure of collected tweets using Claude."""
        if not tweets:
            return []

        prompt_template = (PROMPTS_DIR / "analyze_jp_buzz.txt").read_text(encoding="utf-8")
        tweets_text = json.dumps(tweets, ensure_ascii=False, indent=2)
        prompt = f"{prompt_template}\n\n## バズツイート一覧:\n{tweets_text}"

        try:
            analysis = self.claude.generate_json(prompt, temperature=0.3)
        except Exception as e:
            logger.error("Structure analysis failed: %s", e)
            return []

        if isinstance(analysis, dict):
            analysis = analysis.get("top10", analysis.get("results", []))

        return analysis if isinstance(analysis, list) else []

    def rewrite_as_hiroki(self, analyzed: list) -> list:
        """Rewrite top structures from HIROKI's perspective."""
        if not analyzed:
            return []

        prompt_template = (PROMPTS_DIR / "rewrite_jp_buzz.txt").read_text(encoding="utf-8")
        generated = []

        for item in analyzed[:10]:
            prompt = (
                f"{prompt_template}\n\n"
                f"## 元ツイートの構造分析:\n{json.dumps(item, ensure_ascii=False, indent=2)}"
            )
            try:
                result = self.claude.generate_json(prompt, temperature=0.8)
                if isinstance(result, dict):
                    result["source_structure"] = item
                    result["pipeline"] = "P1"
                    generated.append(result)
            except Exception as e:
                logger.warning("Rewrite failed for item: %s", e)

        # Save
        today = datetime.now(JST).strftime("%Y-%m-%d")
        out_dir = DATA_DIR / "generated"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{today}.json"
        out_path.write_text(
            json.dumps(generated, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("Generated %d P1 rewrites -> %s", len(generated), out_path)
        return generated

    def run(self) -> list:
        """Execute full Pipeline 1 flow."""
        logger.info("Pipeline 1: Starting JP buzz collection...")
        tweets = self.collect_buzz_tweets()
        logger.info("Pipeline 1: Analyzing structure of %d tweets...", len(tweets))
        analyzed = self.analyze_structure(tweets)
        logger.info("Pipeline 1: Rewriting top %d structures...", len(analyzed))
        generated = self.rewrite_as_hiroki(analyzed)
        logger.info("Pipeline 1: Complete. Generated %d posts.", len(generated))
        return generated


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    pipeline = Pipeline1JpBuzz()
    pipeline.run()
