"""System E — Analytics & Performance Tracker.

Tracks engagement, revenue metrics, and content performance
for optimization of the AI content pipeline.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
ANALYTICS_DIR = Path(__file__).parent.parent / "data" / "system_e" / "analytics"
POSTED_LOG = Path(__file__).parent.parent / "data" / "system_e" / "posted_log.json"


class Analytics:
    """Track and analyze System E performance metrics."""

    def __init__(self):
        ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)

    def record_engagement(self, tweet_id: str, metrics: dict) -> None:
        """Record engagement metrics for a posted tweet.

        Args:
            tweet_id: The X tweet ID.
            metrics: Dict with 'likes', 'retweets', 'replies', 'impressions', etc.
        """
        daily_file = self._get_daily_file()
        existing = self._load_json(daily_file)

        record = {
            "tweet_id": tweet_id,
            "recorded_at": datetime.now(JST).isoformat(),
            **metrics,
        }
        existing.append(record)
        self._save_json(daily_file, existing)

    def get_daily_summary(self, date: str | None = None) -> dict:
        """Generate a daily performance summary.

        Args:
            date: Target date (YYYY-MM-DD). Defaults to today.

        Returns:
            Dict with aggregated daily metrics.
        """
        if not date:
            date = datetime.now(JST).strftime("%Y-%m-%d")

        daily_file = ANALYTICS_DIR / f"engagement_{date}.json"
        data = self._load_json(daily_file)

        if not data:
            return {"date": date, "posts": 0, "message": "No data for this date"}

        total_likes = sum(d.get("likes", 0) for d in data)
        total_retweets = sum(d.get("retweets", 0) for d in data)
        total_replies = sum(d.get("replies", 0) for d in data)
        total_impressions = sum(d.get("impressions", 0) for d in data)

        engagement_rate = 0.0
        if total_impressions > 0:
            engagement_rate = (total_likes + total_retweets + total_replies) / total_impressions * 100

        return {
            "date": date,
            "posts": len(data),
            "total_likes": total_likes,
            "total_retweets": total_retweets,
            "total_replies": total_replies,
            "total_impressions": total_impressions,
            "engagement_rate": round(engagement_rate, 2),
            "avg_likes_per_post": round(total_likes / len(data), 1) if data else 0,
        }

    def get_weekly_report(self) -> dict:
        """Generate a weekly performance report."""
        now = datetime.now(JST)
        days = []
        for i in range(7):
            date = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            days.append(self.get_daily_summary(date))

        total_posts = sum(d.get("posts", 0) for d in days)
        total_likes = sum(d.get("total_likes", 0) for d in days)
        total_impressions = sum(d.get("total_impressions", 0) for d in days)

        return {
            "period": f"{days[-1]['date']} to {days[0]['date']}",
            "total_posts": total_posts,
            "total_likes": total_likes,
            "total_impressions": total_impressions,
            "avg_engagement_rate": round(
                sum(d.get("engagement_rate", 0) for d in days if d.get("posts", 0) > 0)
                / max(1, sum(1 for d in days if d.get("posts", 0) > 0)),
                2,
            ),
            "best_day": max(days, key=lambda d: d.get("total_likes", 0)).get("date", ""),
            "daily_breakdown": days,
        }

    def get_content_type_performance(self) -> dict:
        """Analyze performance by content type (standard, story, engagement, promo).

        Returns:
            Dict mapping content type to average engagement metrics.
        """
        posted = self._load_json(POSTED_LOG)
        if not posted:
            return {}

        by_type = {}
        for item in posted:
            ctype = item.get("type", "standard")
            if ctype not in by_type:
                by_type[ctype] = {"count": 0, "total_likes": 0, "total_impressions": 0}
            by_type[ctype]["count"] += 1

        return by_type

    def get_scene_performance(self) -> dict:
        """Analyze performance by scene category.

        Returns:
            Dict mapping scene to post count and engagement.
        """
        posted = self._load_json(POSTED_LOG)
        if not posted:
            return {}

        by_scene = {}
        for item in posted:
            scene = item.get("scene", "unknown")
            if scene not in by_scene:
                by_scene[scene] = {"count": 0}
            by_scene[scene]["count"] += 1

        return by_scene

    def get_posting_time_performance(self) -> dict:
        """Analyze which posting times get the best engagement.

        Returns:
            Dict mapping hour (JST) to engagement metrics.
        """
        posted = self._load_json(POSTED_LOG)
        if not posted:
            return {}

        by_hour = {}
        for item in posted:
            time_str = item.get("time", "")
            if not time_str:
                continue
            try:
                hour = time_str.split(":")[0]
                if hour not in by_hour:
                    by_hour[hour] = {"count": 0}
                by_hour[hour]["count"] += 1
            except (ValueError, IndexError):
                pass

        return by_hour

    def record_revenue(self, source: str, amount: float, currency: str = "USD") -> None:
        """Record a revenue event.

        Args:
            source: Revenue source (e.g., 'x_ad_revenue', 'fanvue', 'affiliate', 'brand_deal').
            amount: Revenue amount.
            currency: Currency code.
        """
        revenue_file = ANALYTICS_DIR / "revenue_log.json"
        existing = self._load_json(revenue_file)

        record = {
            "date": datetime.now(JST).strftime("%Y-%m-%d"),
            "source": source,
            "amount": amount,
            "currency": currency,
            "recorded_at": datetime.now(JST).isoformat(),
        }
        existing.append(record)
        self._save_json(revenue_file, existing)
        logger.info("Revenue recorded: %s $%.2f from %s", currency, amount, source)

    def get_revenue_summary(self, month: str | None = None) -> dict:
        """Get revenue summary for a month.

        Args:
            month: Target month (YYYY-MM). Defaults to current month.

        Returns:
            Dict with revenue breakdown by source.
        """
        if not month:
            month = datetime.now(JST).strftime("%Y-%m")

        revenue_file = ANALYTICS_DIR / "revenue_log.json"
        data = self._load_json(revenue_file)
        monthly = [r for r in data if r.get("date", "").startswith(month)]

        by_source = {}
        total = 0.0
        for item in monthly:
            source = item.get("source", "unknown")
            amount = item.get("amount", 0)
            by_source[source] = by_source.get(source, 0) + amount
            total += amount

        return {
            "month": month,
            "total_revenue": round(total, 2),
            "by_source": {k: round(v, 2) for k, v in by_source.items()},
            "transaction_count": len(monthly),
        }

    def _get_daily_file(self) -> Path:
        today = datetime.now(JST).strftime("%Y-%m-%d")
        return ANALYTICS_DIR / f"engagement_{today}.json"

    def _load_json(self, path: Path) -> list:
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save_json(self, path: Path, data) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    analytics = Analytics()
    print("Weekly report:", json.dumps(analytics.get_weekly_report(), indent=2))
    print("Revenue:", json.dumps(analytics.get_revenue_summary(), indent=2))
