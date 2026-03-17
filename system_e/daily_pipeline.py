"""System E — Daily Pipeline Orchestrator.

Fully automated: generate content plan → generate images → schedule posts → notify.
Runs daily via cron or GitHub Actions.
"""

import json
import logging
from datetime import datetime, timezone, timedelta

from core.notifier import Notifier
from system_e.image_pipeline import ImagePipeline
from system_e.content_generator import ContentGenerator
from system_e.posting_scheduler import PostingScheduler
from system_e.fanvue_manager import FanvueManager
from system_e.analytics import Analytics

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))


class SystemEPipeline:
    """Orchestrate the full System E daily flow."""

    def __init__(self):
        self.content_gen = ContentGenerator()
        self.image_pipeline = ImagePipeline()
        self.scheduler = PostingScheduler()
        self.fanvue = FanvueManager()
        self.analytics = Analytics()
        self.notifier = Notifier()

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
            logger.warning("Image pipeline not configured (FAL_API_KEY missing)")
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
            "content_generated": 0,
            "images_generated": 0,
            "posts_published": 0,
            "fanvue_queued": 0,
        }

        # Phase 1: Generate tomorrow's content
        try:
            plan = self.run_content_generation(target_date)
            summary["content_generated"] = len(plan)
        except Exception as e:
            logger.error("Content generation failed: %s", e)
            plan = []

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

        # Phase 4: Check Fanvue queue
        fanvue_stats = self.fanvue.get_tier_stats()
        summary["fanvue_queued"] = sum(
            v.get("ready", 0) for v in fanvue_stats.values()
        )

        # Notify
        end = datetime.now(JST)
        duration = (end - now).total_seconds()

        self.notifier.send_line(
            f"【System E】パイプライン完了\n"
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

    def run_posting_only(self) -> list[dict]:
        """Run only the posting phase (for frequent cron execution)."""
        return self.run_posting()


def main():
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="System E Daily Pipeline")
    parser.add_argument(
        "--mode",
        choices=["full", "generate", "post"],
        default="full",
        help="Pipeline mode: full (generate+post), generate (content only), post (due posts only)",
    )
    parser.add_argument(
        "--date",
        help="Target date for content generation (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--reference-image",
        help="URL of reference image for Kontext consistency",
    )
    args = parser.parse_args()

    pipeline = SystemEPipeline()

    if args.mode == "full":
        pipeline.run_full_pipeline(args.date)
    elif args.mode == "generate":
        plan = pipeline.run_content_generation(args.date)
        if args.reference_image:
            pipeline.run_image_generation(plan, args.reference_image)
    elif args.mode == "post":
        pipeline.run_posting_only()


if __name__ == "__main__":
    main()
