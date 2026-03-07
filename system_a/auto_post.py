"""System A - TASK A-5: 自動品質チェック＋投稿

品質チェック → 自動スケジュール → X投稿を実行する。
"""

import json
import logging
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml

from core.quality_checker import QualityChecker
from core.sheets_client import SheetsClient
from core.notifier import Notifier
from system_a.x_poster import XPoster

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).parent.parent
TRANSFORMED_DIR = BASE_DIR / "data" / "system_a" / "transformed"


def load_config() -> dict:
    with open(BASE_DIR / "config" / "config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class AutoPoster:
    """品質チェック付き自動投稿"""

    def __init__(self):
        self.config = load_config()["system_a"]
        self.quality_checker = QualityChecker()
        self.sheets = SheetsClient()
        self.notifier = Notifier()
        self.post_times = self.config["post_times"]
        self._scheduled = []
        self.x_poster = XPoster()

    def load_transformed(self, date_str: str | None = None) -> list[dict]:
        """変換済みツイートを読み込む"""
        if date_str is None:
            date_str = datetime.now(JST).strftime("%Y-%m-%d")

        file_path = TRANSFORMED_DIR / f"{date_str}.json"
        if not file_path.exists():
            logger.error(f"Transformed data not found: {file_path}")
            return []

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("tweets", [])

    def select_best_pattern(self, tweet: dict) -> dict | None:
        """3パターンから最も品質の高いものを選定"""
        patterns = tweet.get("patterns", {})
        best = None
        best_score = -1

        for pattern_key in ["A", "B", "C"]:
            pattern = patterns.get(pattern_key)
            if not pattern:
                continue

            text = pattern.get("text", "")
            if not text:
                continue

            result = self.quality_checker.check(
                profile="x_post",
                content=text,
                context=f"pattern_{pattern_key}_pillar_{tweet.get('pillar', '?')}",
            )

            if result.total_score > best_score:
                best_score = result.total_score
                best = {
                    "pattern_key": pattern_key,
                    "text": text,
                    "hashtags": pattern.get("hashtags", []),
                    "is_thread": pattern.get("is_thread", False),
                    "thread_texts": pattern.get("thread_texts", []),
                    "quality_score": result.total_score,
                    "quality_result": result.result,
                    "pillar": tweet.get("pillar", 0),
                    "original_id": tweet.get("original_id", ""),
                }

        return best

    def process_tweets(self, tweets: list[dict], target_date: str | None = None) -> list[dict]:
        """全ツイートを品質チェック→スケジュール

        Args:
            target_date: 投稿日（YYYY-MM-DD）。23時実行時は翌日。
        """
        approved = []
        skipped = []

        for tweet in tweets:
            best = self.select_best_pattern(tweet)
            if not best:
                logger.warning(f"No valid pattern for tweet {tweet.get('original_id')}")
                continue

            if best["quality_result"] == "auto_approved":
                approved.append(best)
                logger.info(
                    f"Approved: pattern {best['pattern_key']} "
                    f"(score: {best['quality_score']})"
                )
            else:
                improved = self._retry_with_improvement(tweet, best)
                if improved:
                    approved.append(improved)
                else:
                    skipped.append(best)
                    logger.warning(
                        f"Skipped: quality too low (score: {best['quality_score']})"
                    )

        scheduled = self._schedule_posts(approved, target_date)
        return scheduled

    def _retry_with_improvement(self, tweet: dict, original: dict) -> dict | None:
        """品質不足時のリトライ"""
        from core.claude_client import ClaudeClient

        claude = ClaudeClient()
        max_retries = 3

        for attempt in range(max_retries):
            result = self.quality_checker.check(
                profile="x_post",
                content=original["text"],
            )
            if result.result == "auto_approved":
                original["quality_score"] = result.total_score
                original["quality_result"] = "approved_after_retry"
                return original

            suggestions = "\n".join(result.improvement_suggestions)
            prompt = (
                f"以下のX投稿を改善してください。\n\n"
                f"現在のテキスト:\n{original['text']}\n\n"
                f"改善提案:\n{suggestions}\n\n"
                f"改善されたテキストのみ出力してください。"
            )
            try:
                improved_text = claude.generate(prompt, temperature=0.7, max_tokens=500)
                original["text"] = improved_text.strip()
            except Exception as e:
                logger.error(f"Retry generation failed: {e}")

        return None

    def _schedule_posts(self, approved: list[dict], target_date: str | None = None) -> list[dict]:
        """投稿をスケジュール（7:00 / 12:00 / 19:00）

        Args:
            target_date: 投稿日（YYYY-MM-DD）。Noneなら翌日。
        """
        scheduled = []
        if target_date is None:
            # 23時実行を想定：翌日の日付を使用
            now = datetime.now(JST)
            if now.hour >= 20:
                target_date = (now + timedelta(days=1)).strftime("%Y-%m-%d")
            else:
                target_date = now.strftime("%Y-%m-%d")

        for i, post in enumerate(approved[: len(self.post_times)]):
            post_time = self.post_times[i] if i < len(self.post_times) else self.post_times[-1]
            post["scheduled_time"] = f"{target_date}T{post_time}:00+09:00"
            post["status"] = "scheduled"
            post["created_at"] = datetime.now(JST).isoformat()
            scheduled.append(post)

        # Google Sheetsに記録（行番号をJSONに保存）
        for post in scheduled:
            if self.sheets.available:
                row_num = self.sheets.append_post_record(post)
                if row_num:
                    post["sheet_row"] = row_num

        # スケジュールをJSONファイルに保存（sheet_row込み）
        self._save_scheduled(scheduled, target_date)

        return scheduled

    def _save_scheduled(self, scheduled: list[dict], target_date: str | None = None):
        """スケジュールをJSON保存（run_scheduled_posts.pyが読み込む）"""
        scheduled_dir = BASE_DIR / "data" / "system_a" / "scheduled"
        scheduled_dir.mkdir(parents=True, exist_ok=True)

        if target_date is None:
            target_date = datetime.now(JST).strftime("%Y-%m-%d")
        file_path = scheduled_dir / f"{target_date}.json"

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "scheduled_at": datetime.now(JST).isoformat(),
                    "posts": scheduled,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
        logger.info(f"Scheduled posts saved: {file_path}")

    def post_to_x(self, post: dict) -> dict:
        """X投稿実行（tweepy v2使用）

        Returns:
            {"success": bool, "tweet_ids": list, "error": str | None}
        """
        try:
            result = self.x_poster.post(post)

            if result["success"]:
                tweet_ids = result["tweet_ids"]
                logger.info(f"Successfully posted to X: {tweet_ids}")

                # Google Sheetsに投稿記録を更新
                if self.sheets.available:
                    record = {
                        "pillar": post.get("pillar", ""),
                        "pattern_key": post.get("pattern_key", ""),
                        "text": post.get("text", ""),
                        "quality_score": post.get("quality_score", 0),
                        "status": "posted",
                        "tweet_id": tweet_ids[0],
                        "all_tweet_ids": ",".join(tweet_ids),
                        "scheduled_time": post.get("scheduled_time", ""),
                        "posted_at": datetime.now(JST).isoformat(),
                    }
                    self.sheets.append_post_record(record)

                return {
                    "success": True,
                    "tweet_ids": tweet_ids,
                    "error": None,
                }
            else:
                error = result.get("error", "Unknown error")
                logger.error(f"Post failed: {error}")
                return {"success": False, "tweet_ids": [], "error": error}

        except Exception as e:
            logger.error(f"Post error: {e}")
            return {"success": False, "tweet_ids": [], "error": str(e)}


def main():
    logging.basicConfig(level=logging.INFO)
    poster = AutoPoster()

    tweets = poster.load_transformed()
    if not tweets:
        print("No transformed tweets found")
        return

    scheduled = poster.process_tweets(tweets)
    print(f"Scheduled {len(scheduled)} posts")

    for post in scheduled:
        print(f"  [{post['scheduled_time']}] {post['text'][:60]}...")

    poster.notifier.notify(
        f"本日の投稿{len(scheduled)}本がスケジュールされました"
    )


if __name__ == "__main__":
    main()
