"""System E — Daily Pipeline Orchestrator.

Fully automated: generate content plan → generate images → schedule posts → notify.
Runs daily via cron or GitHub Actions.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml

from core.notifier import Notifier
from system_e.image_pipeline import ImagePipeline
from system_e.content_generator import ContentGenerator
from system_e.posting_scheduler import PostingScheduler
from system_e.fanvue_manager import FanvueManager
from system_e.analytics import Analytics
from system_e.monetization_engine import MonetizationEngine
from system_e.performance_optimizer import PerformanceOptimizer
from system_e.engagement_collector import EngagementCollector
from system_e.mention_responder import MentionResponder

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
DATA_DIR = Path(__file__).parent.parent / "data" / "system_e"
COST_LOG = DATA_DIR / "analytics" / "cost_log.json"
LOCK_FILE = DATA_DIR / ".pipeline.lock"
CONFIG_PATH = Path(__file__).parent.parent / "config" / "config.yaml"

# Required env vars per mode (empty string = not set)
REQUIRED_ENV = {
    "generate": ["ANTHROPIC_API_KEY"],
    "post": ["ANTHROPIC_API_KEY"],
    "engage": [],
    "collect": [],
    "optimize": [],
    "full": ["ANTHROPIC_API_KEY"],
    "weekly": [],
    "dashboard": [],
    "plan": ["ANTHROPIC_API_KEY"],
    "recycle": [],
    "brand": [],
}


class SystemEPipeline:
    """Orchestrate the full System E daily flow."""

    def __init__(self):
        self.content_gen = ContentGenerator()
        self.image_pipeline = ImagePipeline()
        self.scheduler = PostingScheduler()
        self.fanvue = FanvueManager()
        self.analytics = Analytics()
        self.notifier = Notifier()
        self.monetization = MonetizationEngine()
        self.optimizer = PerformanceOptimizer()
        self.collector = EngagementCollector()
        self.responder = MentionResponder()

    def run_content_generation(self, date: str | None = None) -> list[dict]:
        """Phase 1: Generate tomorrow's content plan with captions."""
        logger.info("Phase 1: Content generation")
        plan = self.content_gen.generate_daily_content_plan(date)
        logger.info("Generated %d content items", len(plan))
        return plan

    def run_image_generation(
        self,
        plan: list[dict],
        reference_image_url: str | None = None,
    ) -> list[dict]:
        """Phase 2: Generate images for each content item."""
        logger.info("Phase 2: Image generation")

        if not self.image_pipeline.enabled:
            logger.warning(
                "Image pipeline not configured (provider=%s)",
                self.image_pipeline.provider,
            )
            return plan

        if not self._check_budget():
            logger.warning("Skipping image generation — budget limit reached")
            return plan

        for item in plan:
            scene = item.get("scene", "lifestyle")
            try:
                image_path = self.image_pipeline.generate_for_scene(
                    scene=scene,
                    aspect_ratio="16:9",  # Optimized for X
                    reference_image_url=reference_image_url,
                )
                if image_path:
                    item["image_path"] = image_path
                    logger.info("Image generated for %s: %s", scene, image_path)

                    # Also prepare Fanvue content (portrait ratio)
                    fanvue_image = self.image_pipeline.generate_for_scene(
                        scene=scene,
                        aspect_ratio="3:4",  # Optimized for Fanvue
                        reference_image_url=reference_image_url,
                    )
                    if fanvue_image:
                        self.fanvue.prepare_fanvue_post(
                            image_path=fanvue_image,
                            scene=scene,
                            caption=item.get("text", ""),
                        )
            except Exception as e:
                logger.error("Image generation failed for %s: %s", scene, e)

        images_generated = sum(1 for item in plan if item.get("image_path"))
        logger.info("Images generated: %d/%d", images_generated, len(plan))

        # Record estimated cost (Flux.1 Dev ~$0.04/image via RunPod)
        cost_per_image = 0.05  # conservative estimate
        total_cost = images_generated * cost_per_image * 2  # X + Fanvue
        if total_cost > 0:
            self._record_cost(f"image_gen_{images_generated}x2", total_cost)

        return plan

    def run_posting(self) -> list[dict]:
        """Phase 3: Post due content to X."""
        logger.info("Phase 3: Posting due content")
        results = self.scheduler.run_due_posts()
        logger.info("Posted %d items", len(results))
        return results

    def run_full_pipeline(self, target_date: str | None = None) -> dict:
        """Run the complete daily pipeline.

        This generates content for tomorrow and posts today's due content.

        Args:
            target_date: Date to generate content for (YYYY-MM-DD). Defaults to tomorrow.

        Returns:
            Summary dict with generation and posting results.
        """
        now = datetime.now(JST)
        logger.info("=== System E Pipeline Start: %s ===", now.strftime("%Y-%m-%d %H:%M"))

        summary = {
            "started_at": now.isoformat(),
            "engagement_collected": 0,
            "content_generated": 0,
            "images_generated": 0,
            "posts_published": 0,
            "fanvue_queued": 0,
            "monetization_enriched": 0,
        }

        # Phase 0: Collect engagement metrics (feeds optimizer)
        try:
            collected = self.collector.collect_tweet_metrics()
            summary["engagement_collected"] = collected
            logger.info("Engagement collection: %d tweets updated", collected)
        except Exception as e:
            logger.error("Engagement collection failed: %s", e)

        # Phase 1: Generate tomorrow's content
        try:
            plan = self.run_content_generation(target_date)
            summary["content_generated"] = len(plan)
        except Exception as e:
            logger.error("Content generation failed: %s", e)
            plan = []

        # Phase 1.5: Monetization enrichment
        if plan:
            try:
                plan = self.monetization.run_monetization_pass(plan)
                summary["monetization_enriched"] = sum(
                    1 for p in plan if p.get("monetization", {}).get("score", 0) > 0
                )
                logger.info("Monetization pass: %d items enriched", summary["monetization_enriched"])
            except Exception as e:
                logger.error("Monetization enrichment failed: %s", e)

        # Phase 2: Generate images
        if plan:
            try:
                plan = self.run_image_generation(plan)
                summary["images_generated"] = sum(1 for p in plan if p.get("image_path"))
            except Exception as e:
                logger.error("Image generation failed: %s", e)

        # Phase 3: Post today's due content
        try:
            posted = self.run_posting()
            summary["posts_published"] = len(posted)
        except Exception as e:
            logger.error("Posting failed: %s", e)

        # Phase 3.5: Auto-reply to mentions (engagement loop)
        try:
            replies = self.responder.run()
            summary["mentions_replied"] = len(replies)
            logger.info("Mention replies: %d", len(replies))
        except Exception as e:
            logger.error("Mention responder failed: %s", e)

        # Phase 4: Check Fanvue queue
        fanvue_stats = self.fanvue.get_tier_stats()
        summary["fanvue_queued"] = sum(
            v.get("ready", 0) for v in fanvue_stats.values()
        )

        # Phase 5: Performance optimization + A/B feedback
        try:
            # Feed engagement data into running A/B tests
            self.optimizer.auto_feed_ab_tests()
            # Generate optimization report
            opt_report = self.optimizer.generate_optimization_report()
            summary["optimization"] = {
                "sample_size": opt_report.get("posting_times", {}).get("sample_size", 0),
                "enough_data": opt_report.get("posting_times", {}).get("enough_data", False),
                "actions": opt_report.get("actions", []),
                "ab_tests_active": len([
                    t for t in opt_report.get("ab_tests", [])
                    if t.get("status") == "running"
                ]),
            }
            logger.info(
                "Optimization: %d samples, %d active A/B tests, actions=%s",
                summary["optimization"]["sample_size"],
                summary["optimization"]["ab_tests_active"],
                summary["optimization"]["actions"][:2],
            )
        except Exception as e:
            logger.error("Optimization analysis failed: %s", e)

        # Notify
        end = datetime.now(JST)
        duration = (end - now).total_seconds()

        self.notifier.send_line(
            f"【System E】パイプライン完了\n"
            f"エンゲージメント収集: {summary['engagement_collected']}件\n"
            f"コンテンツ生成: {summary['content_generated']}件\n"
            f"画像生成: {summary['images_generated']}件\n"
            f"X投稿: {summary['posts_published']}件\n"
            f"Fanvueキュー: {summary['fanvue_queued']}件\n"
            f"所要時間: {duration:.0f}秒"
        )

        logger.info(
            "=== System E Pipeline Complete: %s (%.0fs) ===",
            json.dumps(summary),
            duration,
        )
        return summary

    def run_engagement(self) -> dict:
        """Run engagement collection + mention replies."""
        logger.info("=== Engagement Run ===")
        summary = {"engagement_collected": 0, "mentions_replied": 0}
        try:
            summary["engagement_collected"] = self.collector.collect_tweet_metrics()
            self.collector.collect_mentions()
        except Exception as e:
            logger.error("Engagement collection failed: %s", e)
        try:
            replies = self.responder.run()
            summary["mentions_replied"] = len(replies)
        except Exception as e:
            logger.error("Mention responder failed: %s", e)
        try:
            self.optimizer.auto_feed_ab_tests()
        except Exception as e:
            logger.error("A/B feedback failed: %s", e)
        logger.info("Engagement run complete: %s", summary)
        return summary

    def run_posting_only(self) -> list[dict]:
        """Run only the posting phase (for frequent cron execution)."""
        return self.run_posting()

    def _check_budget(self) -> bool:
        """Check if monthly image generation budget allows more spending."""
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                config = yaml.safe_load(f)
            budget = config.get("system_e", {}).get("cost_tracking", {})
            monthly_limit = budget.get("monthly_budget_usd", 50)
            alert_pct = budget.get("alert_threshold_pct", 80) / 100

            month_key = datetime.now(JST).strftime("%Y-%m")
            spent = self._get_monthly_spend(month_key)
            if spent >= monthly_limit:
                logger.warning(
                    "Monthly budget exhausted: $%.2f / $%.2f", spent, monthly_limit
                )
                return False
            if spent >= monthly_limit * alert_pct:
                logger.warning(
                    "Budget alert: $%.2f / $%.2f (%.0f%%)",
                    spent, monthly_limit, spent / monthly_limit * 100,
                )
            return True
        except Exception as e:
            logger.debug("Budget check skipped: %s", e)
            return True

    def _record_cost(self, item: str, cost_usd: float) -> None:
        """Record a cost entry for tracking."""
        COST_LOG.parent.mkdir(parents=True, exist_ok=True)
        entries = []
        if COST_LOG.exists():
            try:
                entries = json.loads(COST_LOG.read_text(encoding="utf-8"))
            except Exception:
                entries = []
        entries.append({
            "date": datetime.now(JST).isoformat(),
            "item": item,
            "cost_usd": cost_usd,
        })
        COST_LOG.write_text(json.dumps(entries, indent=2), encoding="utf-8")

    def _get_monthly_spend(self, month_key: str) -> float:
        """Sum costs for a given month (YYYY-MM)."""
        if not COST_LOG.exists():
            return 0.0
        try:
            entries = json.loads(COST_LOG.read_text(encoding="utf-8"))
            return sum(
                e.get("cost_usd", 0)
                for e in entries
                if e.get("date", "").startswith(month_key)
            )
        except Exception:
            return 0.0


