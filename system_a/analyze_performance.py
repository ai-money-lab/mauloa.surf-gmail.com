"""Performance analysis and pipeline ratio auto-adjustment."""

import argparse
import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
import yaml
from dotenv import load_dotenv
from core.notifier import Notifier

load_dotenv()

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data" / "system_a"
REPORTS_DIR = BASE_DIR / "reports" / "system_a"
CONFIG_PATH = BASE_DIR / "config" / "config.yaml"
WINNING_PATTERNS_PATH = DATA_DIR / "winning_patterns.json"
POSTED_LOG_PATH = DATA_DIR / "posted_tweets.json"


class PerformanceAnalyzer:
    """Analyze post performance and auto-adjust pipeline ratios."""

    def __init__(self):
        self.api_key = os.getenv("TWITTERAPI_IO_KEY", "")
        self.bearer_token = os.getenv("X_BEARER_TOKEN", "")
        self.notifier = Notifier()
        self._load_config()

    def _load_config(self):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                self.config = yaml.safe_load(f)
        except Exception:
            self.config = {}

    def _save_config(self):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.dump(self.config, f, allow_unicode=True, default_flow_style=False)

    def fetch_tweet_metrics(self, tweet_id: str) -> dict:
        """Fetch engagement metrics for a tweet."""
        if not self.bearer_token:
            return {}

        url = f"https://api.x.com/2/tweets/{tweet_id}"
        headers = {"Authorization": f"Bearer {self.bearer_token}"}
        params = {"tweet.fields": "public_metrics"}

        try:
            resp = requests.get(url, headers=headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json().get("data", {})
            metrics = data.get("public_metrics", {})
            return {
                "likes": metrics.get("like_count", 0),
                "retweets": metrics.get("retweet_count", 0),
                "replies": metrics.get("reply_count", 0),
                "impressions": metrics.get("impression_count", 0),
                "engagement_rate": self._calc_engagement_rate(metrics),
            }
        except Exception as e:
            logger.warning("Failed to fetch metrics for %s: %s", tweet_id, e)
            return {}

    def _calc_engagement_rate(self, metrics: dict) -> float:
        impressions = metrics.get("impression_count", 0)
        if impressions == 0:
            return 0.0
        engagement = (
            metrics.get("like_count", 0)
            + metrics.get("retweet_count", 0)
            + metrics.get("reply_count", 0)
        )
        return round(engagement / impressions, 4)

    def analyze_by_pipeline(self, posts: list) -> dict:
        """Analyze performance grouped by pipeline."""
        pipeline_stats = defaultdict(list)
        for post in posts:
            pipeline = post.get("pipeline", "unknown")
            er = post.get("engagement_rate", 0)
            pipeline_stats[pipeline].append(er)

        result = {}
        for pipeline, rates in pipeline_stats.items():
            result[pipeline] = {
                "count": len(rates),
                "avg_engagement_rate": round(sum(rates) / len(rates), 4) if rates else 0,
                "max_engagement_rate": max(rates) if rates else 0,
            }
        return result

    def analyze_by_pillar(self, posts: list) -> dict:
        """Analyze performance grouped by pillar."""
        pillar_stats = defaultdict(list)
        for post in posts:
            pillar = post.get("pillar", 0)
            er = post.get("engagement_rate", 0)
            pillar_stats[pillar].append(er)

        result = {}
        for pillar, rates in pillar_stats.items():
            result[pillar] = {
                "count": len(rates),
                "avg_engagement_rate": round(sum(rates) / len(rates), 4) if rates else 0,
            }
        return result

    def analyze_by_pattern(self, posts: list) -> dict:
        """Analyze performance by pattern (A/B/C)."""
        pattern_stats = defaultdict(list)
        for post in posts:
            pattern = post.get("pattern", "unknown")
            er = post.get("engagement_rate", 0)
            pattern_stats[pattern].append(er)

        result = {}
        for pattern, rates in pattern_stats.items():
            result[pattern] = {
                "count": len(rates),
                "avg_engagement_rate": round(sum(rates) / len(rates), 4) if rates else 0,
            }
        return result

    def auto_adjust_pipeline_ratio(self, pipeline_stats: dict) -> dict:
        """Auto-adjust pipeline ratios based on performance."""
        limits = self.config.get("system_a", {}).get("pipeline_ratio_limits", {})
        min_ratio = limits.get("min_per_pipeline", 15)
        max_ratio = limits.get("max_per_pipeline", 60)
        max_adj = limits.get("weekly_adjustment_max", 10)

        current = self.config.get("system_a", {}).get("pipeline_ratio", {})
        mapping = {
            "P1": "pipeline1_jp_buzz",
            "P2": "pipeline2_data_driven",
            "P3": "pipeline3_ai_original",
        }

        # Rank pipelines by engagement rate
        ranked = sorted(
            pipeline_stats.items(),
            key=lambda x: x[1].get("avg_engagement_rate", 0),
            reverse=True,
        )

        new_ratio = dict(current)
        if len(ranked) >= 2:
            best_key = mapping.get(ranked[0][0])
            worst_key = mapping.get(ranked[-1][0])

            if best_key and worst_key and best_key in new_ratio and worst_key in new_ratio:
                adjustment = min(max_adj, 5)  # Conservative adjustment
                new_best = min(new_ratio[best_key] + adjustment, max_ratio)
                new_worst = max(new_ratio[worst_key] - adjustment, min_ratio)
                new_ratio[best_key] = new_best
                new_ratio[worst_key] = new_worst

                # Normalize to 100%
                total = sum(new_ratio.values())
                if total != 100:
                    diff = 100 - total
                    mid_key = mapping.get(ranked[1][0], best_key)
                    if mid_key in new_ratio:
                        new_ratio[mid_key] += diff

        # Update config
        if "system_a" not in self.config:
            self.config["system_a"] = {}
        self.config["system_a"]["pipeline_ratio"] = new_ratio
        self._save_config()

        logger.info("Pipeline ratio adjusted: %s", new_ratio)
        return new_ratio

    def update_winning_patterns(self, posts: list) -> None:
        """Accumulate winning patterns from high-performing posts."""
        winning = []
        for post in posts:
            if post.get("engagement_rate", 0) > 0.05:  # 5%+ engagement
                winning.append({
                    "pipeline": post.get("pipeline"),
                    "pillar": post.get("pillar"),
                    "pattern": post.get("pattern"),
                    "engagement_rate": post.get("engagement_rate"),
                    "text_preview": post.get("text", "")[:100],
                    "date": datetime.now(JST).isoformat(),
                })

        existing = []
        if WINNING_PATTERNS_PATH.exists():
            try:
                existing = json.loads(WINNING_PATTERNS_PATH.read_text(encoding="utf-8"))
            except Exception:
                pass

        existing.extend(winning)
        # Keep last 200 entries
        existing = existing[-200:]

        WINNING_PATTERNS_PATH.parent.mkdir(parents=True, exist_ok=True)
        WINNING_PATTERNS_PATH.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def generate_report(self, posts: list, report_type: str = "daily") -> str:
        """Generate performance report in Markdown."""
        now = datetime.now(JST)
        date_str = now.strftime("%Y-%m-%d")

        pipeline_stats = self.analyze_by_pipeline(posts)
        pillar_stats = self.analyze_by_pillar(posts)
        pattern_stats = self.analyze_by_pattern(posts)

        report = f"# System A パフォーマンスレポート ({report_type})\n\n"
        report += f"日付: {date_str}\n\n"
        report += "## パイプライン別成績\n\n"
        report += "| Pipeline | 投稿数 | 平均ER | 最高ER |\n"
        report += "|----------|--------|--------|--------|\n"
        for p, s in pipeline_stats.items():
            report += f"| {p} | {s['count']} | {s['avg_engagement_rate']:.4f} | {s.get('max_engagement_rate', 0):.4f} |\n"

        report += "\n## 柱別成績\n\n"
        report += "| 柱 | 投稿数 | 平均ER |\n"
        report += "|----|--------|--------|\n"
        for p, s in pillar_stats.items():
            report += f"| {p} | {s['count']} | {s['avg_engagement_rate']:.4f} |\n"

        report += "\n## パターン別成績\n\n"
        report += "| Pattern | 投稿数 | 平均ER |\n"
        report += "|---------|--------|--------|\n"
        for p, s in pattern_stats.items():
            report += f"| {p} | {s['count']} | {s['avg_engagement_rate']:.4f} |\n"

        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        report_path = REPORTS_DIR / f"{report_type}_{date_str}.md"
        report_path.write_text(report, encoding="utf-8")
        logger.info("Report saved: %s", report_path)
        return str(report_path)

    def _load_posts(self, days: int = 1) -> list:
        """Load posted tweets from local log, filtered by recent N days."""
        if not POSTED_LOG_PATH.exists():
            logger.info("No posted tweets log found at %s", POSTED_LOG_PATH)
            return []

        try:
            all_posts = json.loads(POSTED_LOG_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("Failed to read posted tweets log: %s", e)
            return []

        cutoff = datetime.now(JST) - timedelta(days=days)
        filtered = []
        for post in all_posts:
            try:
                posted_at = datetime.fromisoformat(post["datetime"])
                if posted_at >= cutoff:
                    filtered.append(post)
            except (KeyError, ValueError):
                continue

        logger.info("Loaded %d posts from last %d day(s)", len(filtered), days)
        return filtered

    def _enrich_with_metrics(self, posts: list) -> list:
        """Fetch X API metrics for each post and merge into post data."""
        enriched = []
        for post in posts:
            tweet_id = post.get("tweet_id", "")
            if tweet_id:
                metrics = self.fetch_tweet_metrics(tweet_id)
                post.update(metrics)
            enriched.append(post)
        return enriched

    def generate_insights(self, posts: list, report_type: str = "daily") -> str:
        """Generate actionable insights from performance data and notify via LINE."""
        if not posts:
            return "投稿データなし"

        pipeline_stats = self.analyze_by_pipeline(posts)
        pillar_stats = self.analyze_by_pillar(posts)

        # Find best/worst performing
        total_likes = sum(p.get("likes", 0) for p in posts)
        total_rts = sum(p.get("retweets", 0) for p in posts)
        total_replies = sum(p.get("replies", 0) for p in posts)
        total_impressions = sum(p.get("impressions", 0) for p in posts)
        post_count = len(posts)

        # Best post
        best = max(posts, key=lambda p: p.get("likes", 0) + p.get("retweets", 0), default=None)

        # Image vs no-image comparison
        with_image = [p for p in posts if p.get("has_image")]
        without_image = [p for p in posts if not p.get("has_image")]
        img_avg_likes = sum(p.get("likes", 0) for p in with_image) / len(with_image) if with_image else 0
        no_img_avg_likes = sum(p.get("likes", 0) for p in without_image) / len(without_image) if without_image else 0

        insight_lines = [
            f"📊 {report_type.upper()} 分析レポート",
            f"投稿数: {post_count}",
            f"合計: ❤️{total_likes} 🔄{total_rts} 💬{total_replies} 👁{total_impressions}",
        ]

        if best and (best.get("likes", 0) + best.get("retweets", 0)) > 0:
            insight_lines.append(f"\n🏆 最高: {best.get('text', '')[:50]}...")
            insight_lines.append(f"  ❤️{best.get('likes', 0)} 🔄{best.get('retweets', 0)}")

        if with_image and without_image:
            insight_lines.append(f"\n🖼 画像あり平均❤️{img_avg_likes:.1f} vs なし❤️{no_img_avg_likes:.1f}")

        if total_impressions == 0 and post_count > 0:
            insight_lines.append("\n⚠️ インプレッション0 → フォロワー増加施策が必要")
            insight_lines.append("推奨: 不動産系アカウントにリプライ交流を開始")

        insights = "\n".join(insight_lines)

        # Send LINE notification
        try:
            self.notifier.send_line(insights)
        except Exception as e:
            logger.warning("Failed to send insights via LINE: %s", e)

        # Save insights to file
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        now = datetime.now(JST)
        path = REPORTS_DIR / f"insights_{report_type}_{now.strftime('%Y-%m-%d')}.txt"
        path.write_text(insights, encoding="utf-8")
        logger.info("Insights saved: %s", path)

        return insights

    def run_daily(self) -> None:
        """Run daily analysis."""
        logger.info("Running daily performance analysis...")
        posts = self._load_posts(days=1)
        posts = self._enrich_with_metrics(posts)
        if posts:
            self.generate_report(posts, "daily")
            self.update_winning_patterns(posts)
            self.generate_insights(posts, "daily")
        else:
            logger.info("No posts found for daily analysis")

    def run_weekly(self) -> None:
        """Run weekly analysis with ratio adjustment."""
        logger.info("Running weekly performance analysis...")
        posts = self._load_posts(days=7)
        posts = self._enrich_with_metrics(posts)
        if posts:
            pipeline_stats = self.analyze_by_pipeline(posts)
            self.auto_adjust_pipeline_ratio(pipeline_stats)
            self.generate_report(posts, "weekly")
            self.update_winning_patterns(posts)
            self.generate_insights(posts, "weekly")
        else:
            logger.info("No posts found for weekly analysis")


def main():
    parser = argparse.ArgumentParser(description="Performance Analyzer")
    parser.add_argument("--weekly", action="store_true", help="Run weekly analysis")
    args = parser.parse_args()

    analyzer = PerformanceAnalyzer()
    if args.weekly:
        analyzer.run_weekly()
    else:
        analyzer.run_daily()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
