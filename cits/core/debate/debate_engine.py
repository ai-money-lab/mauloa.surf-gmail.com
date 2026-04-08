"""Bull vs Bear debate engine for the CITS trading pipeline.

Implements a structured multi-round debate between bullish and bearish
research positions.  Each round is evaluated by Claude Opus acting as
a neutral judge.  The final output summarises the winner, a numeric
conviction score, and the full debate transcript.
"""

from __future__ import annotations

import json
import logging
import os

import anthropic

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_JUDGE_SYSTEM = """\
You are a senior equity research director acting as a neutral judge in a
structured Bull vs Bear investment debate.  Evaluate the arguments presented
in each round on the basis of:
1. Strength of evidence cited
2. Logical coherence
3. Relevance to the investment thesis
4. Identification of risks and catalysts

After evaluating, respond with a JSON object (no markdown fences) containing:
{
  "round_winner": "bull" | "bear" | "tie",
  "round_score": <int from -10 (extremely bearish) to 10 (extremely bullish)>,
  "bull_strengths": ["..."],
  "bear_strengths": ["..."],
  "key_insight": "one sentence summary of the most important takeaway"
}
"""

_BULL_REBUTTAL_SYSTEM = """\
You are a senior bullish equity researcher.  You have been given the bear
case and must provide a rigorous rebuttal defending the bullish thesis.
Be specific, cite data where available, and address each bear point directly.
Respond in plain text (no JSON).
"""

_BEAR_REBUTTAL_SYSTEM = """\
You are a senior bearish equity researcher.  You have been given the bull
case and must provide a rigorous rebuttal defending the bearish thesis.
Be specific, cite data where available, and address each bull point directly.
Respond in plain text (no JSON).
"""


