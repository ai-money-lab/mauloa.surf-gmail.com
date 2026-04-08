"""Trump statement tracker for market-relevant policy signals in CITS trading system."""

from __future__ import annotations

import logging
import os
from typing import Any

import anthropic

logger = logging.getLogger(__name__)

TARIFF_KEYWORDS: list[str] = [
    "tariff",
    "trade war",
    "import duty",
    "reciprocal",
    "customs duty",
    "anti-dumping",
    "countervailing",
    "section 301",
    "section 232",
    "border tax",
    "trade deficit",
    "unfair trade",
]

TRADE_KEYWORDS: list[str] = [
    "trade deal",
    "agreement",
    "negotiation",
    "trade agreement",
    "bilateral deal",
    "phase one",
    "phase two",
    "trade talks",
    "trade representative",
    "commerce secretary",
]

FED_KEYWORDS: list[str] = [
    "interest rates",
    "federal reserve",
    "powell",
    "the fed",
    "rate cuts",
    "rate hikes",
    "monetary policy",
    "strong dollar",
    "weak dollar",
    "quantitative easing",
]

FISCAL_KEYWORDS: list[str] = [
    "tax cuts",
    "spending",
    "infrastructure",
    "tax reform",
    "budget",
    "deficit",
    "stimulus",
    "deregulation",
    "government shutdown",
    "debt ceiling",
]

CATEGORY_MAP: dict[str, list[str]] = {
    "tariff": TARIFF_KEYWORDS,
    "trade": TRADE_KEYWORDS,
    "fed": FED_KEYWORDS,
    "fiscal": FISCAL_KEYWORDS,
}


