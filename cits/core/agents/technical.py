"""Technical analysis agent for CITS trading pipeline."""

import logging

from cits.core.agents.base_agent import BaseAgent


logger = logging.getLogger(__name__)


class TechnicalAnalyst(BaseAgent):
    """Analyses price action, volume patterns, and technical indicators.

    Produces a technical score from -10 (strong bearish setup) to +10
    (strong bullish setup) along with identified signals and key
    support/resistance levels.
    """

    SYSTEM_PROMPT = (
        "You are a senior technical analyst in a systematic trading fund.\n"
        "Your role is to evaluate price charts, volume profiles, and "
        "technical indicators to identify trading signals and key levels.\n\n"
        "## Reasoning Framework (ReAct)\n"
        "1. **Observation**: Describe the current price structure, trend, "
        "and indicator readings.\n"
        "2. **Thought**: Interpret the confluence of signals. Look for "
        "confirmation or divergence across multiple timeframes and "
        "indicators. Assess the probability of continuation vs reversal.\n"
        "3. **Action**: Produce your final technical assessment.\n\n"
        "## Indicators to Consider\n"
        "- Trend: SMA/EMA (20, 50, 200), MACD, ADX\n"
        "- Momentum: RSI, Stochastic, Williams %R\n"
        "- Volatility: Bollinger Bands, ATR, VIX/VI (for JP markets)\n"
        "- Volume: OBV, VWAP, volume profile, 出来高\n"
        "- Japanese-specific: Ichimoku Cloud (一目均衡表) is especially "
        "important for Japanese equities and USD/JPY.\n\n"
        "## Japanese Market Awareness\n"
        "- Ichimoku analysis is primary for Nikkei and TOPIX components.\n"
        "- Note 信用倍率 (margin ratio) as a sentiment/positioning indicator.\n"
        "- Consider 裁定取引残高 (arbitrage balance) for index futures.\n"
        "- Watch 空売り比率 (short-selling ratio) published by JPX.\n"
        "- Be aware of price limits (ストップ高/ストップ安) on individual stocks.\n\n"
        "## Output\n"
        "Return ONLY a JSON object with these fields:\n"
        '  "technical_score": integer from -10 to 10,\n'
        '  "signals": list of objects with "indicator", "reading", "interpretation",\n'
        '  "support_resistance": object with "support_levels" and "resistance_levels" '
        "(each a list of price levels)\n"
    )

    def __init__(self, llm_type: str = "quick_think"):
        super().__init__(
            name="technical_analyst",
            role="Technical Analyst",
            llm_type=llm_type,
        )

    def analyze(self, context: dict) -> dict:
        """Analyse technical data for a given ticker.

        Args:
            context: Must contain ``ticker``. May contain ``price_data``,
                     ``indicators``, ``volume_data``, ``ichimoku``.

        Returns:
            dict with ``technical_score``, ``signals``, and
            ``support_resistance``.
        """
        ticker = context.get("ticker", "UNKNOWN")
        self.logger.info("Running technical analysis for %s", ticker)

        user_prompt_parts = [
            f"Analyse the technical setup for {ticker}.\n"
        ]

        if context.get("price_data"):
            user_prompt_parts.append(
                f"Price data (OHLCV):\n{context['price_data']}\n"
            )

        if context.get("indicators"):
            user_prompt_parts.append(
                f"Technical indicators:\n{context['indicators']}\n"
            )

        if context.get("volume_data"):
            user_prompt_parts.append(
                f"Volume analysis:\n{context['volume_data']}\n"
            )

        if context.get("ichimoku"):
            user_prompt_parts.append(
                f"Ichimoku Cloud data:\n{context['ichimoku']}\n"
            )

        user_prompt = "\n".join(user_prompt_parts)
        response = self._call_llm(self.SYSTEM_PROMPT, user_prompt)
        result = self._validate_and_parse(
            response,
            required_fields={"technical_score": int, "signals": list, "support_resistance": dict},
            defaults={"technical_score": 0, "signals": [], "support_resistance": {"support_levels": [], "resistance_levels": []}},
        )

        self.logger.info(
            "Technical analysis complete for %s: score=%s",
            ticker,
            result.get("technical_score"),
        )
        return result
