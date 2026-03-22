"""FOMC statement and Fed official speech scorer for CITS trading system."""

import logging
import os
from typing import Any

import anthropic

logger = logging.getLogger(__name__)

HAWKISH_KEYWORDS: list[str] = [
    "inflation",
    "tightening",
    "restrictive",
    "price stability",
    "further increases",
    "strong labor market",
    "overheating",
    "above target",
    "upside risks to inflation",
    "reduce the size of the balance sheet",
    "rate hike",
    "higher for longer",
    "insufficient progress",
    "elevated inflation",
    "too high",
]

DOVISH_KEYWORDS: list[str] = [
    "accommodative",
    "support growth",
    "downside risks",
    "patient",
    "gradual",
    "below target",
    "labor market softening",
    "data dependent",
    "easing",
    "rate cut",
    "slowing economy",
    "disinflation",
    "progress on inflation",
    "balanced risks",
    "sufficiently restrictive",
]


class FOMCScorer:
    """Analyzes FOMC statements and Fed chair speeches for hawk/dove signals."""

    def __init__(self) -> None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            logger.warning("ANTHROPIC_API_KEY not set; semantic scoring will be unavailable")
        self.client = anthropic.Anthropic(api_key=api_key) if api_key else None
        self.hawkish_keywords = HAWKISH_KEYWORDS
        self.dovish_keywords = DOVISH_KEYWORDS
        logger.info("FOMCScorer initialized")

    def _keyword_score(self, text: str) -> tuple[float, list[str], list[str]]:
        """Return a raw keyword-based score and matched phrases."""
        text_lower = text.lower()
        hawk_matches = [kw for kw in self.hawkish_keywords if kw in text_lower]
        dove_matches = [kw for kw in self.dovish_keywords if kw in text_lower]
        raw = len(hawk_matches) - len(dove_matches)
        return raw, hawk_matches, dove_matches

    def _semantic_score(self, prompt: str) -> dict[str, Any]:
        """Use Claude for nuanced semantic scoring beyond keyword matching."""
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

    def score_statement(self, text: str) -> dict[str, Any]:
        """Score an FOMC statement on the hawk-dove spectrum.

        Returns:
            dict with hawk_dove_score (-10 dovish to +10 hawkish),
            key_phrases, and rate_direction_signal.
        """
        raw, hawk_matches, dove_matches = self._keyword_score(text)
        key_phrases = hawk_matches + dove_matches

        # Clamp keyword score to [-10, 10]
        keyword_score = max(-10, min(10, raw))

        # Attempt semantic refinement
        semantic = self._semantic_score(
            "You are a Federal Reserve policy analyst. "
            "Score the following FOMC statement on a scale from -10 (very dovish) "
            "to +10 (very hawkish). Return ONLY a JSON object with keys: "
            "hawk_dove_score (int), rate_direction_signal (one of 'hike', 'hold', 'cut'), "
            "key_phrases (list of strings).\n\n"
            f"Statement:\n{text}"
        )

        if semantic.get("raw_response"):
            try:
                import json
                parsed = json.loads(semantic["raw_response"])
                return {
                    "hawk_dove_score": int(parsed.get("hawk_dove_score", keyword_score)),
                    "key_phrases": parsed.get("key_phrases", key_phrases),
                    "rate_direction_signal": parsed.get("rate_direction_signal", "hold"),
                }
            except (json.JSONDecodeError, ValueError):
                logger.warning("Could not parse semantic response; falling back to keywords")

        # Derive direction signal from keyword score
        if keyword_score >= 3:
            direction = "hike"
        elif keyword_score <= -3:
            direction = "cut"
        else:
            direction = "hold"

        return {
            "hawk_dove_score": keyword_score,
            "key_phrases": key_phrases,
            "rate_direction_signal": direction,
        }

    def diff_statements(self, current: str, previous: str) -> dict[str, Any]:
        """Compare two FOMC statements and highlight changes.

        Returns:
            dict with change_score and changed_phrases.
        """
        cur_raw, cur_hawk, cur_dove = self._keyword_score(current)
        prev_raw, prev_hawk, prev_dove = self._keyword_score(previous)
        change_score = max(-10, min(10, cur_raw - prev_raw))

        added_hawk = [kw for kw in cur_hawk if kw not in prev_hawk]
        removed_hawk = [kw for kw in prev_hawk if kw not in cur_hawk]
        added_dove = [kw for kw in cur_dove if kw not in prev_dove]
        removed_dove = [kw for kw in prev_dove if kw not in cur_dove]

        # Semantic diff
        semantic = self._semantic_score(
            "You are a Federal Reserve policy analyst. Compare the two FOMC statements "
            "below. Return ONLY a JSON object with keys: change_score (int, -10 to +10 "
            "where positive means more hawkish than before), changed_phrases (list of "
            "strings describing key changes).\n\n"
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
        for kw in added_hawk:
            changed_phrases.append(f"Added hawkish: {kw}")
        for kw in removed_hawk:
            changed_phrases.append(f"Removed hawkish: {kw}")
        for kw in added_dove:
            changed_phrases.append(f"Added dovish: {kw}")
        for kw in removed_dove:
            changed_phrases.append(f"Removed dovish: {kw}")

        return {
            "change_score": change_score,
            "changed_phrases": changed_phrases,
        }

    def score_speech(self, speaker: str, text: str) -> dict[str, Any]:
        """Score an individual Fed official's speech.

        Args:
            speaker: Name of the Fed official (e.g., 'Powell', 'Waller').
            text: Full speech text.

        Returns:
            dict with hawk_dove_score, key_phrases, rate_direction_signal, speaker.
        """
        result = self.score_statement(text)
        result["speaker"] = speaker

        # Attempt richer semantic scoring with speaker context
        semantic = self._semantic_score(
            f"You are a Federal Reserve policy analyst. Score the following speech by "
            f"{speaker} on a scale from -10 (very dovish) to +10 (very hawkish). "
            "Return ONLY a JSON object with keys: hawk_dove_score (int), "
            "rate_direction_signal ('hike', 'hold', 'cut'), key_phrases (list of strings).\n\n"
            f"Speech:\n{text}"
        )

        if semantic.get("raw_response"):
            try:
                import json
                parsed = json.loads(semantic["raw_response"])
                return {
                    "hawk_dove_score": int(parsed.get("hawk_dove_score", result["hawk_dove_score"])),
                    "key_phrases": parsed.get("key_phrases", result["key_phrases"]),
                    "rate_direction_signal": parsed.get("rate_direction_signal", result["rate_direction_signal"]),
                    "speaker": speaker,
                }
            except (json.JSONDecodeError, ValueError):
                logger.warning("Could not parse semantic speech score")

        return result
