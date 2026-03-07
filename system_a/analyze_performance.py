"""System A - TASK A-6: パフォーマンス分析

投稿済みツイートの成績を自動取得・分析し、勝ちパターンを特定する。
"""

import argparse
import json
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
import yaml
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).parent.parent
REPORTS_DIR = BASE_DIR / "reports" / "system_a"


def load_config() -> dict:
    with open(BASE_DIR / "config" / "config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class PerformanceAnalyzer:
    """X投稿パフォーマンス分析"""

    def __init__(self):
        self.api_key = os.getenv("TWITTERAPI_IO_KEY")
        self.bearer_token = os.getenv("X_BEARER_TOKEN")
        self.config = load_config()

    def get_tweet_metrics(self, tweet_id: str) -> dict:
        """ツイートの指標を取得"""
        if not self.bearer_token:
            logger.warning("X_BEARER_TOKEN not set, using mock data")
            return {
                "likes": 0,
                "retweets": 0,
                "replies": 0,
                "impressions": 0,
                "engagement_rate": 0.0,
            }

        headers = {"Authorization": f"Bearer {self.bearer_token}"}
        url = f"https://api.x.com/2/tweets/{tweet_id}"
        params = {"tweet.fields": "public_metrics"}

        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            metrics = response.json().get("data", {}).get("public_metrics", {})
            total = (
                metrics.get("like_count", 0)
                + metrics.get("retweet_count", 0)
                + metrics.get("reply_count", 0)
            )
            impressions = metrics.get("impression_count", 1)
            return {
                "likes": metrics.get("like_count", 0),
                "retweets": metrics.get("retweet_count", 0),
                "replies": metrics.get("reply_count", 0),
                "impressions": impressions,
                "engagement_rate": round(total / max(impressions, 1), 4),
            }
        except requests.RequestException as e:
            logger.error(f"Failed to get metrics for {tweet_id}: {e}")
            return {}

    def analyze_by_pattern(self, posts: list[dict]) -> dict:
        """パターン別(A/B/C)成績比較"""
        pattern_stats = defaultdict(lambda: {"count": 0, "total_engagement": 0.0})
        for post in posts:
            key = post.get("pattern_key", "unknown")
            pattern_stats[key]["count"] += 1
            pattern_stats[key]["total_engagement"] += post.get("engagement_rate", 0)

        for key in pattern_stats:
            count = pattern_stats[key]["count"]
            if count > 0:
                pattern_stats[key]["avg_engagement"] = round(
                    pattern_stats[key]["total_engagement"] / count, 4
                )

        return dict(pattern_stats)

    def analyze_by_pillar(self, posts: list[dict]) -> dict:
        """柱別(1-5)成績比較"""
        pillar_stats = defaultdict(lambda: {"count": 0, "total_engagement": 0.0})
        for post in posts:
            key = post.get("pillar", 0)
            pillar_stats[key]["count"] += 1
            pillar_stats[key]["total_engagement"] += post.get("engagement_rate", 0)

        for key in pillar_stats:
            count = pillar_stats[key]["count"]
            if count > 0:
                pillar_stats[key]["avg_engagement"] = round(
                    pillar_stats[key]["total_engagement"] / count, 4
                )

        return dict(pillar_stats)

    def check_pillar_ratio(self, posts: list[dict]) -> dict:
        """柱別投稿比率の実績 vs 目標"""
        target = self.config["system_a"]["pillar_ratios"]
        total = len(posts) if posts else 1

        actual = defaultdict(int)
        for post in posts:
            actual[post.get("pillar", 0)] += 1

        result = {}
        for pillar in range(1, 6):
            target_pct = target.get(pillar, 0)
            actual_pct = actual[pillar] / total
            result[pillar] = {
                "target": target_pct,
                "actual": round(actual_pct, 3),
                "deviation": round(actual_pct - target_pct, 3),
            }

        return result

    def generate_weekly_report(self, posts: list[dict]) -> str:
        """週次レポートをMarkdownで生成"""
        pattern_analysis = self.analyze_by_pattern(posts)
        pillar_analysis = self.analyze_by_pillar(posts)
        pillar_ratio = self.check_pillar_ratio(posts)

        date_str = datetime.now(JST).strftime("%Y-%m-%d")
        report = f"# System A 週次パフォーマンスレポート\n\n"
        report += f"**期間:** {date_str} 週\n"
        report += f"**総投稿数:** {len(posts)}\n\n"

        report += "## パターン別成績\n\n"
        report += "| パターン | 投稿数 | 平均ER |\n|---|---|---|\n"
        for key, stats in pattern_analysis.items():
            report += f"| {key} | {stats['count']} | {stats.get('avg_engagement', 0):.4f} |\n"

        report += "\n## 柱別成績\n\n"
        report += "| 柱 | 投稿数 | 平均ER |\n|---|---|---|\n"
        for key, stats in sorted(pillar_analysis.items()):
            report += f"| 柱{key} | {stats['count']} | {stats.get('avg_engagement', 0):.4f} |\n"

        report += "\n## 柱別比率（実績 vs 目標）\n\n"
        report += "| 柱 | 目標 | 実績 | 乖離 |\n|---|---|---|---|\n"
        for pillar, data in sorted(pillar_ratio.items()):
            report += (
                f"| 柱{pillar} | {data['target']:.0%} | "
                f"{data['actual']:.1%} | {data['deviation']:+.1%} |\n"
            )

        return report

    def save_weekly_report(self, report: str) -> str:
        """週次レポートを保存"""
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now(JST).strftime("%Y-%m-%d")
        output_path = REPORTS_DIR / f"weekly_{date_str}.md"

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report)

        logger.info(f"Weekly report saved: {output_path}")
        return str(output_path)


