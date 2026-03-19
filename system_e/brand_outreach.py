"""System E — Brand Outreach Automation Engine.

Automates the 3-phase brand partnership strategy:
Phase 1 (Month 1-3): Foundation — media kit, spec work, metrics
Phase 2 (Month 4-6): Visibility — marketplace listings, agency pitches
Phase 3 (Month 7-12): Direct outreach — personalized pitches, deals
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml

from core.claude_client import ClaudeClient

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
STRATEGY_PATH = Path(__file__).parent / "brand_partnership_strategy.yaml"
CHARACTER_PATH = Path(__file__).parent / "character_config.yaml"
BRAND_DIR = Path(__file__).parent.parent / "data" / "system_e" / "brand_deals"

DEAL_STAGES = [
    "prospect",
    "spec_work",
    "contacted",
    "negotiating",
    "active",
    "completed",
    "declined",
]


def load_strategy() -> dict:
    with open(STRATEGY_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_character_config() -> dict:
    with open(CHARACTER_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


class BrandOutreachEngine:
    """Automate brand partnership pipeline from prospect to deal."""

    def __init__(self):
        self.claude = ClaudeClient()
        self.strategy = load_strategy()
        self.character = load_character_config()["character"]
        BRAND_DIR.mkdir(parents=True, exist_ok=True)

    # ─── Pipeline Management ───

    def add_prospect(self, brand_name: str, tier: int, category: str,
                     contact_info: str = "", notes: str = "") -> dict:
        """Add a brand to the outreach pipeline."""
        pipeline = self._load_pipeline()

        prospect = {
            "brand_name": brand_name,
            "tier": tier,
            "category": category,
            "stage": "prospect",
            "contact_info": contact_info,
            "notes": notes,
            "created_at": datetime.now(JST).isoformat(),
            "updated_at": datetime.now(JST).isoformat(),
            "outreach_history": [],
            "deal_value": 0.0,
        }

        pipeline.append(prospect)
        self._save_pipeline(pipeline)
        logger.info("Added prospect: %s (Tier %d)", brand_name, tier)
        return prospect

    def advance_stage(self, brand_name: str, new_stage: str,
                      notes: str = "") -> dict | None:
        """Move a brand to the next pipeline stage."""
        if new_stage not in DEAL_STAGES:
            logger.error("Invalid stage: %s", new_stage)
            return None

        pipeline = self._load_pipeline()
        brand = next((b for b in pipeline if b["brand_name"] == brand_name), None)
        if not brand:
            logger.error("Brand not found: %s", brand_name)
            return None

        old_stage = brand["stage"]
        brand["stage"] = new_stage
        brand["updated_at"] = datetime.now(JST).isoformat()
        brand["outreach_history"].append({
            "from": old_stage,
            "to": new_stage,
            "notes": notes,
            "date": datetime.now(JST).isoformat(),
        })

        self._save_pipeline(pipeline)
        logger.info("Advanced %s: %s -> %s", brand_name, old_stage, new_stage)
        return brand

    def get_pipeline_summary(self) -> dict:
        """Get summary of current brand pipeline."""
        pipeline = self._load_pipeline()
        by_stage: dict[str, list] = {stage: [] for stage in DEAL_STAGES}

        for brand in pipeline:
            stage = brand.get("stage", "prospect")
            by_stage.setdefault(stage, []).append(brand["brand_name"])

        active_value = sum(
            b.get("deal_value", 0) for b in pipeline
            if b.get("stage") in ("negotiating", "active")
        )
        completed_value = sum(
            b.get("deal_value", 0) for b in pipeline
            if b.get("stage") == "completed"
        )

        return {
            "total_brands": len(pipeline),
            "by_stage": {k: len(v) for k, v in by_stage.items()},
            "brand_names_by_stage": by_stage,
            "active_pipeline_value": active_value,
            "completed_revenue": completed_value,
        }

    # ─── Trigger Content Generation ───

    def generate_trigger_content(self, trigger_type: str,
                                 product_key: str = "",
                                 context: str = "") -> dict:
        """Generate brand-attracting trigger content.

        Args:
            trigger_type: One of 'product_in_life', 'data_story',
                         'honest_review', 'dream_mention'.
            product_key: Optional product/brand to reference.
            context: Additional context for generation.
        """
        char = self.character
        trigger_prompts = {
            "product_in_life": (
                f"Write a short X post (max 250 chars) where {char['name']} "
                f"shows a product naturally in her life. "
                f"{'Product hint: ' + product_key + '. ' if product_key else ''}"
                f"Do NOT mention the brand name directly. "
                f"The product should just be there, in the background. "
                f"Make it feel like a real slice of life, not an ad."
            ),
            "data_story": (
                f"Write a short X post (max 280 chars) where {char['name']} "
                f"shares a 30-day tracking story with real-feeling data. "
                f"{'Context: ' + context + '. ' if context else ''}"
                f"Include specific numbers (sleep score, hours, percentages). "
                f"Mention what she changed — only one thing. "
                f"Never say something 'worked immediately.' Data takes time."
            ),
            "honest_review": (
                f"Write a short X post (max 280 chars) where {char['name']} "
                f"gives an honest review of products she tried. "
                f"{'Category: ' + context + '. ' if context else ''}"
                f"Include what she liked AND didn't like. "
                f"Be specific about ingredients/features. "
                f"The point: brands trust honest reviewers."
            ),
            "dream_mention": (
                f"Write a short X post (max 250 chars) where {char['name']} "
                f"mentions a brand in the context of a dream or aspiration. "
                f"{'Brand hint: ' + product_key + '. ' if product_key else ''}"
                f"This is NOT a review — it's a genuine wish. "
                f"Example: 'Someday I want to open a cafe with Ippodo matcha.' "
                f"Max 1 per month. Make it feel real."
            ),
        }

        prompt = trigger_prompts.get(trigger_type)
        if not prompt:
            logger.error("Unknown trigger type: %s", trigger_type)
            return {"error": f"Unknown trigger type: {trigger_type}"}

        system = (
            f"You are ghostwriting as {char['name']}, "
            f"{char['tagline']}. "
            f"Personality: {', '.join(char['personality']['traits'])}. "
            f"Write in first person. Keep it authentic and natural."
        )

        try:
            text = self.claude.generate(
                prompt=prompt + "\n\nReturn just the post text, nothing else.",
                system=system,
                max_tokens=512,
                temperature=0.8,
            ).strip().strip('"')

            return {
                "text": text,
                "trigger_type": trigger_type,
                "product_key": product_key,
                "generated_at": datetime.now(JST).isoformat(),
            }
        except Exception as e:
            logger.error("Trigger content generation failed: %s", e)
            return {"error": str(e), "trigger_type": trigger_type}

    # ─── Media Kit Generation ───

    def generate_media_kit_data(
        self,
        followers: int,
        engagement_rate: float,
        fanvue_subscribers: int = 0,
    ) -> dict:
        """Generate media kit data with pricing.

        Uses formula: Base rate = (Followers / 1000) * Engagement Rate * $10
        """
        base_rate = (followers / 1000) * engagement_rate * 10

        pricing = {
            "x_post": max(500, round(base_rate)),
            "x_thread": max(1000, round(base_rate * 2)),
            "instagram_post": max(750, round(base_rate * 1.5)),
            "instagram_story_set": max(500, round(base_rate)),
            "fanvue_exclusive": max(2000, round(base_rate * 4)),
            "full_campaign_3_posts": max(2000, round(base_rate * 5)),
        }

        adjustments = {
            "exclusivity_30day": 1.50,
            "usage_rights_6month": 1.30,
            "whitelisting_ads": 1.40,
            "rush_under_7days": 1.25,
        }

        char = self.character
        media_kit = {
            "creator": {
                "name": char["name"],
                "tagline": char["tagline"],
                "type": "AI Wellness Creator",
                "origin": char["backstory"]["origin"],
                "story": char["personality"]["wounds"]["primary"],
            },
            "audience": {
                "followers": followers,
                "engagement_rate": engagement_rate,
                "fanvue_subscribers": fanvue_subscribers,
                "demographics": self.character.get("content_voice", {}),
                "target": self.character.get("niche", {}),
            },
            "pricing": pricing,
            "adjustments": adjustments,
            "brand_safety": {
                "ai_disclosure": "Full FTC compliance — bio + per-sponsored-post disclosure",
                "content_ratio": "Max 1 sponsored per 10 organic posts",
                "review_policy": "Honest reviews only — negative feedback included",
                "kill_clause": "Right to pull content if product recalled/controversial",
            },
            "generated_at": datetime.now(JST).isoformat(),
        }

        media_kit_file = BRAND_DIR / "media_kit.json"
        self._save_json(media_kit_file, media_kit)
        logger.info("Media kit generated: base rate $%.0f", base_rate)
        return media_kit

    def calculate_deal_price(
        self,
        deliverable: str,
        followers: int,
        engagement_rate: float,
        exclusivity: bool = False,
        usage_rights: bool = False,
        whitelisting: bool = False,
        rush: bool = False,
    ) -> float:
        """Calculate price for a specific brand deal."""
        base_rate = (followers / 1000) * engagement_rate * 10

        multipliers = {
            "x_post": 1.0,
            "x_thread": 2.0,
            "instagram_post": 1.5,
            "instagram_story_set": 1.0,
            "fanvue_exclusive": 4.0,
            "full_campaign_3_posts": 5.0,
        }

        price = base_rate * multipliers.get(deliverable, 1.0)

        if exclusivity:
            price *= 1.50
        if usage_rights:
            price *= 1.30
        if whitelisting:
            price *= 1.40
        if rush:
            price *= 1.25

        minimums = {
            "x_post": 500,
            "x_thread": 1000,
            "instagram_post": 750,
            "instagram_story_set": 500,
            "fanvue_exclusive": 2000,
            "full_campaign_3_posts": 2000,
        }

        return max(minimums.get(deliverable, 500), round(price, 2))

    # ─── Outreach Tracking ───

    def record_outreach(self, brand_name: str, method: str,
                        notes: str = "") -> bool:
        """Record an outreach attempt to a brand."""
        if not self._check_outreach_limit():
            logger.warning("Weekly outreach limit reached (5/week)")
            return False

        pipeline = self._load_pipeline()
        brand = next((b for b in pipeline if b["brand_name"] == brand_name), None)
        if not brand:
            logger.error("Brand not found: %s", brand_name)
            return False

        brand["outreach_history"].append({
            "method": method,
            "notes": notes,
            "date": datetime.now(JST).isoformat(),
        })
        brand["updated_at"] = datetime.now(JST).isoformat()

        self._save_pipeline(pipeline)
        logger.info("Outreach recorded: %s via %s", brand_name, method)
        return True

    def get_outreach_stats(self) -> dict:
        """Get outreach activity statistics."""
        pipeline = self._load_pipeline()
        now = datetime.now(JST)
        week_ago = now - timedelta(days=7)

        total_outreach = 0
        weekly_outreach = 0
        response_count = 0

        for brand in pipeline:
            for attempt in brand.get("outreach_history", []):
                total_outreach += 1
                try:
                    attempt_date = datetime.fromisoformat(attempt.get("date", ""))
                    if attempt_date > week_ago:
                        weekly_outreach += 1
                except (ValueError, TypeError):
                    pass
                if attempt.get("to") in ("negotiating", "active"):
                    response_count += 1

        return {
            "total_outreach_attempts": total_outreach,
            "this_week": weekly_outreach,
            "weekly_limit": 5,
            "response_rate": round(
                response_count / max(1, total_outreach) * 100, 1
            ),
        }

    # ─── Spec Work Management ───

    def create_spec_work(self, brand_name: str, content_ideas: list[str]) -> dict:
        """Register spec work for a target brand."""
        spec_file = BRAND_DIR / "spec_work.json"
        specs = self._load_json(spec_file)

        spec = {
            "brand_name": brand_name,
            "content_ideas": content_ideas,
            "status": "planned",
            "created_at": datetime.now(JST).isoformat(),
            "posts_created": [],
        }

        specs.append(spec)
        self._save_json(spec_file, specs)
        logger.info("Spec work created for %s (%d ideas)", brand_name, len(content_ideas))
        return spec

    def mark_spec_ready(self, brand_name: str, post_ids: list[str]) -> bool:
        """Mark spec work as ready to send to brand."""
        spec_file = BRAND_DIR / "spec_work.json"
        specs = self._load_json(spec_file)

        spec = next((s for s in specs if s["brand_name"] == brand_name), None)
        if not spec:
            return False

        spec["status"] = "ready"
        spec["posts_created"] = post_ids
        spec["ready_at"] = datetime.now(JST).isoformat()

        self._save_json(spec_file, specs)
        logger.info("Spec work ready for %s", brand_name)
        return True

    def get_spec_work_status(self) -> list[dict]:
        """Get status of all spec work."""
        spec_file = BRAND_DIR / "spec_work.json"
        return self._load_json(spec_file)

    # ─── Compliance ───

    def check_sponsored_content_compliance(self, content: dict) -> dict:
        """Verify sponsored content meets all requirements."""
        issues = []
        text = content.get("text", "")

        # Double disclosure check
        has_ad = "#ad" in text.lower()
        has_ai = "#aicreator" in text.lower() or "#aigenerated" in text.lower()

        if not has_ad:
            issues.append("Missing #ad disclosure")
        if not has_ai:
            issues.append("Missing #AICreator disclosure")

        # 10% ratio check
        if not self._check_sponsored_ratio():
            issues.append("Sponsored post ratio exceeds 10%")

        return {"compliant": len(issues) == 0, "issues": issues}

    def _check_sponsored_ratio(self) -> bool:
        """Check if sponsored content is within 10% ratio."""
        ratio_file = BRAND_DIR / "posting_ratio.json"
        data = self._load_json(ratio_file)
        if not data:
            return True

        recent = data[-20:]
        sponsored = sum(1 for p in recent if p.get("sponsored"))
        return sponsored < max(1, len(recent) // 10 + 1)

    def _check_outreach_limit(self) -> bool:
        """Check if weekly outreach limit (5/week) is reached."""
        pipeline = self._load_pipeline()
        now = datetime.now(JST)
        week_ago = now - timedelta(days=7)
        weekly_count = 0

        for brand in pipeline:
            for attempt in brand.get("outreach_history", []):
                try:
                    attempt_date = datetime.fromisoformat(attempt.get("date", ""))
                    if attempt_date > week_ago:
                        weekly_count += 1
                except (ValueError, TypeError):
                    pass

        return weekly_count < 5

    def _load_pipeline(self) -> list:
        pipeline_file = BRAND_DIR / "pipeline.json"
        return self._load_json(pipeline_file)

    def _save_pipeline(self, data: list) -> None:
        pipeline_file = BRAND_DIR / "pipeline.json"
        self._save_json(pipeline_file, data)

    def _load_json(self, path: Path) -> list:
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save_json(self, path: Path, data) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    engine = BrandOutreachEngine()
    print("Pipeline:", json.dumps(engine.get_pipeline_summary(), indent=2))
    print("Outreach:", json.dumps(engine.get_outreach_stats(), indent=2))
