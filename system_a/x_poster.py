"""X投稿クライアント（tweepy v2）

tweepy を使用してX API v2経由で投稿する。
- 単一ツイート投稿
- スレッド投稿（reply chain）
"""

import logging
import os
import time
from typing import Optional

import tweepy
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class XPoster:
    """X API v2 投稿クライアント"""

    def __init__(self):
        api_key = os.getenv("X_API_KEY")
        api_secret = os.getenv("X_API_SECRET_KEY")
        access_token = os.getenv("X_ACCESS_TOKEN")
        access_secret = os.getenv("X_ACCESS_TOKEN_SECRET")

        if not all([api_key, api_secret, access_token, access_secret]):
            raise ValueError(
                "X API credentials not fully configured. "
                "Set X_API_KEY, X_API_SECRET_KEY, X_ACCESS_TOKEN, "
                "X_ACCESS_TOKEN_SECRET in .env"
            )

        self.client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_secret,
        )
        logger.info("XPoster initialized with tweepy v2 client")

    def post_single(self, text: str,
                    hashtags: list[str] | None = None) -> Optional[str]:
        """単一ツイートを投稿し、tweet_id を返す"""
        full_text = text
        # ハッシュタグは使わない（Xアルゴリズムでリーチ低下）

        # 280文字制限チェック（日本語は140文字相当）
        if len(full_text) > 280:
            logger.warning(f"Tweet too long ({len(full_text)} chars), truncating")
            full_text = full_text[:277] + "..."

        try:
            response = self.client.create_tweet(text=full_text)
            tweet_id = str(response.data["id"])
            logger.info(f"Posted single tweet: {tweet_id}")
            return tweet_id
        except tweepy.TweepyException as e:
            logger.error(f"Failed to post tweet: {e}")
            return None

    def post_thread(self, thread_texts: list[str],
                    hashtags: list[str] | None = None) -> Optional[list[str]]:
        """スレッド（連続ツイート）を投稿し、全tweet_idのリストを返す"""
        if not thread_texts:
            logger.warning("Empty thread_texts provided")
            return None

        tweet_ids = []
        previous_id = None

        for i, text in enumerate(thread_texts):
            full_text = text
            # ハッシュタグは使わない（Xアルゴリズムでリーチ低下）

            try:
                if previous_id:
                    response = self.client.create_tweet(
                        text=full_text,
                        in_reply_to_tweet_id=previous_id,
                    )
                else:
                    response = self.client.create_tweet(text=full_text)

                tweet_id = str(response.data["id"])
                tweet_ids.append(tweet_id)
                previous_id = tweet_id
                logger.info(
                    f"Posted thread {i + 1}/{len(thread_texts)}: {tweet_id}"
                )

                # レート制限対策（各投稿間に1秒待機）
                if i < len(thread_texts) - 1:
                    time.sleep(1)

            except tweepy.TweepyException as e:
                logger.error(f"Failed to post thread tweet {i + 1}: {e}")
                # 途中まで投稿されたIDは返す
                if tweet_ids:
                    logger.warning(
                        f"Partial thread posted: {len(tweet_ids)}/{len(thread_texts)}"
                    )
                return tweet_ids if tweet_ids else None

        return tweet_ids

    def delete_tweet(self, tweet_id: str) -> bool:
        """ツイートを削除する"""
        try:
            self.client.delete_tweet(tweet_id)
            logger.info(f"Deleted tweet: {tweet_id}")
            return True
        except tweepy.TweepyException as e:
            logger.error(f"Failed to delete tweet {tweet_id}: {e}")
            return False

    def post(self, post_data: dict) -> dict:
        """投稿データから自動判定して投稿する

        Args:
            post_data: {
                "text": str,
                "hashtags": list[str],
                "is_thread": bool,
                "thread_texts": list[str],
            }

        Returns:
            {"success": bool, "tweet_ids": list[str], "error": str | None}
        """
        is_thread = post_data.get("is_thread", False)
        text = post_data.get("text", "")
        thread_texts = post_data.get("thread_texts", [])
        # hashtagsは無視（Xアルゴリズムでリーチ低下のため）

        if is_thread and thread_texts:
            tweet_ids = self.post_thread(thread_texts)
            if tweet_ids:
                return {"success": True, "tweet_ids": tweet_ids, "error": None}
            else:
                return {"success": False, "tweet_ids": [], "error": "Thread post failed"}
        else:
            tweet_id = self.post_single(text)
            if tweet_id:
                return {"success": True, "tweet_ids": [tweet_id], "error": None}
            else:
                return {"success": False, "tweet_ids": [], "error": "Single post failed"}
