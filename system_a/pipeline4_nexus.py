"""Pipeline 4: NEXUS V2 Strategy-Driven Posts.

Reads NEXUS V2 debate insights and content strategy,
generates X posts that build audience for revenue channels
(YouTube, Gumroad, AI music, stock content, micro-SaaS).

This pipeline bridges NEXUS V2's revenue intelligence
with system_a's X posting infrastructure.
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
DATA_DIR = BASE_DIR / "data" / "system_a" / "pipeline4"
NEXUS_DIR = BASE_DIR / "nexus" / "data" / "v2"
PROMPTS_DIR = BASE_DIR / "prompts"


class Pipeline4Nexus:
    """Generate X posts informed by NEXUS V2 revenue strategy."""

    def __init__(self):
        self.claude = ClaudeClient()
        self.quality_checker = QualityChecker(self.claude)

    def _load_latest_debate(self) -> dict | None:
        """Load the most recent debate file from NEXUS V2."""
        debate_dir = NEXUS_DIR / "debate"
        if not debate_dir.exists():
            return None

        files = sorted(debate_dir.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
        if not files:
            return None

        try:
            return json.loads(files[0].read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("Failed to load debate file %s: %s", files[0], e)
            return None

    def _load_content_assets(self) -> list[dict]:
        """Load generated content assets from NEXUS V2."""
        content_dir = NEXUS_DIR / "content"
        if not content_dir.exists():
            return []

        assets = []
        for f in sorted(content_dir.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)[:5]:
            try:
                assets.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception as e:
                logger.warning("Failed to load content file %s: %s", f, e)

        return assets

    def _extract_insights(self, debate: dict | None, assets: list[dict]) -> list[dict]:
        """Extract actionable insights for X post generation."""
        insights = []

        if debate:
            # Extract from debate synthesis
            synthesis = debate.get("debate_synthesis", {})

            # Consensus points → professional insights
            for point in synthesis.get("consensus_points", [])[:3]:
                insights.append({
                    "type": "debate",
                    "insight": point,
                    "pillar": 3,  # Finance/Investment
                })

            # Top channel priorities → tech/business insights
            ranking = synthesis.get("confidence_weighted_ranking", {})
            for item in ranking.get("channel_priority", [])[:2]:
                insights.append({
                    "type": "market",
                    "insight": f"{item['channel']}: {item['rationale']}",
                    "pillar": 5,  # Technology
                })

            # Expert recommendations
            for expert in debate.get("experts", [])[:2]:
                for rec in expert.get("recommendations", [])[:1]:
                    insights.append({
                        "type": "expert",
                        "insight": rec.get("action", ""),
                        "pillar": 5 if "AI" in rec.get("action", "") or "YouTube" in rec.get("action", "") else 3,
                    })

        # Extract from generated assets
        for asset in assets[:3]:
            title = (
                asset.get("album_name")
                or asset.get("title")
                or asset.get("product_name")
                or asset.get("collection_name")
                or asset.get("service_name")
                or ""
            )
            if title:
                asset_type = _guess_asset_type(asset)
                insights.append({
                    "type": "content",
                    "insight": f"デジタルアセット「{title}」を{asset_type}として制作。",
                    "pillar": 5,
                })

        return insights[:5]  # Max 5 insights per run

    def generate_posts(self, count: int = 3) -> list:
        """Generate strategy-driven posts."""
        prompt_template = (PROMPTS_DIR / "nexus_strategy_post.txt").read_text(encoding="utf-8")

        debate = self._load_latest_debate()
        assets = self._load_content_assets()
        insights = self._extract_insights(debate, assets)

        if not insights:
            logger.info("No NEXUS V2 insights available, skipping P4")
            return []

        generated = []
        for insight in insights[:count]:
            strategy_text = insight["insight"]
            asset_context = _build_asset_context(assets)

            prompt = prompt_template.replace(
                "{strategy_insight}", strategy_text
            ).replace(
                "{asset_context}", asset_context
            )

            try:
                result = self.claude.generate_json(prompt, temperature=0.9)
                if isinstance(result, dict):
                    result["pipeline"] = "P4"
                    result["strategy_source"] = insight.get("type", "debate")
                    if "pillar" not in result:
                        result["pillar"] = insight.get("pillar", 5)
                    generated.append(result)
            except Exception as e:
                logger.warning("P4 generation failed: %s", e)

        # Save
        today = datetime.now(JST).strftime("%Y-%m-%d")
        out_dir = DATA_DIR / "generated"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{today}.json"
        out_path.write_text(
            json.dumps(generated, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("Generated %d P4 posts -> %s", len(generated), out_path)
        return generated

    def run(self) -> list:
        """Execute full Pipeline 4 flow."""
        logger.info("Pipeline 4: Loading NEXUS V2 insights...")
        generated = self.generate_posts(count=3)
        logger.info("Pipeline 4: Complete. Generated %d posts.", len(generated))
        return generated


def _guess_asset_type(asset: dict) -> str:
    """Guess the asset type from its structure."""
    if "tracks" in asset:
        return "AI音楽アルバム"
    if "script" in asset:
        return "YouTube動画台本"
    if "sales_page" in asset:
        return "デジタル商品"
    if "assets" in asset and isinstance(asset.get("assets"), list):
        return "ストック素材コレクション"
    if "api_endpoints" in asset:
        return "マイクロSaaS"
    return "デジタルアセット"


def _build_asset_context(assets: list[dict]) -> str:
    """Build a brief summary of generated assets for the prompt."""
    if not assets:
        return "（生成アセットなし）"

    lines = []
    for asset in assets[:3]:
        title = (
            asset.get("album_name")
            or asset.get("title")
            or asset.get("product_name")
            or asset.get("collection_name")
            or ""
        )
        asset_type = _guess_asset_type(asset)
        lines.append(f"- {asset_type}: {title}")

    return "\n".join(lines)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    pipeline = Pipeline4Nexus()
    pipeline.run()