class TrumpTracker:
    """Tracks Trump statements that impact markets (tariffs, trade policy, Fed criticism)."""

    def __init__(self) -> None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            logger.warning("ANTHROPIC_API_KEY not set; semantic analysis will be unavailable")
        self.client = anthropic.Anthropic(api_key=api_key) if api_key else None
        self.category_map = CATEGORY_MAP
        logger.info("TrumpTracker initialized")

    def _detect_categories(self, text: str) -> dict[str, list[str]]:
        """Detect which keyword categories are present in the text."""
        text_lower = text.lower()
        matched: dict[str, list[str]] = {}
        for category, keywords in self.category_map.items():
            hits = [kw for kw in keywords if kw in text_lower]
            if hits:
                matched[category] = hits
        return matched

    def _semantic_analysis(self, prompt: str) -> dict[str, Any]:
        """Use Claude for intent analysis and bluff detection."""
        if self.client is None:
            logger.warning("No Anthropic client; skipping semantic analysis")
            return {}
        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            return {"raw_response": message.content[0].text}
        except Exception:
            logger.exception("Semantic analysis failed")
            return {}

    def score_statement(self, text: str) -> dict[str, Any]:
        """Score a Trump statement for market impact.

        Returns:
            dict with market_impact_score (-10 negative to +10 positive),
            categories, affected_sectors, urgency_level.
        """
        matched_categories = self._detect_categories(text)
        category_names = list(matched_categories.keys())

        # Heuristic: more tariff/trade-war keywords -> more negative
        tariff_count = len(matched_categories.get("tariff", []))
        trade_count = len(matched_categories.get("trade", []))
        fiscal_count = len(matched_categories.get("fiscal", []))

        # Rough heuristic score: trade deals / fiscal positive, tariffs negative
        keyword_score = (trade_count + fiscal_count) - tariff_count
        keyword_score = max(-10, min(10, keyword_score))

        # Urgency based on number of categories triggered
        if len(category_names) >= 3:
            urgency = "high"
        elif len(category_names) >= 2:
            urgency = "medium"
        else:
            urgency = "low"

        semantic = self._semantic_analysis(
            "You are a markets analyst specializing in political risk. "
            "Score the following Trump statement for overall market impact on a scale "
            "from -10 (very negative for markets) to +10 (very positive). "
            "Return ONLY a JSON object with keys: market_impact_score (int), "
            "categories (list of strings from: tariff, trade, fed, fiscal), "
            "affected_sectors (list of strings), urgency_level (low/medium/high).\n\n"
            f"Statement:\n{text}"
        )

        if semantic.get("raw_response"):
            try:
                import json
                parsed = json.loads(semantic["raw_response"])
                return {
                    "market_impact_score": int(parsed.get("market_impact_score", keyword_score)),
                    "categories": parsed.get("categories", category_names),
                    "affected_sectors": parsed.get("affected_sectors", []),
                    "urgency_level": parsed.get("urgency_level", urgency),
                }
            except (json.JSONDecodeError, ValueError):
                logger.warning("Could not parse semantic response; falling back to keywords")

        return {
            "market_impact_score": keyword_score,
            "categories": category_names,
            "affected_sectors": [],
            "urgency_level": urgency,
        }

    def detect_tariff_threat(self, text: str) -> dict[str, Any]:
        """Detect tariff-related statements and assess severity.

        Returns:
            dict with target_countries, affected_industries, severity.
        """
        text_lower = text.lower()
        tariff_hits = [kw for kw in TARIFF_KEYWORDS if kw in text_lower]

        if not tariff_hits:
            return {
                "target_countries": [],
                "affected_industries": [],
                "severity": "none",
            }

        # Known country patterns
        country_keywords: dict[str, list[str]] = {
            "China": ["china", "chinese", "beijing"],
            "Japan": ["japan", "japanese", "tokyo"],
            "EU": ["europe", "european union", "eu", "brussels"],
            "Mexico": ["mexico", "mexican"],
            "Canada": ["canada", "canadian"],
            "South Korea": ["korea", "korean", "seoul"],
            "Taiwan": ["taiwan", "taiwanese"],
        }

        target_countries = [
            country
            for country, patterns in country_keywords.items()
            if any(p in text_lower for p in patterns)
        ]

        semantic = self._semantic_analysis(
            "You are a trade policy analyst. Analyze the following statement for tariff "
            "threats. Return ONLY a JSON object with keys: target_countries (list of "
            "country names), affected_industries (list of strings), "
            "severity (one of 'none', 'low', 'medium', 'high', 'critical').\n\n"
            f"Statement:\n{text}"
        )

        if semantic.get("raw_response"):
            try:
                import json
                parsed = json.loads(semantic["raw_response"])
                return {
                    "target_countries": parsed.get("target_countries", target_countries),
                    "affected_industries": parsed.get("affected_industries", []),
                    "severity": parsed.get("severity", "medium"),
                }
            except (json.JSONDecodeError, ValueError):
                logger.warning("Could not parse semantic tariff analysis")

        # Heuristic severity
        if len(tariff_hits) >= 4:
            severity = "critical"
        elif len(tariff_hits) >= 3:
            severity = "high"
        elif len(tariff_hits) >= 2:
            severity = "medium"
        else:
            severity = "low"

        return {
            "target_countries": target_countries,
            "affected_industries": [],
            "severity": severity,
        }

    def get_pattern_analysis(self, text: str) -> dict[str, Any]:
        """Analyze whether the statement matches known Trump communication patterns.

        Returns:
            dict with pattern (escalation, negotiation, bluff),
            confidence, and reasoning.
        """
        semantic = self._semantic_analysis(
            "You are a political communications analyst specializing in Trump rhetoric. "
            "Analyze the following statement and classify it into one of these patterns: "
            "'escalation' (genuine threat/action), 'negotiation' (opening position in a deal), "
            "'bluff' (rhetoric unlikely to materialize). "
            "Return ONLY a JSON object with keys: pattern (string), confidence (float 0-1), "
            "reasoning (string).\n\n"
            f"Statement:\n{text}"
        )

        if semantic.get("raw_response"):
            try:
                import json
                parsed = json.loads(semantic["raw_response"])
                return {
                    "pattern": parsed.get("pattern", "unknown"),
                    "confidence": float(parsed.get("confidence", 0.5)),
                    "reasoning": parsed.get("reasoning", ""),
                }
            except (json.JSONDecodeError, ValueError):
                logger.warning("Could not parse semantic pattern analysis")

        # Without semantic analysis, we can only return a low-confidence guess
        text_lower = text.lower()
        if any(w in text_lower for w in ["will impose", "effective immediately", "signed an order"]):
            pattern = "escalation"
        elif any(w in text_lower for w in ["deal", "negotiat", "talks", "agreement"]):
            pattern = "negotiation"
        else:
            pattern = "bluff"

        return {
            "pattern": pattern,
            "confidence": 0.3,
            "reasoning": "Keyword-only heuristic; semantic analysis unavailable",
        }
