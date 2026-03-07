"""Daily pipeline orchestrator for System A.

Fully automated: generate → fact check → quality check → image → post → notify.
Runs via GitHub Actions (18:30 JST) or cron daily.
"""

import logging
from datetime import datetime, timezone, timedelta

from core.notifier import Notifier
from core.image_generator import ImageGenerator
from core.engagement_learner import EngagementLearner
from system_a.pipeline1_jp_buzz import Pipeline1JpBuzz
from system_a.pipeline2_data_driven import Pipeline2DataDriven
from system_a.pipeline3_ai_original import Pipeline3AIOriginal
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
        self.selector = PostSelector()
        self.poster = AutoPoster()
        self.notifier = Notifier()
        self.image_generator = ImageGenerator()
        self.learner = EngagementLearner()

    def run_generation(self) -> dict:
        """Run all 3 pipelines and return counts."""
        results = {"P1": 0, "P2": 0, "P3": 0}

        logger.info("Pipeline 1: JP Buzz Structure Import")
        try:
            p1_posts = self.p1.run()
            results["P1"] = len(p1_posts)
        except Exception as e:
            logger.error("Pipeline 1 failed: %s", e)

        logger.info("Pipeline 2: Data-Driven Original")
        try:
            p2_posts = self.p2.run()
            results["P2"] = len(p2_posts)
        except Exception as e:
            logger.error("Pipeline 2 failed: %s", e)

        logger.info("Pipeline 3: AI Original Creation")
        try:
            p3_posts = self.p3.run()
            results["P3"] = len(p3_posts)
        except Exception as e:
            logger.error("Pipeline 3 failed: %s", e)

        return results

    def run_selection(self) -> list:
        """Select and schedule posts (includes fact check + quality check)."""
        logger.info("Post selection (fact check + quality check)...")
        return self.selector.run()

    def run_learning(self) -> None:
        """Run engagement learning cycle before generation."""
        logger.info("Running engagement learning cycle...")
        try:
            insights = self.learner.run()
            patterns = len(insights.get("top_patterns", []))
            learnings = len(insights.get("key_learnings", []))
            logger.info(
                "Learning complete: %d patterns, %d learnings", patterns, learnings
            )
        except Exception as e:
            logger.warning("Engagement learning failed (non-fatal): %s", e)

    def run(self) -> list:
        """Execute the complete daily flow: generate → check → post → notify."""
        now = datetime.now(JST)
        logger.info("=== Daily Pipeline Start: %s ===", now.strftime("%Y-%m-%d %H:%M"))

        # Phase 0: Learn from popular posts before generating
        self.run_learning()

        # Phase 1: Generation (3 pipelines)
        gen_results = self.run_generation()

        # Phase 2: Selection (fact check + quality check + pillar balance)
        selected = self.run_selection()

        if not selected:
            self.notifier.send_line("本日の投稿候補なし（品質基準未達）")
            logger.info("=== No posts passed quality check ===")
            return []

        # Phase 3: Generate images
        if self.image_generator.enabled:
            logger.info("Generating images for selected posts...")
            for post in selected:
                text = post.get("text", "")
                display = text if isinstance(text, str) else text[0] if text else ""
                pillar = post.get("pillar", 0)
                try:
                    image_path = self.image_generator.generate_for_post(display, pillar=pillar)
                    if image_path:
                        post["image_path"] = image_path
                        logger.info("Image generated for pillar %s: %s", pillar, image_path)
                except Exception as e:
                    logger.warning("Image generation failed for post: %s", e)

        # Phase 4: Post to X
        posted = []
        for post in selected:
            text = post.get("text", "")
            display = text if isinstance(text, str) else text[0] if text else ""
            pillar = post.get("pillar", "?")
            pipeline = post.get("pipeline", "?")
            score = post.get("quality_score", "?")

            logger.info(
                "Posting: pillar=%s, pipeline=%s, score=%s, image=%s",
                pillar, pipeline, score, bool(post.get("image_path")),
            )
            try:
                result = self.poster.post_and_record(post)
                posted.append(result)

                # Get tweet ID for notification
                if isinstance(result, list):
                    tweet_id = result[0].get("data", {}).get("id", "") if result else ""
                else:
                    tweet_id = result.get("data", {}).get("id", "")

                self.notifier.send_line(
                    f"投稿完了 (柱{pillar}/{pipeline}/スコア{score})\n"
                    f"{display[:140]}\n"
                    f"https://x.com/HirokiMiyao/status/{tweet_id}"
                )
            except Exception as e:
                logger.error("Failed to post: %s", e)
                self.notifier.send_line(
                    f"投稿失敗 (柱{pillar}/{pipeline})\nエラー: {e}"
                )

        # Phase 5: Summary
        pipeline_counts = ", ".join(f"{k}:{v}本" for k, v in gen_results.items())
        logger.info(
            "=== Daily Pipeline Complete: generated=%s, posted=%d ===",
            pipeline_counts, len(posted),
        )
        return posted


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    pipeline = DailyPipeline()
    pipeline.run()


if __name__ == "__main__":
    main()
