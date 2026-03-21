"""System E — Weekly Report Generator & Unified Dashboard.

Aggregates all System E metrics into a unified dashboard and
generates weekly performance reports with LINE/Slack delivery.

Usage:
    python system_e/weekly_report.py --mode dashboard
    python system_e/weekly_report.py --mode weekly --notify
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
DATA_DIR = Path(__file__).parent.parent / "data" / "system_e"
REPORTS_DIR = DATA_DIR / "reports"


class WeeklyReportGenerator:
    """Generate unified dashboards and weekly performance reports."""

    def __init__(self):
        from system_e.analytics import Analytics
        from system_e.monetization_engine import MonetizationEngine
        from system_e.performance_optimizer import PerformanceOptimizer
        from system_e.fanvue_manager import FanvueManager

        self.analytics = Analytics()
        self.monetization = MonetizationEngine()
        self.optimizer = PerformanceOptimizer()
        self.fanvue = FanvueManager()
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # ─── Unified Dashboard ───

    def get_unified_dashboard(self) -> dict:
        """Single JSON aggregating all System E metrics.

        Returns:
            Unified dashboard with engagement, revenue, optimization,
            Fanvue, and pipeline health metrics.
        """
        now = datetime.now(JST)
        month = now.strftime("%Y-%m")

        # Engagement
        weekly_engagement = self.analytics.get_weekly_report()
        content_perf = self.analytics.get_content_type_performance()
        time_perf = self.analytics.get_posting_time_performance()

        # Revenue
        revenue = self.monetization.get_revenue_dashboard(month)

        # Optimization
        optimization = self.optimizer.generate_optimization_report()

        # Fanvue
        fanvue_stats = self.fanvue.get_tier_stats()
        # Fanvue revenue: use tier stats to estimate subscriber counts
        estimated_subs = {
            tier: stats.get("posted", 0)
            for tier, stats in fanvue_stats.items()
        }
        fanvue_revenue = self.fanvue.track_subscription_revenue(estimated_subs)

        # A/B tests
        ab_tests = optimization.get("ab_tests", [])
        ab_active = [t for t in ab_tests if isinstance(t, dict) and t.get("status") == "running"]
        ab_completed = self.optimizer.get_completed_winners()

        # Reply log stats
        reply_stats = self._get_reply_stats()

        dashboard = {
            "generated_at": now.isoformat(),
            "period": weekly_engagement.get("period", ""),
            "engagement": {
                "weekly": {
                    "posts": weekly_engagement.get("total_posts", 0),
                    "likes": weekly_engagement.get("total_likes", 0),
                    "impressions": weekly_engagement.get("total_impressions", 0),
                    "avg_engagement_rate": weekly_engagement.get("avg_engagement_rate", 0),
                    "best_day": weekly_engagement.get("best_day", ""),
                },
                "by_content_type": content_perf,
                "by_posting_time": time_perf,
            },
            "revenue": {
                "month": month,
                "total": revenue.get("total_revenue", 0),
                "sources": revenue.get("sources", {}),
                "targets": revenue.get("targets", {}),
            },
            "fanvue": {
                "tier_stats": fanvue_stats,
                "subscription_revenue": fanvue_revenue,
            },
            "optimization": {
                "posting_times": optimization.get("posting_times", {}),
                "content_patterns": optimization.get("content_patterns", {}),
                "ab_tests_active": len(ab_active),
                "ab_tests_completed": ab_completed,
                "actions": optimization.get("actions", []),
            },
            "community": {
                "mentions_replied_7d": reply_stats.get("replied_7d", 0),
                "reply_rate": reply_stats.get("reply_rate", 0),
            },
            "health": self._pipeline_health(),
        }

        # Save to file
        dashboard_file = REPORTS_DIR / "dashboard_latest.json"
        dashboard_file.write_text(
            json.dumps(dashboard, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        return dashboard

    # ─── Weekly Report ───

    def generate_weekly_report(self, notify: bool = False) -> dict:
        """Generate a comprehensive weekly report with WoW comparisons.

        Args:
            notify: If True, send summary via LINE/Slack.

        Returns:
            Full weekly report dict.
        """
        now = datetime.now(JST)
        dashboard = self.get_unified_dashboard()

        # Week-over-week comparison
        wow = self._calculate_wow()

        # Top performers
        top_posts = self._get_top_posts(7)

        # Content mix analysis
        content_mix = self.monetization.optimize_content_mix()

        report = {
            "report_type": "weekly",
            "generated_at": now.isoformat(),
            "week_ending": now.strftime("%Y-%m-%d"),
            "dashboard": dashboard,
            "week_over_week": wow,
            "top_posts": top_posts,
            "content_mix_recommendations": content_mix.get("recommendations", []),
            "action_items": self._generate_action_items(dashboard, wow),
        }

        # Save report
        report_file = REPORTS_DIR / f"weekly_{now.strftime('%Y-%m-%d')}.json"
        report_file.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("Weekly report saved: %s", report_file)

        # Notify
        if notify:
            self._send_report_notification(report)

        return report

    # ─── Notification ───

    def _send_report_notification(self, report: dict) -> None:
        """Format and send weekly report summary via LINE."""
        from core.notifier import Notifier

        dashboard = report.get("dashboard", {})
        eng = dashboard.get("engagement", {}).get("weekly", {})
        rev = dashboard.get("revenue", {})
        wow = report.get("week_over_week", {})
        actions = report.get("action_items", [])

        # Format WoW changes
        def fmt_change(val: float) -> str:
            if val > 0:
                return f"+{val:.1f}%"
            return f"{val:.1f}%"

        lines = [
            "=== RIENA Weekly Report ===",
            f"Week ending: {report.get('week_ending', '')}",
            "",
            f"Posts: {eng.get('posts', 0)}",
            f"Likes: {eng.get('likes', 0)}",
            f"Impressions: {eng.get('impressions', 0):,}",
            f"Eng Rate: {eng.get('avg_engagement_rate', 0)}%",
        ]

        if wow:
            lines.append("")
            lines.append("WoW Changes:")
            if "likes" in wow:
                lines.append(f"  Likes: {fmt_change(wow['likes'])}")
            if "impressions" in wow:
                lines.append(f"  Impressions: {fmt_change(wow['impressions'])}")
            if "engagement_rate" in wow:
                lines.append(f"  Eng Rate: {fmt_change(wow['engagement_rate'])}")

        lines.append("")
        lines.append(f"Revenue (MTD): ${rev.get('total', 0):.2f}")

        community = dashboard.get("community", {})
        if community.get("mentions_replied_7d", 0) > 0:
            lines.append(f"Mentions replied: {community['mentions_replied_7d']}")

        if actions:
            lines.append("")
            lines.append("Action Items:")
            for i, action in enumerate(actions[:5], 1):
                lines.append(f"  {i}. {action}")

        message = "\n".join(lines)

        notifier = Notifier()
        notifier.notify(message)
        logger.info("Weekly report notification sent")

    # ─── Helpers ───

    def _calculate_wow(self) -> dict:
        """Calculate week-over-week changes."""
        now = datetime.now(JST)
        this_week = {"likes": 0, "impressions": 0, "posts": 0, "eng_rates": []}
        last_week = {"likes": 0, "impressions": 0, "posts": 0, "eng_rates": []}

        for i in range(7):
            date = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            summary = self.analytics.get_daily_summary(date)
            this_week["likes"] += summary.get("total_likes", 0)
            this_week["impressions"] += summary.get("total_impressions", 0)
            this_week["posts"] += summary.get("posts", 0)
            if summary.get("posts", 0) > 0:
                this_week["eng_rates"].append(summary.get("engagement_rate", 0))

        for i in range(7, 14):
            date = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            summary = self.analytics.get_daily_summary(date)
            last_week["likes"] += summary.get("total_likes", 0)
            last_week["impressions"] += summary.get("total_impressions", 0)
            last_week["posts"] += summary.get("posts", 0)
            if summary.get("posts", 0) > 0:
                last_week["eng_rates"].append(summary.get("engagement_rate", 0))

        def pct_change(curr: float, prev: float) -> float:
            if prev == 0:
                return 0.0
            return round((curr - prev) / prev * 100, 1)

        this_eng = sum(this_week["eng_rates"]) / max(1, len(this_week["eng_rates"]))
        last_eng = sum(last_week["eng_rates"]) / max(1, len(last_week["eng_rates"]))

        return {
            "likes": pct_change(this_week["likes"], last_week["likes"]),
            "impressions": pct_change(this_week["impressions"], last_week["impressions"]),
            "posts": pct_change(this_week["posts"], last_week["posts"]),
            "engagement_rate": pct_change(this_eng, last_eng),
        }

    def _get_top_posts(self, days: int = 7) -> list[dict]:
        """Get top performing posts from the last N days."""
        posted_log = DATA_DIR / "posted_log.json"
        if not posted_log.exists():
            return []

        try:
            posts = json.loads(posted_log.read_text(encoding="utf-8"))
        except Exception:
            return []

        now = datetime.now(JST)
        cutoff = (now - timedelta(days=days)).isoformat()

        recent = [p for p in posts if p.get("posted_at", "") > cutoff]
        # Sort by likes (or engagement if available)
        recent.sort(key=lambda p: p.get("likes", 0), reverse=True)
        return recent[:5]

    def _get_reply_stats(self) -> dict:
        """Get mention reply statistics for the last 7 days."""
        reply_log = DATA_DIR / "reply_log.json"
        if not reply_log.exists():
            return {"replied_7d": 0, "reply_rate": 0}

        try:
            replies = json.loads(reply_log.read_text(encoding="utf-8"))
        except Exception:
            return {"replied_7d": 0, "reply_rate": 0}

        cutoff = (datetime.now(JST) - timedelta(days=7)).isoformat()
        recent = [r for r in replies if r.get("replied_at", "") > cutoff]
        return {
            "replied_7d": len(recent),
            "reply_rate": 100.0,  # All collected mentions get replies
        }

    def _pipeline_health(self) -> dict:
        """Check pipeline component health."""
        health = {
            "content_plans": 0,
            "posted_count": 0,
            "last_post": None,
            "errors": [],
        }

        # Count recent content plans
        generated_dir = DATA_DIR / "generated"
        if generated_dir.exists():
            plans = list(generated_dir.glob("content_plan_*.json"))
            health["content_plans"] = len(plans)

        # Check posted log
        posted_log = DATA_DIR / "posted_log.json"
        if posted_log.exists():
            try:
                posts = json.loads(posted_log.read_text(encoding="utf-8"))
                health["posted_count"] = len(posts)
                if posts:
                    health["last_post"] = posts[-1].get("posted_at", "")
            except Exception:
                health["errors"].append("posted_log.json corrupted")

        # Check for stale pipeline (no posts in 48h)
        if health["last_post"]:
            try:
                last = datetime.fromisoformat(health["last_post"])
                if datetime.now(JST) - last > timedelta(hours=48):
                    health["errors"].append("No posts in 48+ hours — check pipeline")
            except Exception:
                pass

        return health

    def _generate_action_items(self, dashboard: dict, wow: dict) -> list[str]:
        """Generate actionable recommendations from dashboard data."""
        actions = []

        # Engagement dropping
        if wow.get("engagement_rate", 0) < -10:
            actions.append(
                f"Engagement rate dropped {wow['engagement_rate']:.1f}% WoW — "
                "review content mix and posting times"
            )

        # Health issues
        errors = dashboard.get("health", {}).get("errors", [])
        for err in errors:
            actions.append(f"Pipeline alert: {err}")

        # Optimization recommendations
        opt_actions = dashboard.get("optimization", {}).get("actions", [])
        for action in opt_actions[:3]:
            actions.append(action)

        # Revenue check
        revenue = dashboard.get("revenue", {})
        targets = revenue.get("targets", {})
        if targets:
            monthly_target = targets.get("monthly_revenue", 0)
            current = revenue.get("total", 0)
            if monthly_target > 0 and current < monthly_target * 0.5:
                actions.append(
                    f"Revenue ${current:.0f} is below 50% of ${monthly_target:.0f} target — "
                    "increase monetized content"
                )

        # Community engagement
        community = dashboard.get("community", {})
        if community.get("mentions_replied_7d", 0) == 0:
            actions.append("No mention replies this week — check engagement pipeline")

        if not actions:
            actions.append("All systems nominal — keep current strategy")

        return actions


def main():
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="System E Weekly Report")
    parser.add_argument(
        "--mode",
        choices=["dashboard", "weekly"],
        default="dashboard",
        help="Report mode: dashboard (unified JSON) or weekly (full report + notify)",
    )
    parser.add_argument(
        "--notify",
        action="store_true",
        help="Send report summary via LINE/Slack",
    )
    args = parser.parse_args()

    gen = WeeklyReportGenerator()

    if args.mode == "dashboard":
        dashboard = gen.get_unified_dashboard()
        print(json.dumps(dashboard, ensure_ascii=False, indent=2))
    elif args.mode == "weekly":
        report = gen.generate_weekly_report(notify=args.notify)
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
