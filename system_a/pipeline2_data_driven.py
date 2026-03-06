"""Pipeline 2: Data-Driven Original Posts.

Uses System C data + domestic news/trends to generate
fact-based original posts from HIROKI's perspective.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

from core.claude_client import ClaudeClient
from core.quality_checker import QualityChecker
from core.engagement_learner import EngagementLearner
from system_a.collect_jp_trends import JpTrendsCollector

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data" / "system_a" / "pipeline2"
PROMPTS_DIR = BASE_DIR / "prompts"


class Pipeline2DataDriven:
    """Generate data-driven original posts from market data and trends."""

    def __init__(self):
        self.claude = ClaudeClient()
        self.quality_checker = QualityChecker(self.claude)
        self.trends_collector = JpTrendsCollector()
        self.learner = EngagementLearner()

    def collect_sources(self) -> dict:
        """Collect data from System C and domestic trends."""
        return self.trends_collector.run()

    def generate_posts(self, sources: dict) -> list:
        """Generate posts from collected data sources."""
        prompt_template = (PROMPTS_DIR / "data_to_post.txt").read_text(encoding="utf-8")
        generated = []

        items = sources.get("filtered_items", [])
        system_c = sources.get("system_c_data", [])

        # Combine filtered items and system_c data for generation
        materials = []
        for item in items[:10]:
            materials.append({
                "type": "news_trend",
                "data": item,
            })
        for sc in system_c:
            materials.append({
                "type": "system_c",
                "data": sc,
            })

        # Get learning context from past performance
        learning_context = self.learner.build_generation_context()

        for material in materials[:8]:
            learning_section = f"\n\n{learning_context}" if learning_context else ""
            prompt = (
                f"{prompt_template}\n\n"
                f"## 素材データ:\n{json.dumps(material, ensure_ascii=False, indent=2)}"
                f"{learning_section}"
            )
            try:
                result = self.claude.generate_json(prompt, temperature=0.8)
                if isinstance(result, dict):
                    result["pipeline"] = "P2"
                    result["source_material"] = material
                    generated.append(result)
            except Exception as e:
                logger.warning("Post generation failed for material: %s", e)

        # Save
        today = datetime.now(JST).strftime("%Y-%m-%d")
        out_dir = DATA_DIR / "generated"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{today}.json"
        out_path.write_text(
            json.dumps(generated, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("Generated %d P2 posts -> %s", len(generated), out_path)
        return generated

    def run(self) -> list:
        """Execute full Pipeline 2 flow."""
        logger.info("Pipeline 2: Collecting data sources...")
        sources = self.collect_sources()
        logger.info("Pipeline 2: Generating posts from data...")
        generated = self.generate_posts(sources)
        logger.info("Pipeline 2: Complete. Generated %d posts.", len(generated))
        return generated


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    pipeline = Pipeline2DataDriven()
    pipeline.run()
