"""System D - TASK D-1: 実績データ→投稿変換

System B/Cの成果をX投稿用コンテンツに自動変換する。
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

from core.claude_client import ClaudeClient
from core.quality_checker import QualityChecker
from core.sheets_client import SheetsClient
from core.notifier import Notifier

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).parent.parent


def load_config() -> dict:
    with open(BASE_DIR / "config" / "config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class ResultsContentGenerator:
    """実績→X投稿コンテンツ変換"""

    def __init__(self):
        self.claude = ClaudeClient()
        self.quality_checker = QualityChecker()
        self.sheets = SheetsClient()
        self.notifier = Notifier()
        self.config = load_config()["system_d"]

    def gather_results(self) -> dict:
        """各システムの実績データを収集"""
        results = {
            "order_results": self._get_order_results(),
            "market_insights": self._get_market_insights(),
            "tech_discoveries": self._get_tech_discoveries(),
            "x_performance": self._get_x_performance(),
        }
        return results

    def _get_order_results(self) -> list[dict]:
        """System B: 完了案件の実績データ"""
        if self.sheets.available:
            return self.sheets.get_completed_orders(limit=5)

        # Sheetsが無い場合はローカル案件JSONを探索
        orders_dir = BASE_DIR / "data" / "system_b" / "orders"
        if not orders_dir.exists():
            return []

        results = []
        for f in sorted(orders_dir.glob("*.json"), reverse=True)[:5]:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
                if data.get("status") == "received":
                    results.append(data)
        return results

    def _get_market_insights(self) -> list[dict]:
        """System C: 日次/週次レポートからの発見"""
        daily_dir = BASE_DIR / "data" / "system_c" / "daily"
        if not daily_dir.exists():
            return []

        insights = []
        for f in sorted(daily_dir.glob("*.json"), reverse=True)[:3]:
            with open(f, "r", encoding="utf-8") as fp:
                insights.append(json.load(fp))
        return insights

    def _get_tech_discoveries(self) -> list[dict]:
        """System C: テックトレンドからの発見"""
        weekly_dir = BASE_DIR / "data" / "system_c" / "weekly"
        if not weekly_dir.exists():
            return []

        discoveries = []
        for f in sorted(weekly_dir.glob("*.json"), reverse=True)[:2]:
            with open(f, "r", encoding="utf-8") as fp:
                discoveries.append(json.load(fp))
        return discoveries

    def _get_x_performance(self) -> list[dict]:
        """System A: Xパフォーマンスデータ"""
        if self.sheets.available:
            return self.sheets.get_post_performance(days=7)
        return []

    def generate_posts(self, results: dict) -> list[dict]:
        """実績データからX投稿を生成"""
        prompt = self.claude.load_prompt(
            "results_to_post.txt",
            results_data=json.dumps(results, ensure_ascii=False, indent=2),
        )

        try:
            posts = self.claude.generate_json(prompt, max_tokens=4096, temperature=0.8)
            if isinstance(posts, dict):
                posts = posts.get("posts", [posts])
            return posts
        except Exception as e:
            logger.error(f"Post generation failed: {e}")
            return []

    def quality_check_posts(self, posts: list[dict]) -> list[dict]:
        """生成した投稿を品質チェック"""
        approved = []

        for post in posts:
            text = post.get("text", "")
            if not text:
                continue

            result = self.quality_checker.check(
                profile="x_post",
                content=text,
                context=f"results_post_pillar_{post.get('pillar', '?')}",
            )

            if result.result == "auto_approved":
                post["quality_score"] = result.total_score
                approved.append(post)
            else:
                logger.info(
                    f"Post rejected (score: {result.total_score}): {text[:50]}..."
                )

        return approved

    def save_posts(self, posts: list[dict], target_date: str | None = None) -> str:
        """生成投稿を保存

        Args:
            target_date: 保存する日付（YYYY-MM-DD）。Noneなら自動判定。
        """
        output_dir = BASE_DIR / "data" / "system_d"
        output_dir.mkdir(parents=True, exist_ok=True)

        if target_date is None:
            now = datetime.now(JST)
            if now.hour >= 20:
                target_date = (now + timedelta(days=1)).strftime("%Y-%m-%d")
            else:
                target_date = now.strftime("%Y-%m-%d")
        output_path = output_dir / f"results_posts_{target_date}.json"

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "generated_at": datetime.now(JST).isoformat(),
                    "count": len(posts),
                    "posts": posts,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

        logger.info(f"Results posts saved: {output_path}")
        return str(output_path)


def main():
    logging.basicConfig(level=logging.INFO)
    generator = ResultsContentGenerator()

    results = generator.gather_results()
    logger.info(f"Gathered results from all systems")

    posts = generator.generate_posts(results)
    logger.info(f"Generated {len(posts)} posts")

    approved = generator.quality_check_posts(posts)
    logger.info(f"Approved {len(approved)} posts")

    if approved:
        path = generator.save_posts(approved)
        print(f"Generated {len(approved)} results posts → {path}")

        generator.notifier.notify(
            f"System D: 実績投稿{len(approved)}本を生成しました"
        )
    else:
        print("No posts generated or approved")


if __name__ == "__main__":
    main()
