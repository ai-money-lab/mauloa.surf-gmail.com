"""System D: Results Publishing Engine.

Converts System B/C achievements into X post content
for building authority and attracting new clients.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

from core.claude_client import ClaudeClient
from core.quality_checker import QualityChecker

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
PROMPTS_DIR = BASE_DIR / "prompts"


class ResultsContentGenerator:
    """Generate X posts from business results and market insights."""

    def __init__(self):
        self.claude = ClaudeClient()
        self.quality_checker = QualityChecker(self.claude)

    def _load_system_b_results(self) -> list:
        """Load completed order results from System B."""
        deliverables_dir = DATA_DIR / "system_b" / "deliverables"
        results = []

        if not deliverables_dir.exists():
            return results

        for order_dir in deliverables_dir.iterdir():
            if order_dir.is_dir():
                for f in order_dir.glob("*.json"):
                    try:
                        data = json.loads(f.read_text(encoding="utf-8"))
                        results.append({
                            "type": "order_result",
                            "order_id": order_dir.name,
                            "data": data,
                        })
                    except Exception:
                        pass

        return results

    def _load_system_c_insights(self) -> list:
        """Load notable findings from System C."""
        insights = []

        for subdir in ["daily", "weekly"]:
            path = DATA_DIR / "system_c" / subdir
            if not path.exists():
                continue
            files = sorted(path.glob("*.json"), reverse=True)[:3]
            for f in files:
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    insights.append({
                        "type": f"system_c_{subdir}",
                        "file": f.name,
                        "data": data,
                    })
                except Exception:
                    pass

        return insights

    def _load_system_a_performance(self) -> list:
        """Load X performance data."""
        perf = []
        winning_path = DATA_DIR / "system_a" / "winning_patterns.json"
        if winning_path.exists():
            try:
                data = json.loads(winning_path.read_text(encoding="utf-8"))
                perf.append({"type": "winning_patterns", "data": data})
            except Exception:
                pass
        return perf

    def generate_posts(self) -> list:
        """Generate results-based posts."""
        prompt_template = (PROMPTS_DIR / "results_to_post.txt").read_text(encoding="utf-8")

        # Collect all source data
        sources = {
            "order_results": self._load_system_b_results(),
            "market_insights": self._load_system_c_insights(),
            "performance_data": self._load_system_a_performance(),
        }

        # Generate posts for each notable item
        generated = []
        items_to_convert = []

        # From order results
        for result in sources["order_results"][:3]:
            items_to_convert.append({
                "type": "案件実績",
                "target_pillars": [3, 5],
                "data": result,
            })

        # From market insights
        for insight in sources["market_insights"][:3]:
            items_to_convert.append({
                "type": "市場速報",
                "target_pillars": [1, 3],
                "data": insight,
            })

        for item in items_to_convert:
            prompt = (
                f"{prompt_template}\n\n"
                f"## 変換元データ:\n"
                f"種別: {item['type']}\n"
                f"データ:\n{json.dumps(item['data'], ensure_ascii=False, indent=2)[:2000]}"
            )

            try:
                result = self.claude.generate_json(prompt, temperature=0.8)
                if isinstance(result, dict):
                    result["source_type"] = item["type"]
                    result["target_pillars"] = item["target_pillars"]
                    result["pipeline"] = "D"
                    generated.append(result)
            except Exception as e:
                logger.warning("Results post generation failed: %s", e)

        # Quality check all generated posts
        approved = []
        for post in generated:
            text = post.get("pattern_a", post.get("A", post.get("text", "")))
            if isinstance(text, dict):
                text = text.get("text", "")
            if text:
                qr = self.quality_checker.check(
                    profile="x_post", content=text, context="System D results post"
                )
                post["quality_result"] = qr
                if qr.get("result") == "auto_approved":
                    approved.append(post)

        logger.info("Generated %d results posts (%d approved)", len(generated), len(approved))
        return approved

    def run(self) -> list:
        """Execute results content generation."""
        logger.info("System D: Generating results content...")
        posts = self.generate_posts()
        logger.info("System D: Complete. %d posts ready.", len(posts))
        return posts


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    generator = ResultsContentGenerator()
    generator.run()
