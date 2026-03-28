"""Bank of Japan MPM decision and Governor speech scorer for CITS trading system."""

from __future__ import annotations

import logging
import os
from typing import Any

import anthropic

logger = logging.getLogger(__name__)

# Tightening keywords (Japanese and English)
TIGHTENING_KEYWORDS: list[str] = [
    "物価安定",      # price stability
    "正常化",        # normalization
    "利上げ",        # rate hike
    "YCC修正",       # YCC adjustment
    "出口戦略",      # exit strategy
    "物価上昇",      # price increase
    "賃金上昇",      # wage increase
    "引き締め",      # tightening
    "政策修正",      # policy revision
    "金利引き上げ",  # interest rate increase
    "normalization",
    "rate hike",
    "tightening",
    "price stability",
    "exit strategy",
    "ycc adjustment",
    "wage growth",
    "sustainable inflation",
]

# Easing keywords (Japanese and English)
EASING_KEYWORDS: list[str] = [
    "緩和継続",          # continued easing
    "粘り強く",          # patiently / persistently
    "下振れリスク",      # downside risks
    "マイナス金利維持",  # maintaining negative rates
    "金融緩和",          # monetary easing
    "必要に応じて追加",  # additional measures as needed
    "経済の下支え",      # supporting the economy
    "物価目標未達",      # inflation target not achieved
    "慎重に",            # cautiously
    "時期尚早",          # premature
    "continued easing",
    "patiently",
    "downside risks",
    "negative interest rate",
    "monetary accommodation",
    "supporting growth",
    "premature",
    "cautiously",
]


