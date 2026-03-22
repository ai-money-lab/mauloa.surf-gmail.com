"""Fundamental analysis agent for CITS trading pipeline."""

import logging

from cits.core.agents.base_agent import BaseAgent


logger = logging.getLogger(__name__)


class FundamentalAnalyst(BaseAgent):
    """Analyses earnings, financial statements, and insider trading activity.

    Produces a fundamental score from -10 (deeply overvalued / deteriorating)
    to +10 (deeply undervalued / improving) together with supporting reasoning
    and the key metrics that drove the score.
    """

    SYSTEM_PROMPT = (
        "You are a senior fundamental analyst in a systematic trading fund.\n"
        "Your role is to evaluate a company's financial health, earnings quality, "
        "and insider activity to determine whether the stock is fundamentally "
        "attractive or unattractive.\n\n"
        "## Reasoning Framework (ReAct)\n"
        "1. **Observation**: Summarise the key financial data provided.\n"
        "2. **Thought**: Reason about what the numbers imply for future "
        "earnings power, balance-sheet strength, and management alignment.\n"
        "3. **Action**: Produce your final assessment.\n\n"
        "## Japanese Market Awareness\n"
        "- Consider Japanese accounting standards (J-GAAP / IFRS adoption).\n"
        "- Note cross-shareholding structures common in keiretsu groups.\n"
        "- Factor in shareholder return policies (自社株買い, 増配) that are "
        "increasingly important in TSE reforms.\n"
        "- Be aware of fiscal year-end patterns (March) and 決算 season timing.\n\n"
        "## Output\n"
        "Return ONLY a JSON object with these fields:\n"
        '  "score": integer from -10 to 10,\n'
        '  "reasoning": string explaining your analysis step by step,\n'
        '  "key_metrics": object with the most important metrics and their values\n'
    )

    def __init__(self, llm_type: str = "quick_think"):
        super().__init__(
            name="fundamental_analyst",
            role="Fundamental Analyst",
            llm_type=llm_type,
        )

    def analyze(self, context: dict) -> dict:
        """Analyse fundamental data for a given ticker.

        Args:
            context: Must contain ``ticker``. May contain ``financials``,
                     ``earnings``, ``insider_trades``, and ``market_data``.

        Returns:
            dict with ``score``, ``reasoning``, and ``key_metrics``.
        """
        ticker = context.get("ticker", "UNKNOWN")
        self.logger.info("Running fundamental analysis for %s", ticker)

        user_prompt_parts = [f"Analyse the fundamentals of {ticker}.\n"]

        if context.get("financials"):
            user_prompt_parts.append(
                f"Financial statements:\n{context['financials']}\n"
            )

        if context.get("earnings"):
            user_prompt_parts.append(
                f"Recent earnings data:\n{context['earnings']}\n"
            )

        if context.get("insider_trades"):
            user_prompt_parts.append(
                f"Insider trading activity:\n{context['insider_trades']}\n"
            )

        if context.get("market_data"):
            user_prompt_parts.append(
                f"Current market data:\n{context['market_data']}\n"
            )

        user_prompt = "\n".join(user_prompt_parts)
        response = self._call_llm(self.SYSTEM_PROMPT, user_prompt)
        result = self._parse_json_response(response)

        self.logger.info(
            "Fundamental analysis complete for %s: score=%s",
            ticker,
            result.get("score"),
        )
        return result
