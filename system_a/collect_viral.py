"""System A - TASK A-2: バイラル投稿収集

TwitterAPI.io で海外バイラル投稿を収集し、TOP20を抽出してJSON保存する。
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
import yaml
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data" / "system_a" / "collected"


def load_config() -> dict:
    with open(BASE_DIR / "config" / "config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class ViralCollector:
    """海外バイラルツイート収集"""

    def __init__(self):
        self.api_key = os.getenv("TWITTERAPI_IO_KEY")
        if not self.api_key:
            raise ValueError("TWITTERAPI_IO_KEY not set")
        self.config = load_config()["system_a"]["collection"]
        self.base_url = "https://api.twitterapi.io/twitter"

    def collect(self) -> list[dict]:
        """バイラルツイートを収集"""
        lookback = self.config["lookback_hours"]
        min_likes = self.config["min_likes"]
        max_results = self.config["max_results"]

        since = datetime.now(timezone.utc) - timedelta(hours=lookback)
        since_str = since.strftime("%Y-%m-%dT%H:%M:%SZ")

        logger.info(
            f"Collecting viral tweets: min_likes={min_likes}, since={since_str}"
        )

        params = {
            "query": f"lang:en min_faves:{min_likes} -is:reply -is:quote since:{since_str}",
            "queryType": "Latest",
        }
        headers = {"X-API-Key": self.api_key}

        try:
            response = requests.get(
                f"{self.base_url}/tweet/advanced_search",
                params=params,
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            logger.error(f"TwitterAPI.io request failed: {e}")
            return []

        tweets = data.get("tweets", [])
        logger.info(f"Raw tweets collected: {len(tweets)}")

        processed = []
        for tweet in tweets:
            author = tweet.get("author", {})
            followers = author.get("followers", 1)
            likes = tweet.get("likeCount", 0)
            retweets = tweet.get("retweetCount", 0)
            replies = tweet.get("replyCount", 0)

            engagement_rate = (likes + retweets + replies) / max(followers, 1)

            processed.append({
                "id": tweet.get("id", ""),
                "text": tweet.get("text", ""),
                "author_name": author.get("name", ""),
                "author_username": author.get("userName", ""),
                "followers": followers,
                "likes": likes,
                "retweets": retweets,
                "replies": replies,
                "engagement_rate": round(engagement_rate, 4),
                "created_at": tweet.get("createdAt", ""),
                "language": tweet.get("lang", "en"),
            })

        processed.sort(key=lambda x: x["engagement_rate"], reverse=True)
        top_tweets = processed[:max_results]

        logger.info(f"Top {len(top_tweets)} tweets selected by engagement rate")
        return top_tweets

    def save(self, tweets: list[dict]) -> str:
        """収集結果をJSON保存"""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now(JST).strftime("%Y-%m-%d")
        output_path = DATA_DIR / f"{date_str}.json"

        output = {
            "collected_at": datetime.now(JST).isoformat(),
            "count": len(tweets),
            "tweets": tweets,
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved {len(tweets)} tweets to {output_path}")
        return str(output_path)


def main():
    logging.basicConfig(level=logging.INFO)
    collector = ViralCollector()
    tweets = collector.collect()
    if tweets:
        path = collector.save(tweets)
        print(f"Collected {len(tweets)} viral tweets → {path}")
    else:
        print("No tweets collected")


if __name__ == "__main__":
    main()
