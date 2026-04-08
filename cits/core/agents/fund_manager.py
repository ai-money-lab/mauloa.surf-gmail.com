"""Fund manager agent for CITS trading pipeline."""

import json
import logging

from cits.core.agents.base_agent import BaseAgent


logger = logging.getLogger(__name__)


class FundManager(BaseAgent):
    """Final approval and execution authority for the trading pipeline.

    Uses the deep_think (Opus) model for the most consequential decision
    in the pipeline.  Reviews the trader's proposal alongside the risk
    manager's assessment to make the ultimate go/no-go call.
    """

    SYSTEM_PROMPT = (
        "You are the fund manager with final execution authority.\n"
        "You review every trade proposal that has passed through the analyst "
        "team, debate, trader, and risk management stages. Your approval is "
        "the last gate before execution.\n\n"
        "## Reasoning Framework (ReAct)\n"
        "1. **Observation**: Review the trade proposal and risk assessment.\n"
        "2. **Thought**: Consider the holistic picture:\n"
        "   - Does this trade align with the fund's strategy and mandate?\n"
        "   - Is the risk/reward compelling after risk adjustments?\n"
        "   - Is the timing appropriate given the market regime?\n"
        "   - Are there any portfolio-level considerations the risk manager "
        "     may have missed?\n"
        "   - What is the opportunity cost of this capital allocation?\n"
        "3. **Action**: Give final approval or rejection with clear reasoning.\n\n"
        "## Fund Mandate\n"
        "- Target annual return: 15-25% with Sharpe > 1.5\n"
        "- Maximum drawdown tolerance: 15%\n"
        "- Focus on Japanese and US equity markets\n"
        "- Blend of systematic signals and discretionary overlays\n"
        "- Capital preservation is the primary objective during high-volatility "
        "regimes\n\n"
        "## Japanese Market Awareness\n"
        "- Consider 決算シーズン (earnings season) timing for JP equities.\n"
        "- Factor in 為替ヘッジ (FX hedge) costs and strategy.\n"
        "- Note Japan-specific corporate actions: TOB (株式公開買付), MBO, "
        "株式分割, 株式併合.\n"
        "- Consider the impact of 海外投資家 (foreign investor) flow patterns.\n"
        "- Watch for 政策保有株式 (policy shareholding) unwind trends as a "
        "structural catalyst.\n\n"
        "## Output\n"
        "Return ONLY a JSON object with these fields:\n"
        '  "approved": boolean,\n'
        '  "final_action": one of "buy", "sell", "hold",\n'
        '  "final_size": float from 0.0 to 1.0 (final position size),\n'
        '  "reasoning": string explaining your final decision\n'
    )

    def __init__(self):
        super().__init__(
            name="fund_manager",
            role="Fund Manager",
            llm_type="deep_think",
        )

    def analyze(self, context: dict) -> dict:
        """Convenience wrapper that delegates to ``approve``."""
        return self.approve(
            trade_proposal=context.get("trade_decision", {}),
            risk_assessment=context.get("risk_assessment", {}),
        )

    def approve(self, trade_proposal: dict, risk_assessment: dict) -> dict:
        """Make the final approval decision on a trade.

        Args:
            trade_proposal: The trade from the Trader agent, including action,
                size, reasoning, and confidence.
            risk_assessment: The RiskManager's evaluation including approved
                status, risk_score, warnings, and adjusted_size.

        Returns:
            dict with ``approved``, ``final_action``, ``final_size``, and
            ``reasoning``.
        """
        self.logger.info("Fund manager reviewing trade proposal")

        user_prompt = (
            "Review the following trade proposal and risk assessment. "
            "Make your final decision.\n\n"
            f"Trade proposal:\n{json.dumps(trade_proposal, indent=2, default=str)}\n\n"
            f"Risk assessment:\n{json.dumps(risk_assessment, indent=2, default=str)}\n"
        )

        response = self._call_llm(self.SYSTEM_PROMPT, user_prompt)
        result = self._validate_and_parse(
            response,
            required_fields={"approved": bool, "final_action": str, "final_size": float, "reasoning": str},
            defaults={"approved": False, "final_action": "hold", "final_size": 0.0, "reasoning": "Decision unavailable"},
        )

        self.logger.info(
            "Fund manager decision: approved=%s action=%s size=%s",
            result.get("approved"),
            result.get("final_action"),
            result.get("final_size"),
        )
        return result