class DebateEngine:
    """Orchestrates a multi-round Bull vs Bear debate judged by Claude.

    Parameters
    ----------
    max_rounds : int
        Number of debate rounds (default 2, empirically optimal for balancing
        depth of argumentation against latency and cost).
    """

    MODEL = "claude-opus-4-6"

    def __init__(self, max_rounds: int = 2):
        self.max_rounds = max_rounds
        self.logger = logging.getLogger("cits.debate.engine")
        self._client = anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY"),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.4,
    ) -> str:
        """Send a single request to Claude and return the text response."""
        self.logger.debug(
            "LLM call model=%s temperature=%.2f prompt_len=%d",
            self.MODEL,
            temperature,
            len(user_prompt),
        )
        message = self._client.messages.create(
            model=self.MODEL,
            max_tokens=4096,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return message.content[0].text

    def _parse_json(self, text: str) -> dict:
        """Parse a JSON object from LLM output, tolerating code fences."""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            first_nl = cleaned.index("\n")
            cleaned = cleaned[first_nl + 1:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:cleaned.rfind("```")]
        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            self.logger.warning("Failed to parse judge JSON; returning raw text")
            return {
                "round_winner": "tie",
                "round_score": 0,
                "bull_strengths": [],
                "bear_strengths": [],
                "key_insight": cleaned[:200],
                "parse_error": True,
            }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_debate(
        self,
        bull_case: dict,
        bear_case: dict,
        analyst_reports: dict,
    ) -> dict:
        """Run a structured Bull vs Bear debate.

        Parameters
        ----------
        bull_case : dict
            The initial bullish research thesis.  Expected keys include
            ``summary``, ``key_points``, ``catalysts``, and ``target_upside``.
        bear_case : dict
            The initial bearish research thesis with similar structure.
        analyst_reports : dict
            Consolidated outputs from the Stage I analyst team
            (fundamental, sentiment, news, technical) used as shared
            evidence base.

        Returns
        -------
        dict
            {
                "winner": "bull" | "bear" | "neutral",
                "final_score": int,          # -10..10
                "debate_transcript": [...],  # list of round dicts
                "key_points_bull": [...],
                "key_points_bear": [...],
                "consensus_view": str,
            }
        """
        self.logger.info(
            "Starting debate: max_rounds=%d", self.max_rounds
        )

        transcript: list[dict] = []
        cumulative_score = 0

        # Serialise analyst context once for use in prompts
        analyst_context = json.dumps(analyst_reports, indent=2, default=str)

        # Current positions start from the initial cases
        current_bull = json.dumps(bull_case, indent=2, default=str)
        current_bear = json.dumps(bear_case, indent=2, default=str)

        all_bull_strengths: list[str] = []
        all_bear_strengths: list[str] = []

        for round_num in range(1, self.max_rounds + 1):
            self.logger.info("Debate round %d/%d", round_num, self.max_rounds)

            # --- Bull rebuts Bear's latest points ---
            bull_rebuttal_prompt = (
                f"=== ANALYST REPORTS ===\n{analyst_context}\n\n"
                f"=== BEAR CASE TO REBUT ===\n{current_bear}\n\n"
                f"=== YOUR PREVIOUS BULL CASE ===\n{current_bull}\n\n"
                "Provide your rebuttal and updated bullish thesis."
            )
            bull_rebuttal = self._call_llm(
                _BULL_REBUTTAL_SYSTEM, bull_rebuttal_prompt
            )
            self.logger.debug("Bull rebuttal length=%d", len(bull_rebuttal))

            # --- Bear rebuts Bull's latest points ---
            bear_rebuttal_prompt = (
                f"=== ANALYST REPORTS ===\n{analyst_context}\n\n"
                f"=== BULL CASE TO REBUT ===\n{bull_rebuttal}\n\n"
                f"=== YOUR PREVIOUS BEAR CASE ===\n{current_bear}\n\n"
                "Provide your rebuttal and updated bearish thesis."
            )
            bear_rebuttal = self._call_llm(
                _BEAR_REBUTTAL_SYSTEM, bear_rebuttal_prompt
            )
            self.logger.debug("Bear rebuttal length=%d", len(bear_rebuttal))

            # --- Judge evaluates this round ---
            judge_prompt = (
                f"=== DEBATE ROUND {round_num} ===\n\n"
                f"--- BULL ARGUMENT ---\n{bull_rebuttal}\n\n"
                f"--- BEAR ARGUMENT ---\n{bear_rebuttal}\n\n"
                "Evaluate this round and respond with JSON."
            )
            judge_raw = self._call_llm(_JUDGE_SYSTEM, judge_prompt, temperature=0.2)
            judge_result = self._parse_json(judge_raw)

            round_score = judge_result.get("round_score", 0)
            cumulative_score += round_score

            round_record = {
                "round": round_num,
                "bull_argument": bull_rebuttal,
                "bear_argument": bear_rebuttal,
                "judge_result": judge_result,
                "round_score": round_score,
                "cumulative_score": cumulative_score,
            }
            transcript.append(round_record)

            all_bull_strengths.extend(judge_result.get("bull_strengths", []))
            all_bear_strengths.extend(judge_result.get("bear_strengths", []))

            self.logger.info(
                "Round %d result: winner=%s score=%d cumulative=%d",
                round_num,
                judge_result.get("round_winner", "unknown"),
                round_score,
                cumulative_score,
            )

            # Update positions for next round
            current_bull = bull_rebuttal
            current_bear = bear_rebuttal

        # --- Determine overall winner ---
        avg_score = cumulative_score / self.max_rounds if self.max_rounds else 0
        if avg_score > 2:
            winner = "bull"
        elif avg_score < -2:
            winner = "bear"
        else:
            winner = "neutral"

        # Clamp final score to [-10, 10]
        final_score = max(-10, min(10, cumulative_score))

        # Build consensus view
        consensus = (
            f"After {self.max_rounds} rounds of debate the "
            f"{'bullish' if winner == 'bull' else 'bearish' if winner == 'bear' else 'neutral'} "
            f"side prevailed with a conviction score of {final_score}/10. "
            f"Key bull points: {'; '.join(all_bull_strengths[:3]) or 'N/A'}. "
            f"Key bear points: {'; '.join(all_bear_strengths[:3]) or 'N/A'}."
        )

        result = {
            "winner": winner,
            "final_score": final_score,
            "debate_transcript": transcript,
            "key_points_bull": all_bull_strengths,
            "key_points_bear": all_bear_strengths,
            "consensus_view": consensus,
        }

        self.logger.info(
            "Debate complete: winner=%s final_score=%d", winner, final_score
        )
        self.logger.debug("Full debate result: %s", json.dumps(result, default=str))

        return result
