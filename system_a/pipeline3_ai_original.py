"""Pipeline 3: AI Original Creation.

Generates original posts from HIROKI's persona and sub-theme rotation,
without any external source material.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

from core.claude_client import ClaudeClient
from core.quality_checker import QualityChecker
from core.engagement_learner import EngagementLearner
from system_a.theme_rotator import ThemeRotator

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data" / "system_a" / "pipeline3"
PROMPTS_DIR = BASE_DIR / "prompts"


class Pipeline3AIOriginal:
    """Generate fully AI-created original posts."""

    def __init__(self):
        self.claude = ClaudeClient()
        self.quality_checker = QualityChecker(self.claude)
        self.theme_rotator = ThemeRotator()
        self.learner = EngagementLearner()

    def generate_posts(self, count: int = 5) -> list:
        """Generate original posts for selected themes.

        Injects engagement learnings from past analysis to continuously improve.
        """
        prompt_template = (PROMPTS_DIR / "ai_original.txt").read_text(encoding="utf-8")
        generated = []

        # Get learning context from past performance analysis
        learning_context = self.learner.build_generation_context()

        for _ in range(count):
            theme = self.theme_rotator.select_theme()
            if not theme:
                logger.warning("No theme available, skipping")
                continue

            prompt = prompt_template.replace(
                "{pillar_number}", str(theme["pillar_number"])
            ).replace(
                "{pillar_name}", theme["pillar_name"]
            ).replace(
                "{sub_theme}", theme["sub_theme"]
            )

            # Inject learning context if available
            if learning_context:
                prompt += f"\n\n{learning_context}"

            try:
                result = self.claude.generate_json(prompt, temperature=0.9)
                if isinstance(result, dict):
                    result["pipeline"] = "P3"
                    result["theme"] = theme
                    generated.append(result)
                    self.theme_rotator.record_usage(
                        theme["pillar_number"], theme["sub_theme"]
                    )
            except Exception as e:
                logger.warning("AI original generation failed: %s", e)

        # Save
        today = datetime.now(JST).strftime("%Y-%m-%d")
        out_dir = DATA_DIR / "generated"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{today}.json"
        out_path.write_text(
            json.dumps(generated, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("Generated %d P3 posts -> %s", len(generated), out_path)
        return generated

    def run(self) -> list:
        """Execute full Pipeline 3 flow."""
        logger.info("Pipeline 3: Selecting themes and generating...")
        generated = self.generate_posts(count=5)
        logger.info("Pipeline 3: Complete. Generated %d posts.", len(generated))
        return generated


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    pipeline = Pipeline3AIOriginal()
    pipeline.run()
