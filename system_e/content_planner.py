"""System E — Weekly Content Planner & Automation Orchestrator.

Runs weekly (Monday) to:
1. Generate next week's content calendar (7 days of plans)
2. Recycle top X posts to Fanvue with exclusive framing
3. Schedule Fanvue weekly content across tiers
4. Run drip campaigns for subscriber retention
5. Evaluate brand outreach triggers based on metrics

Usage:
    python system_e/content_planner.py --mode plan      # Full weekly plan
    python system_e/content_planner.py --mode recycle    # Recycle top posts only
    python system_e/content_planner.py --mode brand      # Brand trigger evaluation
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
DATA_DIR = Path(__file__).parent.parent / "data" / "system_e"
POSTED_LOG = DATA_DIR / "posted_log.json"

# Brand outreach trigger thresholds
BRAND_TRIGGER_THRESHOLDS = {
    "min_weekly_impressions": 5000,
    "min_avg_engagement_rate": 3.0,  # percent
    "min_posts_with_data": 10,
    "min_followers_estimate": 1000,  # based on impressions
}

# Brand categories to auto-prospect when triggers fire
AUTO_PROSPECT_CATEGORIES = [
    {"brand": "AG1", "tier": 2, "category": "supplements"},
    {"brand": "Oura Ring", "tier": 2, "category": "wearables"},
    {"brand": "Calm App", "tier": 3, "category": "wellness"},
    {"brand": "Lululemon", "tier": 1, "category": "fitness_apparel"},
    {"brand": "Thorne", "tier": 3, "category": "supplements"},
    {"brand": "Whoop", "tier": 2, "category": "wearables"},
    {"brand": "Alo Yoga", "tier": 2, "category": "fitness_apparel"},
    {"brand": "Athletic Greens", "tier": 2, "category": "supplements"},
]


class ContentPlanner:
    """Orchestrate weekly content planning and automation tasks."""

    def __init__(self):
        from system_e.content_generator import ContentGenerator
        from system_e.fanvue_manager import FanvueManager
        from system_e.brand_outreach import BrandOutreachEngine
        from system_e.analytics import Analytics
        from system_e.performance_optimizer import PerformanceOptimizer

        self.generator = ContentGenerator()
        self.fanvue = FanvueManager()
        self.brand = BrandOutreachEngine()
        self.analytics = Analytics()
        self.optimizer = PerformanceOptimizer()

    # ─── Weekly Planning ───

    def run_weekly_plan(self) -> dict:
        """Run full weekly content planning pipeline.

        Returns:
            Summary dict with all planning results.
        """
        now = datetime.now(JST)
        logger.info("=== Weekly Content Planning: %s ===", now.strftime("%Y-%m-%d"))

        summary = {
            "planned_at": now.isoformat(),
            "content_plans": 0,
            "fanvue_recycled": 0,
            "fanvue_scheduled": 0,
            "drip_actions": 0,
            "brand_triggers": 0,
        }

        # 1. Generate 7 days of content plans
        try:
            plans = self._generate_week_plans()
            summary["content_plans"] = len(plans)
            logger.info("Generated %d daily content plans", len(plans))
        except Exception as e:
            logger.error("Weekly content plan generation failed: %s", e)

        # 2. Recycle top X posts to Fanvue
        try:
            recycled = self.recycle_top_posts()
            summary["fanvue_recycled"] = len(recycled)
            logger.info("Recycled %d top posts to Fanvue", len(recycled))
        except Exception as e:
            logger.error("Fanvue content recycling failed: %s", e)

        # 3. Schedule Fanvue weekly content
        try:
            schedule = self.fanvue.schedule_weekly_content()
            summary["fanvue_scheduled"] = len(schedule.get("posts", []))
            logger.info("Fanvue weekly schedule: %d posts", summary["fanvue_scheduled"])
        except Exception as e:
            logger.error("Fanvue scheduling failed: %s", e)

        # 4. Run drip campaigns
        try:
            drip_actions = self.fanvue.run_drip_campaign()
            summary["drip_actions"] = len(drip_actions)
            logger.info("Drip campaign: %d actions", len(drip_actions))
        except Exception as e:
            logger.error("Drip campaign failed: %s", e)

        # 5. Evaluate brand outreach triggers
        try:
            triggers = self.evaluate_brand_triggers()
            summary["brand_triggers"] = triggers.get("triggers_fired", 0)
            summary["brand_prospects_added"] = triggers.get("prospects_added", 0)
            logger.info(
                "Brand triggers: %d fired, %d prospects added",
                summary["brand_triggers"],
                triggers.get("prospects_added", 0),
            )
        except Exception as e:
            logger.error("Brand trigger evaluation failed: %s", e)

        # Save summary
        summary_file = DATA_DIR / "reports" / f"weekly_plan_{now.strftime('%Y-%m-%d')}.json"
        summary_file.parent.mkdir(parents=True, exist_ok=True)
        summary_file.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        logger.info("=== Weekly planning complete: %s ===", json.dumps(summary))
        return summary

    # ─── Content Generation ───

    def _generate_week_plans(self) -> list[list[dict]]:
        """Generate content plans for the next 7 days."""
        now = datetime.now(JST)
        plans = []

        for day_offset in range(1, 8):
            target = now + timedelta(days=day_offset)
            date_str = target.strftime("%Y-%m-%d")

            # Check if plan already exists
            plan_file = DATA_DIR / "generated" / f"content_plan_{date_str}.json"
            if plan_file.exists():
                logger.info("Plan already exists for %s, skipping", date_str)
                try:
                    plans.append(json.loads(plan_file.read_text(encoding="utf-8")))
                except Exception:
                    pass
                continue

            try:
                plan = self.generator.generate_daily_content_plan(date_str)
                plans.append(plan)
            except Exception as e:
                logger.error("Failed to generate plan for %s: %s", date_str, e)

        return plans

    # ─── Fanvue Content Recycling ───

    def recycle_top_posts(self, days: int = 7, limit: int = 5) -> list[dict]:
        """Recycle top-performing X posts to Fanvue.

        Args:
            days: Look back period for top posts.
            limit: Max posts to recycle.

        Returns:
            List of recycled content items.
        """
        # Load recent X posts with engagement data
        x_posts = self._get_recent_posts_with_engagement(days)
        if not x_posts:
            logger.info("No recent posts with engagement data for recycling")
            return []

        # Use FanvueManager's recycle method
        recycled = self.fanvue.recycle_top_content(x_posts, limit=limit)
        logger.info("Recycled %d/%d posts to Fanvue", len(recycled), len(x_posts))
        return recycled

    def _get_recent_posts_with_engagement(self, days: int = 7) -> list[dict]:
        """Get recent posted content with engagement metrics."""
        if not POSTED_LOG.exists():
            return []

        try:
            posts = json.loads(POSTED_LOG.read_text(encoding="utf-8"))
        except Exception:
            return []

        cutoff = (datetime.now(JST) - timedelta(days=days)).isoformat()
        recent = [p for p in posts if p.get("posted_at", "") > cutoff]

        # Merge engagement data from analytics
        enriched = []
        for post in recent:
            tweet_id = post.get("tweet_id", "")
            if not tweet_id:
                continue

            # Get engagement from daily analytics files
            engagement = self._get_post_engagement(tweet_id)
            enriched.append({
                **post,
                "likes": engagement.get("likes", post.get("likes", 0)),
                "retweets": engagement.get("retweets", post.get("retweets", 0)),
                "impressions": engagement.get("impressions", 0),
            })

        return enriched

    def _get_post_engagement(self, tweet_id: str) -> dict:
        """Look up engagement metrics for a specific tweet."""
        analytics_dir = DATA_DIR / "analytics"
        if not analytics_dir.exists():
            return {}

        # Search recent daily files
        for f in sorted(analytics_dir.glob("engagement_*.json"), reverse=True)[:14]:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                for record in data:
                    if record.get("tweet_id") == tweet_id:
                        return record
            except Exception:
                continue

        return {}

    # ─── Brand Outreach Triggers ───

    def evaluate_brand_triggers(self) -> dict:
        """Evaluate if metrics thresholds are met for brand outreach.

        Checks weekly engagement metrics against thresholds and:
        - Generates trigger content (organic brand mentions)
        - Auto-adds prospect brands to pipeline if metrics qualify

        Returns:
            Dict with trigger evaluation results.
        """
        weekly = self.analytics.get_weekly_report()
        thresholds = BRAND_TRIGGER_THRESHOLDS

        result = {
            "evaluated_at": datetime.now(JST).isoformat(),
            "metrics": {
                "weekly_impressions": weekly.get("total_impressions", 0),
                "avg_engagement_rate": weekly.get("avg_engagement_rate", 0),
                "total_posts": weekly.get("total_posts", 0),
            },
            "thresholds": thresholds,
            "triggers_fired": 0,
            "prospects_added": 0,
            "trigger_content": [],
            "reasons": [],
        }

        impressions = weekly.get("total_impressions", 0)
        eng_rate = weekly.get("avg_engagement_rate", 0)
        total_posts = weekly.get("total_posts", 0)

        # Check thresholds
        meets_impressions = impressions >= thresholds["min_weekly_impressions"]
        meets_engagement = eng_rate >= thresholds["min_avg_engagement_rate"]
        meets_data = total_posts >= thresholds["min_posts_with_data"]

        if not meets_data:
            result["reasons"].append(
                f"Not enough data: {total_posts} posts "
                f"(need {thresholds['min_posts_with_data']})"
            )
            return result

        triggers_fired = 0

        # Trigger 1: High impressions → ready for brand visibility
        if meets_impressions:
            triggers_fired += 1
            result["reasons"].append(
                f"Impressions threshold met: {impressions:,} >= "
                f"{thresholds['min_weekly_impressions']:,}"
            )

            # Generate organic brand-mention content
            try:
                trigger = self.brand.generate_trigger_content(
                    trigger_type="product_in_life",
                    context="high engagement week",
                )
                if trigger and not trigger.get("error"):
                    result["trigger_content"].append(trigger)
            except Exception as e:
                logger.error("Trigger content generation failed: %s", e)

        # Trigger 2: High engagement → ready for affiliate/brand pitches
        if meets_engagement and meets_impressions:
            triggers_fired += 1
            result["reasons"].append(
                f"Engagement threshold met: {eng_rate:.1f}% >= "
                f"{thresholds['min_avg_engagement_rate']}%"
            )

            # Auto-add prospect brands that aren't already in pipeline
            prospects_added = self._auto_add_prospects()
            result["prospects_added"] = prospects_added

        # Trigger 3: Data story opportunity
        if meets_data and total_posts >= 20:
            triggers_fired += 1
            result["reasons"].append(
                f"Data story opportunity: {total_posts} posts with metrics"
            )
            try:
                trigger = self.brand.generate_trigger_content(
                    trigger_type="data_story",
                    context=f"{total_posts} posts analyzed",
                )
                if trigger and not trigger.get("error"):
                    result["trigger_content"].append(trigger)
            except Exception as e:
                logger.error("Data story trigger failed: %s", e)

        result["triggers_fired"] = triggers_fired

        # Save evaluation
        trigger_file = DATA_DIR / "brand_deals" / "trigger_evaluation.json"
        trigger_file.parent.mkdir(parents=True, exist_ok=True)
        trigger_file.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        return result

    def _auto_add_prospects(self) -> int:
        """Add pre-defined brand prospects to pipeline if not already there."""
        existing = self.brand.get_pipeline_summary()
        existing_names = set()
        for names in existing.get("brand_names_by_stage", {}).values():
            existing_names.update(names)

        added = 0
        for prospect in AUTO_PROSPECT_CATEGORIES:
            if prospect["brand"] not in existing_names:
                try:
                    self.brand.add_prospect(
                        brand_name=prospect["brand"],
                        tier=prospect["tier"],
                        category=prospect["category"],
                        notes="Auto-added by trigger evaluation",
                    )
                    added += 1
                    logger.info("Auto-added prospect: %s", prospect["brand"])
                except Exception as e:
                    logger.error("Failed to add prospect %s: %s", prospect["brand"], e)

        return added


def main():
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="System E Weekly Content Planner")
    parser.add_argument(
        "--mode",
        choices=["plan", "recycle", "brand"],
        default="plan",
        help="Mode: plan (full weekly), recycle (top posts to Fanvue), brand (trigger eval)",
    )
    args = parser.parse_args()

    planner = ContentPlanner()

    if args.mode == "plan":
        result = planner.run_weekly_plan()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.mode == "recycle":
        recycled = planner.recycle_top_posts()
        print(f"Recycled {len(recycled)} posts to Fanvue")
        print(json.dumps(recycled, indent=2, ensure_ascii=False))
    elif args.mode == "brand":
        result = planner.evaluate_brand_triggers()
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
