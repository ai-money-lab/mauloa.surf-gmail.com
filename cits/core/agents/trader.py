"""Trader agent for CITS trading pipeline."""

import json
import logging

from cits.core.agents.base_agent import BaseAgent


logger = logging.getLogger(__name__)


class Trader(BaseAgent):
    """Makes buy/sell/hold decisions based on the bull-bear debate.

    Uses the deep_think (Opus) model for careful deliberation over the
    competing arguments, market conditions, and risk/reward profile.
    """

    SYSTEM_PROMPT = (
        "You are the head trader at a systematic trading fund.\n"
        "You have heard the bull and bear cases debated by your research team. "
        "Your job is to make the final trading decision: BUY, SELL, or HOLD.\n\n"
        "## Reasoning Framework (ReAct)\n"
        "1. **Observation**: Review the bull case, bear case, and current "
        "market data.\n"
        "2. **Thought**: Weigh the strength of each side's arguments. Consider "
        "the risk/reward ratio, conviction level, and market timing. Factor "
        "in liquidity, slippage, and execution feasibility.\n"
        "3. **Action**: Make your trading decision with a clear rationale.\n\n"
        "## Position Sizing\n"
        "- Express size as a percentage of portfolio (0.0 to 1.0).\n"
        "- Scale size with conviction: low conviction = small size.\n"
        "- Consider correlation with existing positions.\n"
        "- Account for asset liquidity and average daily volume.\n\n"
        "## Japanese Market Awareness\n"
        "- Consider 取引時間 (trading hours: 9:00-11:30, 12:30-15:30 JST).\n"
        "- Factor in lot sizes (売買単位, typically 100 shares).\n"
        "- Note 値幅制限 (price limits) that may affect execution.\n"
        "- Consider T+2 settlement cycle.\n"
        "- Watch for 大引け (closing auction) and 寄り付き (opening auction) "
        "effects.\n\n"
        "## Output\n"
        "Return ONLY a JSON object with these fields:\n"
        '  "action": one of "buy", "sell", "hold",\n'
        '  "size": float from 0.0 to 1.0 (percentage of portfolio),\n'
        '  "reasoning": string explaining your decision step by step,\n'
        '  "confidence": float from 0.0 to 1.0\n'
    )

    def __init__(self):
        super().__init__(
            name="trader",
            role="Trader",
            llm_type="deep_think",
        )

    def analyze(self, context: dict) -> dict:
        """Convenience wrapper that delegates to ``decide``."""
        return self.decide(
            debate_result=context.get("debate_result", {}),
            market_data=context.get("market_data", {}),
        )

    def decide(self, debate_result: dict, market_data: dict) -> dict:
        """Decide on a trade action given the debate outcome and market data.

        Args:
            debate_result: Contains ``bull_case`` and ``bear_case`` from the
                researcher agents.
            market_data: Current price, volume, and other live market data.

        Returns:
            dict with ``action``, ``size``, ``reasoning``, and ``confidence``.
        """
        self.logger.info("Making trading decision")

        user_prompt = (
            "Based on the following debate results and market data, make "
            "your trading decision.\n\n"
            f"Debate result:\n{json.dumps(debate_result, indent=2, default=str)}\n\n"
            f"Current market data:\n{json.dumps(market_data, indent=2, default=str)}\n"
        )

        response = self._call_llm(self.SYSTEM_PROMPT, user_prompt)
        result = self._parse_json_response(response)

        self.logger.info(
            "Trading decision: action=%s size=%s confidence=%s",
            result.get("action"),
            result.get("size"),
            result.get("confidence"),
        )
        return result
