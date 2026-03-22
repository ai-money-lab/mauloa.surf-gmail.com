"""Risk manager agent for CITS trading pipeline."""

import json
import logging

from cits.core.agents.base_agent import BaseAgent


logger = logging.getLogger(__name__)


class RiskManager(BaseAgent):
    """Evaluates portfolio risk and market volatility before trade execution.

    Uses the deep_think (Opus) model for thorough risk assessment.
    Can approve, reject, or adjust proposed trades based on portfolio
    constraints, correlation analysis, and market conditions.
    """

    SYSTEM_PROMPT = (
        "You are the chief risk officer at a systematic trading fund.\n"
        "Your job is to evaluate proposed trades against portfolio constraints, "
        "market conditions, and risk limits. You have veto power over any trade.\n\n"
        "## Reasoning Framework (ReAct)\n"
        "1. **Observation**: Review the trade proposal and current portfolio.\n"
        "2. **Thought**: Assess the risk from multiple angles:\n"
        "   - Position concentration risk\n"
        "   - Correlation with existing holdings\n"
        "   - Market volatility regime (VIX / 日経VI)\n"
        "   - Liquidity risk and potential slippage\n"
        "   - Tail risk and maximum drawdown scenarios\n"
        "   - Currency exposure (JPY/USD) if applicable\n"
        "3. **Action**: Approve, reject, or adjust the proposed trade.\n\n"
        "## Risk Limits\n"
        "- Maximum single position: 10% of portfolio\n"
        "- Maximum sector exposure: 30% of portfolio\n"
        "- Maximum correlation with existing book: 0.7\n"
        "- Minimum liquidity: position must be closeable within 3 days\n"
        "- Stop-loss must be defined for every new position\n\n"
        "## Japanese Market Awareness\n"
        "- Monitor 日経VI (Nikkei Volatility Index) for JP equity risk.\n"
        "- Consider FX hedging costs for USD-based portfolios in JPY assets.\n"
        "- Factor in 信用取引 (margin trading) regulations and costs.\n"
        "- Note that Japanese markets can gap significantly on overnight "
        "US/global moves.\n"
        "- Watch for 追証 (margin call) cascade risks during selloffs.\n"
        "- Consider 決算 (earnings) and 権利落ち (ex-dividend) event risk.\n\n"
        "## Output\n"
        "Return ONLY a JSON object with these fields:\n"
        '  "approved": boolean,\n'
        '  "risk_score": float from 0.0 (no risk) to 10.0 (extreme risk),\n'
        '  "warnings": list of strings describing identified risks,\n'
        '  "adjusted_size": float (adjusted position size, may equal original)\n'
    )

    def __init__(self):
        super().__init__(
            name="risk_manager",
            role="Risk Manager",
            llm_type="deep_think",
        )

    def analyze(self, context: dict) -> dict:
        """Convenience wrapper that delegates to ``evaluate``."""
        return self.evaluate(
            trade_proposal=context.get("trade_proposal", {}),
            portfolio=context.get("portfolio", {}),
        )

    def evaluate(self, trade_proposal: dict, portfolio: dict) -> dict:
        """Evaluate a trade proposal against portfolio risk constraints.

        Args:
            trade_proposal: The proposed trade from the Trader agent, including
                action, size, ticker, and reasoning.
            portfolio: Current portfolio state including positions, cash,
                total value, and exposure metrics.

        Returns:
            dict with ``approved``, ``risk_score``, ``warnings``, and
            ``adjusted_size``.
        """
        self.logger.info(
            "Evaluating risk for proposed trade: %s",
            trade_proposal.get("action"),
        )

        user_prompt = (
            "Evaluate the following trade proposal against our risk limits "
            "and current portfolio.\n\n"
            f"Trade proposal:\n{json.dumps(trade_proposal, indent=2, default=str)}\n\n"
            f"Current portfolio:\n{json.dumps(portfolio, indent=2, default=str)}\n"
        )

        response = self._call_llm(self.SYSTEM_PROMPT, user_prompt)
        result = self._parse_json_response(response)

        self.logger.info(
            "Risk evaluation: approved=%s risk_score=%s warnings=%d",
            result.get("approved"),
            result.get("risk_score"),
            len(result.get("warnings", [])),
        )
        return result
