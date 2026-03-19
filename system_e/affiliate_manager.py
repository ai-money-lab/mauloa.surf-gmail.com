"""System E — Affiliate Link Manager.

Manages affiliate programs, auto-inserts tracking links into content,
and tracks click/conversion data for revenue optimization.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
CONFIG_PATH = Path(__file__).parent / "character_config.yaml"
AFFILIATE_DIR = Path(__file__).parent.parent / "data" / "system_e" / "affiliate"

# Affiliate program definitions with tracking link templates
AFFILIATE_PROGRAMS = {
    "ag1": {
        "brand": "Athletic Greens (AG1)",
        "category": "supplements",
        "network": "impact",
        "base_url": "https://athleticgreens.com/partner/riena",
        "commission_rate": 0.20,
        "cookie_days": 30,
        "scenes": ["morning_routine", "lifestyle", "studio"],
        "keywords": ["greens", "supplement", "nutrition", "morning", "health drink"],
        "tier": 1,
    },
    "oura": {
        "brand": "Oura Ring",
        "category": "fitness_gear",
        "network": "impact",
        "base_url": "https://ouraring.com/partner/riena",
        "commission_rate": 0.10,
        "cookie_days": 30,
        "scenes": ["morning_routine", "lifestyle", "studio"],
        "keywords": ["sleep", "tracking", "data", "recovery", "hrv", "ring", "wearable"],
        "tier": 1,
    },
    "calm": {
        "brand": "Calm",
        "category": "wellness_apps",
        "network": "impact",
        "base_url": "https://calm.com/partner/riena",
        "commission_rate": 0.25,
        "cookie_days": 30,
        "scenes": ["vulnerable", "lifestyle", "morning_routine"],
        "keywords": ["meditation", "mindfulness", "calm", "stress", "sleep", "relax"],
        "tier": 1,
    },
    "lululemon": {
        "brand": "Lululemon",
        "category": "athleisure",
        "network": "rakuten",
        "base_url": "https://lululemon.com/partner/riena",
        "commission_rate": 0.07,
        "cookie_days": 7,
        "scenes": ["workout", "outdoor", "studio"],
        "keywords": ["leggings", "activewear", "yoga", "athleisure", "outfit"],
        "tier": 2,
    },
    "thorne": {
        "brand": "Thorne",
        "category": "supplements",
        "network": "shareasale",
        "base_url": "https://thorne.com/partner/riena",
        "commission_rate": 0.15,
        "cookie_days": 45,
        "scenes": ["morning_routine", "lifestyle", "workout"],
        "keywords": ["supplement", "vitamin", "magnesium", "protein", "recovery"],
        "tier": 1,
    },
    "whoop": {
        "brand": "Whoop",
        "category": "fitness_gear",
        "network": "direct",
        "base_url": "https://join.whoop.com/riena",
        "commission_rate": 0.15,
        "cookie_days": 30,
        "scenes": ["workout", "morning_routine", "outdoor"],
        "keywords": ["strain", "recovery", "hrv", "fitness tracker", "workout data"],
        "tier": 1,
    },
    "amazon": {
        "brand": "Amazon Associates",
        "category": "general",
        "network": "amazon",
        "base_url": "https://amazon.com/shop/riena",
        "commission_rate": 0.04,
        "cookie_days": 1,
        "scenes": [],
        "keywords": [],
        "tier": 3,
    },
    "ippodo": {
        "brand": "Ippodo Tea",
        "category": "supplements",
        "network": "direct",
        "base_url": "https://ippodo-tea.co.jp/partner/riena",
        "commission_rate": 0.12,
        "cookie_days": 30,
        "scenes": ["morning_routine", "lifestyle", "cat_moments"],
        "keywords": ["matcha", "tea", "ritual", "morning", "japanese"],
        "tier": 1,
    },
}


def load_character_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


class AffiliateManager:
    """Manage affiliate links, auto-insertion, and tracking."""

    def __init__(self):
        self.config = load_character_config()
        self.programs = AFFILIATE_PROGRAMS.copy()
        self.categories = self.config.get("monetization", {}).get(
            "affiliate_categories", []
        )
        AFFILIATE_DIR.mkdir(parents=True, exist_ok=True)
        self._rotation_index: dict[str, int] = {}

    def get_affiliate_link(self, product_key: str, platform: str = "x") -> str | None:
        """Get tracking link for a product."""
        program = self.programs.get(product_key)
        if not program:
            return None

        base = program["base_url"]
        utm = f"?utm_source={platform}&utm_medium=social&utm_campaign=riena"
        link = f"{base}{utm}"

        self._log_link_generation(product_key, platform)
        return link

    def match_content_to_affiliate(
        self, scene: str, text: str, content_type: str
    ) -> str | None:
        """Find the best affiliate match for content."""
        if content_type in ("poll", "engagement"):
            return None

        text_lower = text.lower() if text else ""
        candidates: list[tuple[str, int]] = []

        for key, program in self.programs.items():
            score = 0
            if scene in program["scenes"]:
                score += 3
            for kw in program["keywords"]:
                if kw in text_lower:
                    score += 2
            score += max(0, 4 - program["tier"])

            if score > 0:
                candidates.append((key, score))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]

    def enrich_content(self, content: dict) -> dict:
        """Add affiliate link to content if relevant.

        Non-destructive: adds 'affiliate' field to content dict.
        Respects the 10% sponsored ratio.
        """
        scene = content.get("scene", "")
        text = content.get("text", "")
        content_type = content.get("type", "standard")

        if content_type in ("poll", "engagement"):
            return content

        if not self._check_sponsored_ratio():
            logger.info("Skipping affiliate: sponsored ratio limit reached")
            return content

        match = self.match_content_to_affiliate(scene, text, content_type)
        if not match:
            return content

        program = self.programs[match]
        link = self.get_affiliate_link(match, platform="x")

        content["affiliate"] = {
            "product_key": match,
            "brand": program["brand"],
            "link": link,
            "commission_rate": program["commission_rate"],
            "disclosure_required": True,
        }

        logger.info(
            "Affiliate enriched: %s -> %s (%.0f%% commission)",
            scene,
            program["brand"],
            program["commission_rate"] * 100,
        )
        return content

    def check_compliance(self, content: dict) -> dict:
        """Verify FTC compliance for content with affiliate links."""
        issues = []
        affiliate = content.get("affiliate")
        if not affiliate:
            return {"compliant": True, "issues": []}

        text = content.get("text", "")

        if affiliate.get("disclosure_required"):
            disclosure_markers = ["#ad", "#sponsored", "#affiliate", "#partner"]
            has_disclosure = any(m in text.lower() for m in disclosure_markers)
            if not has_disclosure:
                issues.append("Missing FTC disclosure (#ad or equivalent)")

        product_key = affiliate.get("product_key", "")
        if not self._check_narrative_history(product_key):
            issues.append(
                f"Product '{product_key}' not in narrative for 2+ weeks yet"
            )

        return {"compliant": len(issues) == 0, "issues": issues}

    def rotate_links(self) -> str | None:
        """Select next affiliate link in rotation to avoid spam."""
        tier1 = [k for k, v in self.programs.items() if v["tier"] == 1]
        if not tier1:
            return None

        idx = self._rotation_index.get("main", 0)
        selected = tier1[idx % len(tier1)]
        self._rotation_index["main"] = idx + 1
        return selected

    def get_monthly_earnings(self, month: str | None = None) -> dict:
        """Get affiliate earnings summary for a month."""
        if not month:
            month = datetime.now(JST).strftime("%Y-%m")

        earnings_file = AFFILIATE_DIR / "earnings_log.json"
        data = self._load_json(earnings_file)
        monthly = [r for r in data if r.get("date", "").startswith(month)]

        by_program: dict[str, float] = {}
        total = 0.0
        for item in monthly:
            key = item.get("product_key", "unknown")
            amount = item.get("amount", 0.0)
            by_program[key] = by_program.get(key, 0) + amount
            total += amount

        return {
            "month": month,
            "total_earnings": round(total, 2),
            "by_program": {k: round(v, 2) for k, v in by_program.items()},
            "click_count": sum(1 for r in monthly if r.get("event") == "click"),
            "conversion_count": sum(
                1 for r in monthly if r.get("event") == "conversion"
            ),
        }

    def record_click(self, product_key: str, platform: str) -> None:
        """Record an affiliate link click."""
        self._record_event("click", product_key, platform)

    def record_conversion(
        self, product_key: str, platform: str, amount: float
    ) -> None:
        """Record an affiliate conversion (sale)."""
        self._record_event("conversion", product_key, platform, amount=amount)

    def get_program_stats(self) -> dict:
        """Get performance stats for all affiliate programs."""
        earnings_file = AFFILIATE_DIR / "earnings_log.json"
        data = self._load_json(earnings_file)

        stats: dict[str, dict] = {}
        for item in data:
            key = item.get("product_key", "unknown")
            if key not in stats:
                stats[key] = {
                    "brand": self.programs.get(key, {}).get("brand", key),
                    "clicks": 0,
                    "conversions": 0,
                    "revenue": 0.0,
                }
            if item.get("event") == "click":
                stats[key]["clicks"] += 1
            elif item.get("event") == "conversion":
                stats[key]["conversions"] += 1
                stats[key]["revenue"] += item.get("amount", 0.0)

        for s in stats.values():
            if s["clicks"] > 0:
                s["conversion_rate"] = round(s["conversions"] / s["clicks"] * 100, 1)
            else:
                s["conversion_rate"] = 0.0

        return stats

    def add_to_narrative(self, product_key: str) -> None:
        """Mark a product as appearing in narrative content."""
        history_file = AFFILIATE_DIR / "narrative_history.json"
        data = self._load_json(history_file)

        existing = next(
            (item for item in data if item.get("product_key") == product_key), None
        )
        if existing:
            existing["mention_count"] = existing.get("mention_count", 0) + 1
            existing["last_mentioned"] = datetime.now(JST).isoformat()
        else:
            data.append({
                "product_key": product_key,
                "first_mentioned": datetime.now(JST).isoformat(),
                "last_mentioned": datetime.now(JST).isoformat(),
                "mention_count": 1,
            })
        self._save_json(history_file, data)

    def _check_sponsored_ratio(self) -> bool:
        """Ensure max 1 sponsored post per 10 organic (10% ratio)."""
        link_log = AFFILIATE_DIR / "link_generation_log.json"
        data = self._load_json(link_log)
        recent = data[-10:] if len(data) >= 10 else data
        if not recent:
            return True
        sponsored = sum(1 for r in recent if r.get("had_affiliate"))
        return sponsored < max(1, len(recent) // 10 + 1)

    def _check_narrative_history(self, product_key: str) -> bool:
        """Check if product has been in narrative for 2+ weeks."""
        history_file = AFFILIATE_DIR / "narrative_history.json"
        data = self._load_json(history_file)

        for item in data:
            if item.get("product_key") == product_key:
                first_mention = item.get("first_mentioned")
                if first_mention:
                    try:
                        mentioned_date = datetime.fromisoformat(first_mention)
                        days = (datetime.now(JST) - mentioned_date).days
                        return days >= 14
                    except (ValueError, TypeError):
                        pass
        return False

    def _log_link_generation(self, product_key: str, platform: str) -> None:
        log_file = AFFILIATE_DIR / "link_generation_log.json"
        data = self._load_json(log_file)
        data.append({
            "product_key": product_key,
            "platform": platform,
            "had_affiliate": True,
            "timestamp": datetime.now(JST).isoformat(),
        })
        self._save_json(log_file, data)

    def _record_event(
        self, event: str, product_key: str, platform: str, amount: float = 0.0
    ) -> None:
        earnings_file = AFFILIATE_DIR / "earnings_log.json"
        data = self._load_json(earnings_file)
        data.append({
            "event": event,
            "product_key": product_key,
            "platform": platform,
            "amount": amount,
            "date": datetime.now(JST).strftime("%Y-%m-%d"),
            "timestamp": datetime.now(JST).isoformat(),
        })
        self._save_json(earnings_file, data)
        logger.info("Affiliate %s: %s on %s ($%.2f)", event, product_key, platform, amount)

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
    manager = AffiliateManager()
    print("Affiliate programs:", list(manager.programs.keys()))
    print("Monthly earnings:", json.dumps(manager.get_monthly_earnings(), indent=2))
