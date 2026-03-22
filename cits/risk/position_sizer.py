"""
Position Sizer — calculates appropriate position sizes based on risk parameters.

Methods:
  - Fixed-risk sizing (risk per trade as % of account)
  - Kelly criterion adjustment
  - Volatility-based adjustment
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class PositionSizer:
    """Calculates position sizes with risk-aware adjustments."""

    def __init__(
        self,
        account_size: float = 100000,
        max_risk_per_trade: float = 0.02,
        max_position_ratio: float = 0.2,
    ) -> None:
        """
        Args:
            account_size: Total account value in JPY (or account currency).
            max_risk_per_trade: Maximum risk per trade as fraction of account (0.02 = 2%).
            max_position_ratio: Maximum single-position notional as fraction of account.
        """
        self.account_size = account_size
        self.max_risk_per_trade = max_risk_per_trade
        self.max_position_ratio = max_position_ratio

    def calculate_size(
        self,
        entry_price: float,
        stop_loss: float,
        volatility: float | None = None,
    ) -> dict:
        """
        Calculate position size based on fixed-risk model.

        Risk amount = account_size * max_risk_per_trade
        Risk per unit = |entry_price - stop_loss|
        Position size = risk_amount / risk_per_unit

        The result is capped so that notional_value does not exceed
        account_size * max_position_ratio.

        Args:
            entry_price: Planned entry price.
            stop_loss: Stop-loss price.
            volatility: Optional current volatility for adjustment.

        Returns:
            Dict with position_size (int), risk_amount (float),
            notional_value (float).
        """
        if entry_price <= 0:
            logger.error("Invalid entry_price: %.2f", entry_price)
            return {"position_size": 0, "risk_amount": 0.0, "notional_value": 0.0}

        risk_per_unit = abs(entry_price - stop_loss)
        if risk_per_unit <= 0:
            logger.error("entry_price and stop_loss are equal — cannot size position")
            return {"position_size": 0, "risk_amount": 0.0, "notional_value": 0.0}

        risk_amount = self.account_size * self.max_risk_per_trade
        position_size = int(risk_amount / risk_per_unit)

        # Cap by max position ratio
        max_notional = self.account_size * self.max_position_ratio
        max_size_by_notional = int(max_notional / entry_price)
        if position_size > max_size_by_notional:
            logger.info(
                "Position capped by max_position_ratio: %d -> %d",
                position_size, max_size_by_notional,
            )
            position_size = max_size_by_notional

        # Optional volatility adjustment
        if volatility is not None and volatility > 0:
            position_size = self.adjust_for_volatility(
                base_size=position_size,
                current_vol=volatility,
                avg_vol=volatility,  # caller should provide proper avg
            )

        position_size = max(position_size, 0)
        notional_value = position_size * entry_price

        logger.info(
            "Position sized: %d units @ ¥%.2f = ¥%.0f notional (risk ¥%.0f)",
            position_size, entry_price, notional_value, risk_amount,
        )

        return {
            "position_size": position_size,
            "risk_amount": round(risk_amount, 2),
            "notional_value": round(notional_value, 2),
        }

    def adjust_for_kelly(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
    ) -> float:
        """
        Calculate Kelly criterion fraction for position sizing.

        Kelly % = W - (1 - W) / R
        where W = win rate, R = avg_win / avg_loss

        The result is halved (half-Kelly) for safety and capped at
        max_risk_per_trade.

        Args:
            win_rate: Historical win rate (0.0–1.0).
            avg_win: Average winning trade profit.
            avg_loss: Average losing trade loss (positive number).

        Returns:
            Recommended risk fraction (0.0 – max_risk_per_trade).
        """
        if avg_loss <= 0 or win_rate <= 0:
            logger.warning("Kelly inputs invalid: win_rate=%.2f, avg_loss=%.2f", win_rate, avg_loss)
            return 0.0

        r = avg_win / avg_loss  # win/loss ratio
        kelly = win_rate - (1.0 - win_rate) / r

        if kelly <= 0:
            logger.info("Kelly fraction negative (%.4f) — edge insufficient", kelly)
            return 0.0

        # Half-Kelly for safety
        half_kelly = kelly / 2.0

        # Cap at max risk per trade
        result = min(half_kelly, self.max_risk_per_trade)

        logger.info(
            "Kelly: full=%.4f  half=%.4f  capped=%.4f (W=%.2f R=%.2f)",
            kelly, half_kelly, result, win_rate, r,
        )
        return round(result, 6)

    def adjust_for_volatility(
        self,
        base_size: int,
        current_vol: float,
        avg_vol: float,
    ) -> int:
        """
        Adjust position size inversely with volatility.

        If current vol > avg vol, reduce size proportionally.
        If current vol < avg vol, do NOT increase beyond base_size
        (conservative — never lever up on low vol).

        Args:
            base_size: Base position size (shares/contracts).
            current_vol: Current volatility measure.
            avg_vol: Average/normal volatility measure.

        Returns:
            Adjusted position size (int, >= 0).
        """
        if avg_vol <= 0 or current_vol <= 0:
            logger.warning("Volatility inputs invalid: current=%.2f avg=%.2f", current_vol, avg_vol)
            return base_size

        vol_ratio = current_vol / avg_vol

        if vol_ratio <= 1.0:
            # Low vol — keep base size (no leverage-up)
            return base_size

        # High vol — reduce proportionally
        adjusted = int(base_size / vol_ratio)
        adjusted = max(adjusted, 0)

        logger.info(
            "Vol adjustment: %d -> %d (vol ratio %.2f)",
            base_size, adjusted, vol_ratio,
        )
        return adjusted