def _check_env(mode: str) -> list[str]:
    """Check that required environment variables are set for the given mode.

    Returns:
        List of missing variable names (empty = all good).
    """
    import os

    required = REQUIRED_ENV.get(mode, [])
    return [var for var in required if not os.getenv(var)]


def _acquire_lock() -> bool:
    """Acquire a file-based lock to prevent duplicate pipeline runs.

    Returns:
        True if lock acquired, False if another instance is running.
    """
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    if LOCK_FILE.exists():
        try:
            lock_data = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
            locked_at = datetime.fromisoformat(lock_data.get("locked_at", ""))
            # Stale lock: older than 30 minutes
            if datetime.now(JST) - locked_at > timedelta(minutes=30):
                logger.warning("Stale lock detected (>30min), overriding")
            else:
                logger.warning(
                    "Pipeline already running (locked at %s, pid=%s)",
                    lock_data.get("locked_at"),
                    lock_data.get("pid"),
                )
                return False
        except Exception:
            pass  # Corrupt lock file, override

    import os

    LOCK_FILE.write_text(
        json.dumps({
            "locked_at": datetime.now(JST).isoformat(),
            "pid": os.getpid(),
        }),
        encoding="utf-8",
    )
    return True


def _release_lock() -> None:
    """Release the pipeline lock."""
    if LOCK_FILE.exists():
        LOCK_FILE.unlink()


