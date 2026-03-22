"""Bear researcher agent for CITS trading pipeline."""

import json
import logging

from cits.core.agents.base_agent import BaseAgent


logger = logging.getLogger(__name__)


class BearResearcher(BaseAgent):
    """Builds the strongest possible bearish case from analyst reports.

    Acts as an advocate for the short side in the bull-bear debate,
    synthesising evidence from fundamental, sentiment, news, and technical
    analysts into a compelling bearish thesis.
    """

    SYSTEM_PROMPT = (
        "You are a senior bear-side researcher in a systematic trading fund.\n"
        "Your job is to construct the strongest possible BEARISH case for a "
        "trade based on the analyst reports you receive. You are an advocate "
        "for going short or staying out.\n\n"
        "## Reasoning Framework (ReAct)\n"
        "1. **Observation**: Review all analyst reports and identify every "
        "piece of evidence that supports a bearish thesis or raises red flags.\n"
        "2. **Thought**: Synthesise the evidence into a coherent narrative. "
        "Identify downside risks, deteriorating fundamentals, and crowded "
        "positioning. Address potential bull arguments critically.\n"
        "3. **Action**: Present your bearish case with conviction and "
        "supporting evidence.\n\n"
        "## Japanese Market Awareness\n"
        "- Consider BOJ policy normalisation risks (利上げ) and impact on "
        "growth stocks.\n"
        "- Note yen-strengthening risk for exporters.\n"
        "- Factor in demographic headwinds and deflationary pressures.\n"
        "- Watch for 信用買い残 (margin longs) build-up indicating crowded trades.\n"
        "- Flag governance concerns, 持ち合い (cross-shareholding) issues, and "
        "poor capital allocation history.\n\n"
        "## Output\n"
        "Return ONLY a JSON object with these fields:\n"
        '  "bear_case": string with your full bearish thesis,\n'
        '  "confidence": float from 0.0 to 1.0,\n'
        '  "key_arguments": list of strings, each a distinct bearish argument\n'
    )

    def __init__(self, llm_type: str = "quick_think"):
        super().__init__(
            name="bear_researcher",
            role="Bear Researcher",
            llm_type=llm_type,
        )

    def analyze(self, context: dict) -> dict:
        """Convenience wrapper that delegates to ``research``."""
        return self.research(context)

    def research(self, analyst_reports: dict) -> dict:
        """Build a bearish case from upstream analyst reports.

        Args:
            analyst_reports: Dictionary containing outputs from the
                fundamental, sentiment, news, and technical analysts.

        Returns:
            dict with ``bear_case``, ``confidence``, and ``key_arguments``.
        """
        self.logger.info("Building bearish case from analyst reports")

        user_prompt = (
            "Based on the following analyst reports, build the strongest "
            "possible bearish case against this trade.\n\n"
            f"Analyst reports:\n{json.dumps(analyst_reports, indent=2, default=str)}\n"
        )

        response = self._call_llm(self.SYSTEM_PROMPT, user_prompt)
        result = self._parse_json_response(response)

        self.logger.info(
            "Bear research complete: confidence=%s, arguments=%d",
            result.get("confidence"),
            len(result.get("key_arguments", [])),
        )
        return result
