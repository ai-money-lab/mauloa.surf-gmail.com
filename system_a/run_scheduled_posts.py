"""スケジュール済み投稿の実行スクリプト

Windowsタスクスケジューラから 7:00 / 12:00 / 19:00 に呼び出される。
当日のスケジュールファイルを読み込み、該当時刻の投稿を1件実行する。

Usage:
    python system_a/run_scheduled_posts.py
    python system_a/run_scheduled_posts.py --force  # 時刻チェックをスキップ
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

load_dotenv(_ROOT / ".env", override=True)

from core.notifier import Notifier
from core.sheets_client import SheetsClient
from system_a.auto_post import AutoPoster

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).parent.parent
SCHEDULED_DIR = BASE_DIR / "data" / "system_a" / "scheduled"
LOGS_DIR = BASE_DIR / "logs"


def load_scheduled_posts(date_str: str | None = None) -> list[dict]:
    """当日のスケジュールファイルを読み込む"""
    if date_str is None:
        date_str = datetime.now(JST).strftime("%Y-%m-%d")

    file_path = SCHEDULED_DIR / f"{date_str}.json"
    if not file_path.exists():
        logger.warning(f"Scheduled file not found: {file_path}")
        return []

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data.get("posts", [])


def get_current_time_slot() -> str | None:
    """現在の時刻に対応する投稿スロットを取得

    許容幅: スケジュール時刻の ±1.5時間
    - 05:30 ~ 08:29 → "07:00"
    - 10:30 ~ 13:29 → "12:00"
    - 17:30 ~ 20:29 → "19:00"
    """
    now = datetime.now(JST)
    hour = now.hour
    minute = now.minute
    t = hour + minute / 60

    if 5.5 <= t < 8.5:
        return "07:00"
    elif 10.5 <= t < 13.5:
        return "12:00"
    elif 17.5 <= t < 20.5:
        return "19:00"
    else:
        logger.warning(f"Current time {now.strftime('%H:%M')} not in posting window")
        return None


def save_updated_schedule(posts: list[dict], date_str: str | None = None):
    """更新されたスケジュールを保存"""
    if date_str is None:
        date_str = datetime.now(JST).strftime("%Y-%m-%d")

    SCHEDULED_DIR.mkdir(parents=True, exist_ok=True)
    file_path = SCHEDULED_DIR / f"{date_str}.json"

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "updated_at": datetime.now(JST).isoformat(),
                "posts": posts,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    logger.info(f"Updated schedule saved: {file_path}")


def run_scheduled_posts(force: bool = False):
    """スケジュール済み投稿を実行"""
    notifier = Notifier()
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    now = datetime.now(JST)
    logger.info("=" * 60)
    logger.info(f"Scheduled post execution: {now.isoformat()}")
    logger.info("=" * 60)

    # 現在時刻のスロットを取得
    if force:
        # --force: 最初の未投稿を実行
        time_slot = None
        logger.info("Force mode: will post first available scheduled post")
    else:
        time_slot = get_current_time_slot()
        if not time_slot:
            logger.error("Not in valid posting time window. Use --force to override.")
            return

    # スケジュールファイルを読み込む
    scheduled_posts = load_scheduled_posts()
    if not scheduled_posts:
        logger.warning("No scheduled posts found for today")
        return

    # 該当時刻の投稿を抽出
    today = datetime.now(JST).strftime("%Y-%m-%d")
    target_post = None

    if force:
        # --force: 最初の status="scheduled" を選択
        for post in scheduled_posts:
            if post.get("status") == "scheduled":
                target_post = post
                break
    else:
        target_time_str = f"{today}T{time_slot}:00+09:00"
        for post in scheduled_posts:
            if (post.get("scheduled_time") == target_time_str
                    and post.get("status") == "scheduled"):
                target_post = post
                break

    if not target_post:
        slot_info = time_slot or "any"
        logger.info(f"No pending post for slot {slot_info}")
        return

    # Sheetsから最新テキストを取得（手動編集の反映）
    sheets = SheetsClient()
    sheet_row = target_post.get("sheet_row")
    if sheet_row and sheets.available:
        sheet_data = sheets.get_scheduled_post_text(sheet_row)
        if sheet_data:
            if sheet_data["status"] == "skip":
                logger.info(f"Post skipped via Sheets (row {sheet_row})")
                target_post["status"] = "skipped"
                target_post["skip_reason"] = "Sheetsからスキップ指示"
                save_updated_schedule(scheduled_posts)
                return

            sheet_text = sheet_data["text"].strip()
            original_text = target_post.get("text", "").strip()
            if sheet_text and sheet_text != original_text:
                logger.info(f"Text updated from Sheets (row {sheet_row})")
                logger.info(f"  Before: {original_text[:60]}...")
                logger.info(f"  After:  {sheet_text[:60]}...")
                target_post["text"] = sheet_text
                target_post["edited_via_sheets"] = True

    # 投稿実行
    logger.info(
        f"Posting: pattern={target_post.get('pattern_key')} "
        f"pillar={target_post.get('pillar')} "
        f"score={target_post.get('quality_score')}"
    )

    poster = AutoPoster()
    result = poster.post_to_x(target_post)

    if result.get("success"):
        tweet_ids = result.get("tweet_ids", [])
        message = (
            f"【X投稿成功】\n"
            f"時刻: {now.strftime('%H:%M')}\n"
            f"Tweet ID: {tweet_ids[0] if tweet_ids else '?'}\n"
            f"Pattern: {target_post.get('pattern_key', '?')}\n"
            f"柱: {target_post.get('pillar', '?')}\n"
            f"品質: {target_post.get('quality_score', 0)}pt\n"
            f"本文: {target_post.get('text', '')[:80]}..."
        )
        notifier.notify(message)
        logger.info(message)

        # ステータス更新
        target_post["status"] = "posted"
        target_post["posted_at"] = now.isoformat()
        target_post["tweet_ids"] = tweet_ids
        save_updated_schedule(scheduled_posts)

        # Sheetsのステータスも更新
        if sheet_row and sheets.available:
            sheets.update_post_status(
                sheet_row, "posted",
                tweet_id=tweet_ids[0] if tweet_ids else "",
                posted_at=now.isoformat(),
            )

    else:
        error = result.get("error", "Unknown")
        error_msg = (
            f"【X投稿失敗】\n"
            f"時刻: {now.strftime('%H:%M')}\n"
            f"エラー: {error}\n"
            f"Pattern: {target_post.get('pattern_key', '?')}\n"
            f"柱: {target_post.get('pillar', '?')}"
        )
        notifier.notify(error_msg)
        logger.error(error_msg)

        # 失敗ステータスを記録
        target_post["status"] = "failed"
        target_post["error"] = error
        save_updated_schedule(scheduled_posts)

        # Sheetsのステータスも更新
        if sheet_row and sheets.available:
            sheets.update_post_status(sheet_row, "failed")


def main():
    parser = argparse.ArgumentParser(description="Execute scheduled X posts")
    parser.add_argument(
        "--force", action="store_true",
        help="Skip time slot check, post first available scheduled post",
    )
    args = parser.parse_args()

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / f"post_{datetime.now(JST).strftime('%Y%m%d')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[
            logging.FileHandler(str(log_file), encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

    run_scheduled_posts(force=args.force)


if __name__ == "__main__":
    main()
