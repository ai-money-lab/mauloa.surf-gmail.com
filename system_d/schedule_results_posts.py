"""System D - TASK D-2: 投稿スケジュール統合

System Dの実績投稿をSystem Aの投稿スケジュールにマージする。
System Aの3枠（7:00/12:00/19:00）のうち1枠をSystem D投稿で置き換える。
"""

import json
import logging
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv(_ROOT / ".env", override=True)

import yaml

from core.notifier import Notifier

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).parent.parent
SCHEDULED_DIR = BASE_DIR / "data" / "system_a" / "scheduled"


def load_config() -> dict:
    with open(BASE_DIR / "config" / "config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class ResultsPostScheduler:
    """実績投稿のスケジュール統合"""

    def __init__(self):
        self.config = load_config()
        self.system_d_config = self.config["system_d"]
        self.system_a_config = self.config["system_a"]
        self.notifier = Notifier()

    def load_results_posts(self, date_str: str | None = None) -> list[dict]:
        """生成済みの実績投稿を読み込む"""
        if date_str is None:
            date_str = datetime.now(JST).strftime("%Y-%m-%d")

        file_path = BASE_DIR / "data" / "system_d" / f"results_posts_{date_str}.json"
        if not file_path.exists():
            logger.info(f"No results posts found: {file_path}")
            return []

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("posts", [])

    def load_system_a_schedule(self, date_str: str | None = None) -> dict:
        """System Aのスケジュールファイルを読み込む"""
        if date_str is None:
            date_str = datetime.now(JST).strftime("%Y-%m-%d")

        file_path = SCHEDULED_DIR / f"{date_str}.json"
        if not file_path.exists():
            logger.warning(f"System A schedule not found: {file_path}")
            return {"posts": []}

        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def inject_results_post(
        self, schedule_data: dict, results_posts: list[dict], date_str: str | None = None
    ) -> dict:
        """System Aのスケジュールに1本のSystem D投稿を挿入

        戦略: 12:00枠をSystem D投稿で置き換える（柱3:投資 or 柱5:テック）
        """
        if date_str is None:
            date_str = datetime.now(JST).strftime("%Y-%m-%d")

        if not results_posts:
            logger.info("No results posts to inject")
            return schedule_data

        posts = schedule_data.get("posts", [])

        # 今週すでにSystem D投稿を何本使ったかチェック
        weekly_limit = self.system_d_config.get("results_posts_per_week", 4)
        week_start = self._get_week_start(date_str)
        used_this_week = self._count_weekly_results_posts(week_start, date_str)

        if used_this_week >= weekly_limit:
            logger.info(f"Weekly limit reached ({used_this_week}/{weekly_limit})")
            return schedule_data

        # ターゲット柱でフィルタ
        target_pillars = self.system_d_config.get("target_pillars", [3, 5])
        candidates = [
            p for p in results_posts
            if p.get("pillar") in target_pillars
        ]

        if not candidates:
            candidates = results_posts[:1]

        if not candidates:
            return schedule_data

        # 最初の候補を使用
        result_post = candidates[0]

        # System Aと同じフォーマットに整形
        scheduled_post = {
            "text": result_post.get("text", ""),
            "is_thread": result_post.get("is_thread", False),
            "thread_texts": result_post.get("thread_texts", []),
            "pillar": result_post.get("pillar", 0),
            "quality_score": result_post.get("quality_score", 0),
            "quality_result": "auto_approved",
            "pattern_key": "D",
            "source": "system_d",
            "type": result_post.get("type", "実績"),
            "scheduled_time": f"{date_str}T12:00:00+09:00",
            "status": "scheduled",
            "created_at": datetime.now(JST).isoformat(),
        }

        # 12:00枠のSystem A投稿を探して置き換え
        replaced = False
        for i, post in enumerate(posts):
            if "T12:00" in post.get("scheduled_time", "") and post.get("status") == "scheduled":
                logger.info(
                    f"Replacing 12:00 slot (pillar {post.get('pillar')}) "
                    f"with System D post (pillar {scheduled_post['pillar']})"
                )
                posts[i] = scheduled_post
                replaced = True
                break

        if not replaced:
            # 12:00枠がなければ追加
            posts.append(scheduled_post)
            logger.info("No 12:00 slot found, appending System D post")

        schedule_data["posts"] = posts
        schedule_data["updated_at"] = datetime.now(JST).isoformat()
        return schedule_data

    def save_schedule(self, schedule_data: dict, date_str: str | None = None):
        """更新されたスケジュールを保存"""
        if date_str is None:
            date_str = datetime.now(JST).strftime("%Y-%m-%d")

        SCHEDULED_DIR.mkdir(parents=True, exist_ok=True)
        file_path = SCHEDULED_DIR / f"{date_str}.json"

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(schedule_data, f, ensure_ascii=False, indent=2)

        logger.info(f"Updated schedule saved: {file_path}")

    def _get_week_start(self, date_str: str) -> str:
        """月曜日の日付を取得"""
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        monday = dt - timedelta(days=dt.weekday())
        return monday.strftime("%Y-%m-%d")

    def _count_weekly_results_posts(self, week_start: str, current_date: str) -> int:
        """今週のSystem D投稿数をカウント"""
        count = 0
        start = datetime.strptime(week_start, "%Y-%m-%d")

        for day_offset in range(7):
            day = start + timedelta(days=day_offset)
            day_str = day.strftime("%Y-%m-%d")
            if day_str > current_date:
                break

            file_path = SCHEDULED_DIR / f"{day_str}.json"
            if not file_path.exists():
                continue

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for post in data.get("posts", []):
                    if post.get("source") == "system_d" and post.get("status") in ("scheduled", "posted"):
                        count += 1
            except Exception:
                continue

        return count


def main():
    logging.basicConfig(level=logging.INFO)
    scheduler = ResultsPostScheduler()

    date_str = datetime.now(JST).strftime("%Y-%m-%d")

    # System D投稿を読み込む
    results_posts = scheduler.load_results_posts(date_str)
    if not results_posts:
        print("No results posts available")
        return

    # System Aスケジュールを読み込む
    schedule = scheduler.load_system_a_schedule(date_str)

    # System D投稿を注入
    updated = scheduler.inject_results_post(schedule, results_posts, date_str)

    # 保存
    scheduler.save_schedule(updated, date_str)

    # 結果表示
    d_count = sum(1 for p in updated.get("posts", []) if p.get("source") == "system_d")
    total = len(updated.get("posts", []))
    print(f"Schedule updated: {total} posts ({d_count} from System D)")

    for post in updated.get("posts", []):
        src = post.get("source", "system_a")
        time = post.get("scheduled_time", "?")
        pillar = post.get("pillar", "?")
        print(f"  [{time[-14:-6]}] pillar={pillar} source={src} status={post.get('status')}")


if __name__ == "__main__":
    main()
