"""Daily pipeline orchestrator for System A.

Runs all 3 pipelines, selects posts, and schedules them.
Designed to be called via cron at 06:00 JST daily.
"""

import logging
from datetime import datetime, timezone, timedelta

from core.notifier import Notifier
from system_a.pipeline1_jp_buzz import Pipeline1JpBuzz
from system_a.pipeline2_data_driven import Pipeline2DataDriven
from system_a.pipeline3_ai_original import Pipeline3AIOriginal
from system_a.pipeline4_nexus import Pipeline4Nexus
from system_a.post_selector import PostSelector
from system_a.auto_post import AutoPoster

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))


class DailyPipeline:
    """Orchestrate the full daily posting flow."""

    def __init__(self):
        self.p1 = Pipeline1JpBuzz()
        self.p2 = Pipeline2DataDriven()
        self.p3 = Pipeline3AIOriginal()
        self.p4 = Pipeline4Nexus()
        self.selector = PostSelector()
        self.poster = AutoPoster()
        self.notifier = Notifier()

    def run_generation(self) -> dict:
        """Run all 4 pipelines and return counts."""
        results = {"P1": 0, "P2": 0, "P3": 0, "P4": 0}

        logger.info("[06:00] Pipeline 1: JP Buzz Structure Import")
        try:
            p1_posts = self.p1.run()
            results["P1"] = len(p1_posts)
        except Exception as e:
            logger.error("Pipeline 1 failed: %s", e)

        logger.info("[06:02] Pipeline 2: Data-Driven Original")
        try:
            p2_posts = self.p2.run()
            results["P2"] = len(p2_posts)
        except Exception as e:
            logger.error("Pipeline 2 failed: %s", e)

        logger.info("[06:04] Pipeline 3: AI Original Creation")
        try:
            p3_posts = self.p3.run()
            results["P3"] = len(p3_posts)
        except Exception as e:
            logger.error("Pipeline 3 failed: %s", e)

        logger.info("[06:05] Pipeline 4: NEXUS V2 Strategy Posts")
        try:
            p4_posts = self.p4.run()
            results["P4"] = len(p4_posts)
        except Exception as e:
            logger.error("Pipeline 4 failed: %s", e)

        return results

    def run_selection(self) -> list:
        """Select and schedule posts."""
        logger.info("[06:06] Post selection and scheduling")
        return self.selector.run()

    def run(self) -> None:
        """Execute the complete daily flow."""
        now = datetime.now(JST)
        logger.info("=== Daily Pipeline Start: %s ===", now.strftime("%Y-%m-%d %H:%M"))

        # Phase 1: Generation
        gen_results = self.run_generation()

        # Phase 2: Selection
        selected = self.run_selection()

        # Phase 3: Notify
        pipeline_counts = ", ".join(f"{k}:{v}本" for k, v in gen_results.items())
        selected_count = len(selected)
        skipped = sum(gen_results.values()) - selected_count

        self.notifier.send_line(
            f"本日の投稿{selected_count}本がスケジュールされました\n"
            f"生成: {pipeline_counts}\n"
            f"品質不足スキップ: {skipped}本"
        )

        # Phase 4: Execute scheduled posts
        for post in selected:
            scheduled_time = post.get("scheduled_time", "07:00")
            logger.info(
                "Scheduled: %s (pillar=%s, pipeline=%s)",
                scheduled_time, post.get("pillar"), post.get("pipeline"),
            )

        logger.info("=== Daily Pipeline Complete ===")
        return selected


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    pipeline = DailyPipeline()
    pipeline.run()


if __name__ == "__main__":
    main()