class BOJScorer:
    """Analyzes Bank of Japan MPM decisions and Governor Ueda statements."""

    def __init__(self) -> None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            logger.warning("ANTHROPIC_API_KEY not set; semantic scoring will be unavailable")
        self.client = anthropic.Anthropic(api_key=api_key) if api_key else None
        self.tightening_keywords = TIGHTENING_KEYWORDS
        self.easing_keywords = EASING_KEYWORDS
        logger.info("BOJScorer initialized")

    def _keyword_score(self, text: str) -> tuple[float, list[str], list[str]]:
        """Return a raw keyword-based score and matched phrases."""
        text_lower = text.lower()
        tight_matches = [kw for kw in self.tightening_keywords if kw.lower() in text_lower or kw in text]
        ease_matches = [kw for kw in self.easing_keywords if kw.lower() in text_lower or kw in text]
        raw = len(tight_matches) - len(ease_matches)
        return raw, tight_matches, ease_matches

    def _semantic_score(self, prompt: str) -> dict[str, Any]:
        """Use Claude for nuanced semantic scoring with Japanese language understanding."""
        if self.client is None:
            logger.warning("No Anthropic client; skipping semantic scoring")
            return {}
        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            return {"raw_response": message.content[0].text}
        except Exception:
            logger.exception("Semantic scoring failed")
            return {}

    def score_mpm_decision(self, text: str) -> dict[str, Any]:
        """Score a Bank of Japan Monetary Policy Meeting decision.

        Returns:
            dict with policy_score (-10 easing to +10 tightening),
            ycc_status, rate_decision, forward_guidance.
        """
        raw, tight_matches, ease_matches = self._keyword_score(text)
        keyword_score = max(-10, min(10, raw))

        semantic = self._semantic_score(
            "You are a Bank of Japan monetary policy analyst fluent in Japanese. "
            "Score the following MPM decision on a scale from -10 (very dovish / easing) "
            "to +10 (very hawkish / tightening). Return ONLY a JSON object with keys: "
            "policy_score (int), ycc_status (string describing YCC stance), "
            "rate_decision (one of 'hike', 'hold', 'cut'), "
            "forward_guidance (string summary of forward guidance).\n\n"
            f"MPM Decision:\n{text}"
        )

        if semantic.get("raw_response"):
            try:
                import json
                parsed = json.loads(semantic["raw_response"])
                return {
                    "policy_score": int(parsed.get("policy_score", keyword_score)),
                    "ycc_status": parsed.get("ycc_status", "unknown"),
                    "rate_decision": parsed.get("rate_decision", "hold"),
                    "forward_guidance": parsed.get("forward_guidance", ""),
                }
            except (json.JSONDecodeError, ValueError):
                logger.warning("Could not parse semantic response; falling back to keywords")

        # Heuristic YCC / rate detection from keywords
        text_lower = text.lower()
        if "ycc修正" in text or "ycc adjustment" in text_lower:
            ycc_status = "modified"
        elif "ycc撤廃" in text or "ycc removal" in text_lower:
            ycc_status = "removed"
        else:
            ycc_status = "unchanged"

        if keyword_score >= 3:
            rate_decision = "hike"
        elif keyword_score <= -3:
            rate_decision = "cut"
        else:
            rate_decision = "hold"

        return {
            "policy_score": keyword_score,
            "ycc_status": ycc_status,
            "rate_decision": rate_decision,
            "forward_guidance": ", ".join(tight_matches + ease_matches) if tight_matches or ease_matches else "neutral",
        }

    def diff_mpm_statements(self, current: str, previous: str) -> dict[str, Any]:
        """Compare two MPM statements and highlight changes.

        Returns:
            dict with change_score and changed_phrases.
        """
        cur_raw, cur_tight, cur_ease = self._keyword_score(current)
        prev_raw, prev_tight, prev_ease = self._keyword_score(previous)
        change_score = max(-10, min(10, cur_raw - prev_raw))

        added_tight = [kw for kw in cur_tight if kw not in prev_tight]
        removed_tight = [kw for kw in prev_tight if kw not in cur_tight]
        added_ease = [kw for kw in cur_ease if kw not in prev_ease]
        removed_ease = [kw for kw in prev_ease if kw not in cur_ease]

        semantic = self._semantic_score(
            "You are a Bank of Japan monetary policy analyst fluent in Japanese. "
            "Compare the two MPM statements below. Return ONLY a JSON object with keys: "
            "change_score (int, -10 to +10 where positive means more hawkish/tightening), "
            "changed_phrases (list of strings describing key changes).\n\n"
            f"Previous statement:\n{previous}\n\nCurrent statement:\n{current}"
        )

        if semantic.get("raw_response"):
            try:
                import json
                parsed = json.loads(semantic["raw_response"])
                return {
                    "change_score": int(parsed.get("change_score", change_score)),
                    "changed_phrases": parsed.get("changed_phrases", []),
                }
            except (json.JSONDecodeError, ValueError):
                logger.warning("Could not parse semantic diff; falling back to keywords")

        changed_phrases: list[str] = []
        for kw in added_tight:
            changed_phrases.append(f"Added tightening: {kw}")
        for kw in removed_tight:
            changed_phrases.append(f"Removed tightening: {kw}")
        for kw in added_ease:
            changed_phrases.append(f"Added easing: {kw}")
        for kw in removed_ease:
            changed_phrases.append(f"Removed easing: {kw}")

        return {
            "change_score": change_score,
            "changed_phrases": changed_phrases,
        }

    def score_governor_speech(self, text: str) -> dict[str, Any]:
        """Score a Governor Ueda speech.

        Returns:
            dict with policy_score, ycc_status, rate_decision, forward_guidance.
        """
        semantic = self._semantic_score(
            "You are a Bank of Japan monetary policy analyst fluent in Japanese. "
            "Score the following speech by BOJ Governor Ueda on a scale from "
            "-10 (very dovish / easing) to +10 (very hawkish / tightening). "
            "Return ONLY a JSON object with keys: policy_score (int), "
            "ycc_status (string), rate_decision ('hike', 'hold', 'cut'), "
            "forward_guidance (string), key_phrases (list of strings).\n\n"
            f"Speech:\n{text}"
        )

        if semantic.get("raw_response"):
            try:
                import json
                parsed = json.loads(semantic["raw_response"])
                return {
                    "policy_score": int(parsed.get("policy_score", 0)),
                    "ycc_status": parsed.get("ycc_status", "unknown"),
                    "rate_decision": parsed.get("rate_decision", "hold"),
                    "forward_guidance": parsed.get("forward_guidance", ""),
                    "key_phrases": parsed.get("key_phrases", []),
                }
            except (json.JSONDecodeError, ValueError):
                logger.warning("Could not parse semantic governor speech score")

        # Fall back to keyword scoring
        result = self.score_mpm_decision(text)
        result["key_phrases"] = []
        return result
