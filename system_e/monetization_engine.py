"""System E — Content Monetization Engine.

Central orchestrator that ties together all monetization systems:
affiliates, brand partnerships, Fanvue subscriptions, and analytics.
Provides revenue dashboard, A/B testing, and optimization.
"""

import json
import logging
import math
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
DATA_DIR = Path(__file__).parent.parent / "data" / "system_e"
AB_TEST_DIR = DATA_DIR / "ab_tests"
ANALYTICS_DIR = DATA_DIR / "analytics"
CONFIG_PATH = Path(__file__).parent.parent / "config" / "config.yaml"
STRATEGY_PATH = Path(__file__).parent / "brand_partnership_strategy.yaml"


class MonetizationEngine:
    """Central monetization orchestrator for System E."""

    def __init__(self):
        from system_e.affiliate_manager import AffiliateManager
        from system_e.brand_outreach import BrandOutreachEngine
        from system_e.fanvue_manager import FanvueManager
        from system_e.analytics import Analytics

        self.affiliate = AffiliateManager()
        self.brand = BrandOutreachEngine()
        self.fanvue = FanvueManager()
        self.analytics = Analytics()
        AB_TEST_DIR.mkdir(parents=True, exist_ok=True)
        ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)

    # ─── Revenue Dashboard ───

    def get_revenue_dashboard(self, month: str | None = None) -> dict:
        """Aggregate revenue from all sources."""
        if not month:
            month = datetime.now(JST).strftime("%Y-%m")

        # Affiliate revenue
        affiliate_data = self.affiliate.get_monthly_earnings(month)

        # Fanvue revenue
        fanvue_stats = self.fanvue.get_tier_stats()
        fanvue_revenue = self._estimate_fanvue_revenue(fanvue_stats)

        # Brand deal revenue
        brand_summary = self.brand.get_pipeline_summary()
        brand_revenue = brand_summary.get("completed_revenue", 0)

        # Analytics revenue (X ad revenue etc)
        analytics_revenue = self.analytics.get_revenue_summary(month)

        total = (
            affiliate_data.get("total_earnings", 0)
            + fanvue_revenue
            + brand_revenue
            + analytics_revenue.get("total_revenue", 0)
        )

        # Load KPI targets
        targets = self._load_kpi_targets()

        dashboard = {
            "month": month,
            "total_revenue": round(total, 2),
            "sources": {
                "affiliate": {
                    "revenue": affiliate_data.get("total_earnings", 0),
                    "details": affiliate_data.get("by_program", {}),
                },
                "fanvue": {
                    "revenue": round(fanvue_revenue, 2),
                    "tier_breakdown": fanvue_stats,
                },
                "brand_deals": {
                    "revenue": brand_revenue,
                    "active_pipeline": brand_summary.get("active_pipeline_value", 0),
                },
                "other": {
                    "revenue": analytics_revenue.get("total_revenue", 0),
                    "details": analytics_revenue.get("by_source", {}),
                },
            },
            "targets": targets,
            "generated_at": datetime.now(JST).isoformat(),
        }

        return dashboard

    # ─── Content Monetization Scoring ───

    def score_monetization_potential(self, content: dict) -> dict:
        """Score content for monetization potential (0-100)."""
        score = 0
        reasons = []
        scene = content.get("scene", "")
        content_type = content.get("type", "standard")
        text = content.get("text", "")

        # Scene scoring
        high_value_scenes = {"workout": 20, "morning_routine": 18, "studio": 15,
                             "lifestyle": 12, "outdoor": 10}
        scene_score = high_value_scenes.get(scene, 5)
        score += scene_score
        reasons.append(f"scene '{scene}': +{scene_score}")

        # Content type scoring
        type_scores = {"promo": 25, "standard": 15, "story": 12,
                       "thread": 20, "engagement": 8, "poll": 5}
        type_score = type_scores.get(content_type, 10)
        score += type_score
        reasons.append(f"type '{content_type}': +{type_score}")

        # Affiliate opportunity
        match = self.affiliate.match_content_to_affiliate(scene, text, content_type)
        if match:
            score += 20
            reasons.append(f"affiliate match '{match}': +20")

        # Fanvue upsell potential
        if scene in ("studio", "workout", "vulnerable"):
            score += 15
            reasons.append("fanvue upsell potential: +15")

        # Keyword richness
        monetizable_keywords = [
            "routine", "review", "tried", "favorite", "data", "results",
            "tracking", "supplement", "workout", "sleep", "recovery",
        ]
        kw_count = sum(1 for kw in monetizable_keywords if kw in text.lower())
        kw_score = min(20, kw_count * 5)
        if kw_score > 0:
            score += kw_score
            reasons.append(f"keywords ({kw_count} matches): +{kw_score}")

        score = min(100, score)

        # Recommend action
        if score >= 70:
            action = "affiliate_link"
        elif score >= 50:
            action = "fanvue_teaser"
        elif score >= 30:
            action = "brand_trigger"
        else:
            action = "organic"

        return {
            "score": score,
            "action": action,
            "reasons": reasons,
        }

    # ─── A/B Testing ───

    def create_ab_test(self, test_name: str, variants: list[dict],
                       metric: str = "engagement_rate") -> dict:
        """Create an A/B test for content optimization.

        Args:
            test_name: Descriptive name for the test.
            variants: List of variant dicts with 'name' and 'content'.
            metric: Metric to optimize ('engagement_rate', 'clicks', 'conversions').
        """
        test = {
            "test_name": test_name,
            "variants": [
                {
                    "name": v["name"],
                    "content": v["content"],
                    "impressions": 0,
                    "successes": 0,
                }
                for v in variants
            ],
            "metric": metric,
            "status": "running",
            "created_at": datetime.now(JST).isoformat(),
        }

        test_file = AB_TEST_DIR / f"{test_name.replace(' ', '_')}.json"
        self._save_json(test_file, test)
        logger.info("A/B test created: %s (%d variants)", test_name, len(variants))
        return test

    def record_ab_result(self, test_name: str, variant_name: str,
                         impressions: int = 1, successes: int = 0) -> None:
        """Record a result for an A/B test variant."""
        test_file = AB_TEST_DIR / f"{test_name.replace(' ', '_')}.json"
        test = self._load_json_dict(test_file)
        if not test:
            return

        for variant in test.get("variants", []):
            if variant["name"] == variant_name:
                variant["impressions"] += impressions
                variant["successes"] += successes
                break

        self._save_json(test_file, test)

    def evaluate_ab_test(self, test_name: str) -> dict:
        """Evaluate an A/B test for statistical significance."""
        test_file = AB_TEST_DIR / f"{test_name.replace(' ', '_')}.json"
        test = self._load_json_dict(test_file)
        if not test:
            return {"error": "Test not found"}

        variants = test.get("variants", [])
        if len(variants) < 2:
            return {"error": "Need at least 2 variants"}

        results = []
        for v in variants:
            rate = v["successes"] / max(1, v["impressions"])
            results.append({
                "name": v["name"],
                "impressions": v["impressions"],
                "successes": v["successes"],
                "rate": round(rate * 100, 2),
            })

        results.sort(key=lambda x: x["rate"], reverse=True)

        # Simple significance check (chi-square approximation)
        significant = False
        if len(results) >= 2:
            a = results[0]
            b = results[1]
            if a["impressions"] >= 30 and b["impressions"] >= 30:
                p_a = a["successes"] / max(1, a["impressions"])
                p_b = b["successes"] / max(1, b["impressions"])
                p_pool = (a["successes"] + b["successes"]) / max(
                    1, a["impressions"] + b["impressions"]
                )
                se = math.sqrt(
                    max(0.0001, p_pool * (1 - p_pool))
                    * (1 / max(1, a["impressions"]) + 1 / max(1, b["impressions"]))
                )
                z = abs(p_a - p_b) / max(0.0001, se)
                significant = z > 1.96  # 95% confidence

        return {
            "test_name": test_name,
            "results": results,
            "winner": results[0]["name"] if significant else None,
            "significant": significant,
            "min_sample_needed": 30 if not significant else 0,
        }

    # ─── Revenue Optimization ───

    def optimize_content_mix(self) -> dict:
        """Analyze and recommend content mix adjustments."""
        content_perf = self.analytics.get_content_type_performance()
        scene_perf = self.analytics.get_scene_performance()

        recommendations = []

        # Check if we have enough data
        total_posts = sum(v.get("count", 0) for v in content_perf.values())
        if total_posts < 10:
            return {
                "recommendations": ["Need at least 10 posts for optimization"],
                "data_sufficient": False,
            }

        # Analyze content type distribution
        for ctype, data in content_perf.items():
            count = data.get("count", 0)
            pct = count / max(1, total_posts) * 100
            if ctype == "thread" and pct < 20:
                recommendations.append(
                    f"Increase threads (currently {pct:.0f}%, target 25%+). "
                    f"Threads get 40-60% more impressions."
                )
            if ctype == "poll" and pct < 10:
                recommendations.append(
                    f"Add more polls (currently {pct:.0f}%). "
                    f"Polls drive highest engagement."
                )

        # Check monetization ratio
        sponsored_pct = (
            content_perf.get("promo", {}).get("count", 0) / max(1, total_posts) * 100
        )
        if sponsored_pct > 10:
            recommendations.append(
                f"Reduce sponsored content ({sponsored_pct:.0f}% > 10% limit). "
                f"Over-monetization hurts trust."
            )
        elif sponsored_pct < 5:
            recommendations.append(
                f"Room for more monetized content ({sponsored_pct:.0f}%). "
                f"Can safely increase to 10%."
            )

        return {
            "recommendations": recommendations,
            "content_distribution": content_perf,
            "scene_distribution": scene_perf,
            "data_sufficient": True,
            "total_posts_analyzed": total_posts,
        }

    def optimize_fanvue_pricing(
        self, subscriber_counts: dict[str, int]
    ) -> dict:
        """Recommend Fanvue pricing adjustments."""
        tiers = self.fanvue.tiers
        recommendations = []

        for tier_name, count in subscriber_counts.items():
            tier = tiers.get(tier_name, {})
            price = tier.get("price", 0)

            if tier_name == "free":
                continue

            # Basic pricing analysis
            if count > 100 and tier_name == "basic":
                recommendations.append({
                    "tier": tier_name,
                    "current_price": price,
                    "suggested_price": round(price * 1.1, 2),
                    "reason": f"Strong demand ({count} subs) supports 10% increase",
                })
            elif count < 10 and price > 20:
                recommendations.append({
                    "tier": tier_name,
                    "current_price": price,
                    "suggested_price": round(price * 0.85, 2),
                    "reason": f"Low adoption ({count} subs) — test lower price",
                })

        # Revenue projection
        current_mrr = sum(
            subscriber_counts.get(t, 0) * tiers.get(t, {}).get("price", 0)
            for t in tiers
        )

        return {
            "current_mrr": round(current_mrr, 2),
            "subscriber_counts": subscriber_counts,
            "recommendations": recommendations,
        }

    # ─── Monthly Report ───

    def generate_monthly_report(self, month: str | None = None) -> dict:
        """Generate comprehensive monthly monetization report."""
        if not month:
            month = datetime.now(JST).strftime("%Y-%m")

        dashboard = self.get_revenue_dashboard(month)
        content_mix = self.optimize_content_mix()
        affiliate_stats = self.affiliate.get_program_stats()
        brand_pipeline = self.brand.get_pipeline_summary()
        outreach_stats = self.brand.get_outreach_stats()

        report = {
            "month": month,
            "revenue": dashboard,
            "content_optimization": content_mix,
            "affiliate_performance": affiliate_stats,
            "brand_pipeline": brand_pipeline,
            "outreach_activity": outreach_stats,
            "generated_at": datetime.now(JST).isoformat(),
        }

        report_file = ANALYTICS_DIR / f"monthly_report_{month}.json"
        self._save_json(report_file, report)
        logger.info("Monthly report generated: %s", month)
        return report

    # ─── Pipeline Runner ───

    def run_monetization_pass(self, content_items: list[dict]) -> list[dict]:
        """Enrich content items with monetization data.

        Takes content from content_generator and adds:
        - Affiliate links where appropriate
        - Monetization scores
        - Fanvue upsell suggestions
        """
        enriched = []
        for item in content_items:
            # Score monetization potential
            score = self.score_monetization_potential(item)
            item["monetization"] = score

            # Try to add affiliate link
            if score["action"] == "affiliate_link":
                item = self.affiliate.enrich_content(item)

            # Add Fanvue upsell suggestion
            if score["action"] == "fanvue_teaser":
                scene = item.get("scene", "")
                tier = self.fanvue.categorize_content("", scene)
                if tier in ("premium", "basic"):
                    item["fanvue_upsell"] = {
                        "suggested_tier": tier,
                        "hint": f"More {scene} content on Fanvue",
                    }

            enriched.append(item)

        # Log monetization pass
        logger.info(
            "Monetization pass: %d items, %d enriched with affiliates, %d with upsells",
            len(enriched),
            sum(1 for i in enriched if "affiliate" in i),
            sum(1 for i in enriched if "fanvue_upsell" in i),
        )

        return enriched

    # ─── Helpers ───

    def _estimate_fanvue_revenue(self, tier_stats: dict) -> float:
        """Estimate monthly Fanvue revenue from tier stats."""
        tiers = self.fanvue.tiers
        revenue = 0.0
        for tier_name, stats in tier_stats.items():
            price = tiers.get(tier_name, {}).get("price", 0)
            posted = stats.get("posted", 0)
            # Rough estimate: posted items represent subscriber engagement
            revenue += posted * price * 0.1  # Conservative estimate
        return revenue

    def _load_kpi_targets(self) -> dict:
        """Load KPI targets from brand partnership strategy."""
        try:
            with open(STRATEGY_PATH, encoding="utf-8") as f:
                strategy = yaml.safe_load(f)
            return strategy.get("kpis", {})
        except Exception:
            return {}

    def _load_json_dict(self, path: Path) -> dict:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_json(self, path: Path, data) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    engine = MonetizationEngine()
    print("Dashboard:", json.dumps(engine.get_revenue_dashboard(), indent=2))
