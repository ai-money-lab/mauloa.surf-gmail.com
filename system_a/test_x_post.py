"""Quick test script for X API connection.

Usage:
    python -m system_a.test_x_post
"""

import logging
import sys

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main():
    from system_a.auto_post import AutoPoster

    poster = AutoPoster()

    # Check keys are set
    keys = {
        "X_API_KEY": poster.api_key,
        "X_API_SECRET_KEY": poster.api_secret,
        "X_ACCESS_TOKEN": poster.access_token,
        "X_ACCESS_TOKEN_SECRET": poster.access_secret,
        "X_BEARER_TOKEN": poster.bearer_token,
    }

    missing = [k for k, v in keys.items() if not v]
    if missing:
        logger.error("Missing keys: %s", ", ".join(missing))
        sys.exit(1)

    logger.info("All 5 API keys are set ✓")

    # Test post
    logger.info("Posting test tweet...")
    try:
        result = poster.post_tweet("🏠 mauloa.surf AIシステム テスト投稿です")
        tweet_id = result.get("data", {}).get("id")
        logger.info("Success! Tweet ID: %s", tweet_id)
        logger.info("URL: https://x.com/HirokiMiyao/status/%s", tweet_id)
    except Exception as e:
        logger.error("Failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
