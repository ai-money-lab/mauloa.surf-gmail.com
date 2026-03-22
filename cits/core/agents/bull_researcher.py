"""Bull researcher agent for CITS trading pipeline."""

import json
import logging

from cits.core.agents.base_agent import BaseAgent


logger = logging.getLogger(__name__)


class BullResearcher(BaseAgent):
    """Builds the strongest possible bullish case from analyst reports.

    Acts as an advocate for the long side in the bull-bear debate,
    synthesising evidence from fundamental, sentiment, news, and technical
    analysts into a compelling bullish thesis.
    """

    SYSTEM_PROMPT = (
        "You are a senior bull-side researcher in a systematic trading fund.\n"
        "Your job is to construct the strongest possible BULLISH case for a "
        "trade based on the analyst reports you receive. You are an advocate "
        "for going long.\n\n"
        "## Reasoning Framework (ReAct)\n"
        "1. **Observation**: Review all analyst reports and identify every "
        "piece of evidence that supports a bullish thesis.\n"
        "2. **Thought**: Synthesise the evidence into a coherent narrative. "
        "Identify catalysts, upside scenarios, and asymmetric opportunities. "
        "Address potential bear arguments pre-emptively.\n"
        "3. **Action**: Present your bullish case with conviction and "
        "supporting evidence.\n\n"
        "## Japanese Market Awareness\n"
        "- Consider TSE corporate governance reforms driving shareholder returns.\n"
        "- Note the weak-yen tailwind for exporters (輸出関連銘柄).\n"
        "- Factor in foreign investor flows into Japanese equities.\n"
        "- Consider 新NISA driven retail inflows.\n"
        "- Highlight any 自社株買い (buyback) or 増配 (dividend increase) announcements.\n\n"
        "## Output\n"
        "Return ONLY a JSON object with these fields:\n"
        '  "bull_case": string with your full bullish thesis,\n'
        '  "confidence": float from 0.0 to 1.0,\n'
        '  "key_arguments": list of strings, each a distinct bullish argument\n'
    )

    def __init__(self, llm_type: str = "quick_think"):
        super().__init__(
            name="bull_researcher",
            role="Bull Researcher",
            llm_type=llm_type,
        )

    def analyze(self, context: dict) -> dict:
        """Convenience wrapper that delegates to ``research``."""
        return self.research(context)

    def research(self, analyst_reports: dict) -> dict:
        """Build a bullish case from upstream analyst reports.

        Args:
            analyst_reports: Dictionary containing outputs from the
                fundamental, sentiment, news, and technical analysts.

        Returns:
            dict with ``bull_case``, ``confidence``, and ``key_arguments``.
        """
        self.logger.info("Building bullish case from analyst reports")

        user_prompt = (
            "Based on the following analyst reports, build the strongest "
            "possible bullish case for this trade.\n\n"
            f"Analyst reports:\n{json.dumps(analyst_reports, indent=2, default=str)}\n"
        )

        response = self._call_llm(self.SYSTEM_PROMPT, user_prompt)
        result = self._parse_json_response(response)

        self.logger.info(
            "Bull research complete: confidence=%s, arguments=%d",
            result.get("confidence"),
            len(result.get("key_arguments", [])),
        )
        return result