def main():
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="System E Daily Pipeline")
    parser.add_argument(
        "--mode",
        choices=["full", "generate", "post", "engage", "monetize", "optimize", "collect", "weekly", "dashboard", "plan", "recycle", "brand"],
        default="full",
        help="Pipeline mode: full, generate, post, engage, monetize, optimize, collect, weekly, dashboard, plan, recycle, brand",
    )
    parser.add_argument(
        "--date",
        help="Target date for content generation (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--reference-image",
        help="URL of reference image for Kontext consistency",
    )
    parser.add_argument(
        "--no-lock",
        action="store_true",
        help="Skip execution lock (for parallel modes like collect/optimize)",
    )
    args = parser.parse_args()

    # Environment validation
    missing = _check_env(args.mode)
    if missing:
        logger.error("Missing required env vars for mode '%s': %s", args.mode, missing)
        raise SystemExit(1)

    # Execution lock for modes that modify state
    needs_lock = args.mode in ("full", "generate", "post", "engage", "plan")
    if needs_lock and not args.no_lock:
        if not _acquire_lock():
            logger.error("Cannot acquire lock — another pipeline is running")
            raise SystemExit(1)

    try:
        pipeline = SystemEPipeline()

        if args.mode == "full":
            pipeline.run_full_pipeline(args.date)
        elif args.mode == "generate":
            plan = pipeline.run_content_generation(args.date)
            if args.reference_image:
                pipeline.run_image_generation(plan, args.reference_image)
        elif args.mode == "post":
            pipeline.run_posting_only()
        elif args.mode == "engage":
            result = pipeline.run_engagement()
            print(json.dumps(result, indent=2))
        elif args.mode == "monetize":
            report = pipeline.monetization.generate_monthly_report()
            print(json.dumps(report, indent=2, ensure_ascii=False))
        elif args.mode == "optimize":
            report = pipeline.optimizer.generate_optimization_report()
            print(json.dumps(report, indent=2, ensure_ascii=False))
        elif args.mode == "collect":
            count = pipeline.collector.collect_tweet_metrics()
            print(f"Collected metrics for {count} tweets")
            pipeline.optimizer.auto_feed_ab_tests()
            print("A/B test feedback updated")
        elif args.mode in ("weekly", "dashboard"):
            from system_e.weekly_report import WeeklyReportGenerator
            gen = WeeklyReportGenerator()
            if args.mode == "weekly":
                report = gen.generate_weekly_report(notify=True)
                print(json.dumps(report, indent=2, ensure_ascii=False))
            else:
                dashboard = gen.get_unified_dashboard()
                print(json.dumps(dashboard, indent=2, ensure_ascii=False))
        elif args.mode in ("plan", "recycle", "brand"):
            from system_e.content_planner import ContentPlanner
            planner = ContentPlanner()
            if args.mode == "plan":
                result = planner.run_weekly_plan()
                print(json.dumps(result, indent=2, ensure_ascii=False))
            elif args.mode == "recycle":
                recycled = planner.recycle_top_posts()
                print(f"Recycled {len(recycled)} posts to Fanvue")
            elif args.mode == "brand":
                result = planner.evaluate_brand_triggers()
                print(json.dumps(result, indent=2, ensure_ascii=False))
    finally:
        if needs_lock and not args.no_lock:
            _release_lock()


if __name__ == "__main__":
    main()