def load_posts_from_sheets(days: int = 7) -> list[dict]:
    """Google Sheetsから投稿データを取得"""
    from core.sheets_client import SheetsClient

    sheets = SheetsClient()
    if not sheets.available:
        logger.warning("Sheets not available, trying local schedule files")
        return load_posts_from_local(days)

    try:
        records = sheets.get_post_performance(days=days)
        posts = []
        for r in records:
            posts.append({
                "pattern_key": r.get("pattern", r.get("pattern_key", "unknown")),
                "pillar": r.get("pillar", 0),
                "text": r.get("text", ""),
                "quality_score": r.get("quality_score", 0),
                "tweet_id": r.get("tweet_id", ""),
                "status": r.get("status", ""),
                "engagement_rate": r.get("engagement_rate", 0.0),
            })
        logger.info(f"Loaded {len(posts)} posts from Sheets")
        return posts
    except Exception as e:
        logger.error(f"Failed to load from Sheets: {e}")
        return load_posts_from_local(days)


def load_posts_from_local(days: int = 7) -> list[dict]:
    """ローカルスケジュールファイルから投稿データを取得（フォールバック）"""
    scheduled_dir = BASE_DIR / "data" / "system_a" / "scheduled"
    if not scheduled_dir.exists():
        logger.warning(f"Scheduled dir not found: {scheduled_dir}")
        return []

    posts = []
    now = datetime.now(JST)
    for i in range(days):
        date = now - timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        file_path = scheduled_dir / f"{date_str}.json"
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for post in data.get("posts", []):
                    if post.get("status") == "posted":
                        posts.append(post)
            except Exception as e:
                logger.error(f"Failed to load {file_path}: {e}")

    logger.info(f"Loaded {len(posts)} posts from local schedule files")
    return posts


def main():
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--weekly", action="store_true", help="Generate weekly report")
    parser.add_argument("--days", type=int, default=7, help="Number of days to analyze")
    parser.add_argument("--fetch-metrics", action="store_true",
                        help="Fetch live metrics from X API for each tweet")
    args = parser.parse_args()

    analyzer = PerformanceAnalyzer()

    # Sheetsから投稿データを取得（フォールバック: ローカルJSONファイル）
    posts = load_posts_from_sheets(days=args.days)

    if not posts:
        logger.warning("No posts found. Nothing to analyze.")
        print("No posts found for analysis.")
        return

    # X APIからメトリクスを取得（オプション）
    if args.fetch_metrics:
        print(f"Fetching metrics for {len(posts)} posts...")
        for post in posts:
            tweet_id = post.get("tweet_id", "")
            if tweet_id:
                metrics = analyzer.get_tweet_metrics(tweet_id)
                post.update(metrics)
        print("Metrics fetched.")

    if args.weekly:
        report = analyzer.generate_weekly_report(posts)
        path = analyzer.save_weekly_report(report)
        print(f"Weekly report generated → {path}")
    else:
        # 日次サマリーを表示
        print(f"\n=== Daily Performance Summary ===")
        print(f"Posts analyzed: {len(posts)}")
        pattern_analysis = analyzer.analyze_by_pattern(posts)
        for key, stats in pattern_analysis.items():
            print(f"  Pattern {key}: {stats['count']} posts, "
                  f"avg ER: {stats.get('avg_engagement', 0):.4f}")
        print("Daily performance analysis completed")


if __name__ == "__main__":
    main()
