"""Daily pipeline orchestrator for System A.

Runs all 3 pipelines, selects posts, and schedules them.
Designed to be called via cron at 06:00 JST daily.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

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

        return results

    def run_selection(self) -> list:
        """Select and schedule posts."""
        logger.info("[06:06] Post selection and scheduling")
        return self.selector.run()

    def run_learning(self) -> None:
        """Run engagement learning cycle before generation.

        Analyzes popular posts (own + industry), extracts patterns,
        and saves insights for use during generation.
        """
        logger.info("[Pre-gen] Running engagement learning cycle...")
        try:
            insights = self.learner.run()
            patterns = len(insights.get("top_patterns", []))
            learnings = len(insights.get("key_learnings", []))
            logger.info(
                "Learning complete: %d patterns, %d learnings", patterns, learnings
            )
        except Exception as e:
            logger.warning("Engagement learning failed (non-fatal): %s", e)

    def run(self) -> None:
        """Execute the complete daily flow."""
        now = datetime.now(JST)
        logger.info("=== Daily Pipeline Start: %s ===", now.strftime("%Y-%m-%d %H:%M"))

        # Phase 0: Learn from popular posts before generating
        self.run_learning()

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

        # Phase 4: Generate images for selected posts
        if self.image_generator.enabled:
            logger.info("[06:08] Generating images for selected posts...")
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

        # Phase 5: Save to pending approval (DO NOT auto-post)
        if selected:
            # Save best post to pending approval
            best = selected[0]
            pending_path = Path(__file__).parent.parent / "data" / "system_a" / "pending_approval.json"
            pending_path.parent.mkdir(parents=True, exist_ok=True)

            text = best.get("text", "")
            display = text if isinstance(text, str) else "\n".join(text) if text else ""
            pillar = best.get("pillar", "?")
            pipeline = best.get("pipeline", "?")
            score = best.get("quality_score", "?")

            pending_data = {
                "text": text,
                "image_path": best.get("image_path"),
                "pillar": pillar,
                "pipeline": pipeline,
                "pattern": best.get("pattern", "A"),
                "quality_score": score,
                "created_at": now.isoformat(),
            }
            pending_path.write_text(
                json.dumps(pending_data, ensure_ascii=False, indent=2), encoding="utf-8"
            )

            # Send LINE notification for approval
            self.notifier.send_line(
                f"【X投稿 承認待ち】\n"
                f"柱{pillar} / {pipeline}\n"
                f"スコア: {score}\n"
                f"---\n"
                f"{display[:200]}\n"
                f"---\n"
                f"承認: python -m system_a.generate_and_post --approve"
            )
            logger.info("Pending approval: pillar=%s, pipeline=%s, score=%s", pillar, pipeline, score)
        else:
            self.notifier.send_line("本日の投稿候補がありませんでした（品質基準未達）")

        logger.info("=== Daily Pipeline Complete: %d candidates pending approval ===", len(selected))
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
