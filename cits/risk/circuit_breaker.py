"""
Circuit Breaker — auto-stops trading when adverse conditions are detected.

Rules:
  1. Daily loss exceeds max_daily_loss → halt
  2. N consecutive losses → halt
  3. Daily trade count exceeds max → halt
  4. Market volatility exceeds threshold → reduce position size
  5. Near SQ date (2nd Friday of month) → reduce position size
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)


def _second_friday(year: int, month: int) -> date:
    """Return the date of the 2nd Friday of the given month."""
    # Find first day of month, then first Friday
    first_day = date(year, month, 1)
    # weekday(): Monday=0 … Friday=4
    days_until_friday = (4 - first_day.weekday()) % 7
    first_friday = first_day + timedelta(days=days_until_friday)
    return first_friday + timedelta(weeks=1)


class CircuitBreaker:
    """Auto-stops or reduces trading under adverse conditions."""

    def __init__(
        self,
        max_daily_loss: float = 50000,
        max_consecutive_losses: int = 3,
        max_daily_trades: int = 10,
        volatility_threshold: float = 3.0,
    ) -> None:
        """
        Args:
            max_daily_loss: Maximum acceptable daily loss in JPY (or account currency).
            max_consecutive_losses: Halt after this many consecutive losing trades.
            max_daily_trades: Maximum number of trades per day.
            volatility_threshold: VIX-equivalent level that triggers position reduction.
        """
        self.max_daily_loss = max_daily_loss
        self.max_consecutive_losses = max_consecutive_losses
        self.max_daily_trades = max_daily_trades
        self.volatility_threshold = volatility_threshold

        # Daily counters (reset via reset_daily)
        self.daily_pnl: float = 0.0
        self.consecutive_losses: int = 0
        self.daily_trade_count: int = 0

    def check(self, portfolio: dict, market_data: dict) -> dict:
        """
        Run all circuit-breaker checks.

        Args:
            portfolio: Dict with keys like "daily_pnl", "consecutive_losses",
                       "daily_trade_count".
            market_data: Dict with keys like "volatility" (VIX-equivalent),
                         "date" (ISO string or date object).

        Returns:
            Dict with:
              - is_triggered (bool)
              - reason (str)
              - action ("halt" | "reduce" | "continue")
        """
        # Update internal state from portfolio
        self.daily_pnl = portfolio.get("daily_pnl", self.daily_pnl)
        self.consecutive_losses = portfolio.get("consecutive_losses", self.consecutive_losses)
        self.daily_trade_count = portfolio.get("daily_trade_count", self.daily_trade_count)

        # Rule 1: daily loss
        if self.daily_pnl <= -abs(self.max_daily_loss):
            reason = (
                f"Daily loss ¥{abs(self.daily_pnl):,.0f} exceeds "
                f"limit ¥{self.max_daily_loss:,.0f}"
            )
            logger.warning("CIRCUIT BREAKER HALT: %s", reason)
            return {"is_triggered": True, "reason": reason, "action": "halt"}

        # Rule 2: consecutive losses
        if self.consecutive_losses >= self.max_consecutive_losses:
            reason = (
                f"{self.consecutive_losses} consecutive losses "
                f"(limit: {self.max_consecutive_losses})"
            )
            logger.warning("CIRCUIT BREAKER HALT: %s", reason)
            return {"is_triggered": True, "reason": reason, "action": "halt"}

        # Rule 3: daily trade count
        if self.daily_trade_count >= self.max_daily_trades:
            reason = (
                f"{self.daily_trade_count} trades today "
                f"(limit: {self.max_daily_trades})"
            )
            logger.warning("CIRCUIT BREAKER HALT: %s", reason)
            return {"is_triggered": True, "reason": reason, "action": "halt"}

        # Rule 4: volatility
        volatility = market_data.get("volatility", 0.0)
        if volatility >= self.volatility_threshold:
            reason = (
                f"Volatility {volatility:.1f}% exceeds "
                f"threshold {self.volatility_threshold:.1f}%"
            )
            logger.warning("CIRCUIT BREAKER REDUCE: %s", reason)
            return {"is_triggered": True, "reason": reason, "action": "reduce"}

        # Rule 5: near SQ date (2nd Friday of month)
        today = market_data.get("date")
        if today is not None:
            if isinstance(today, str):
                today = date.fromisoformat(today)
            sq_date = _second_friday(today.year, today.month)
            days_to_sq = (sq_date - today).days
            if 0 <= days_to_sq <= 2:
                reason = f"SQ date in {days_to_sq} day(s) ({sq_date.isoformat()})"
                logger.warning("CIRCUIT BREAKER REDUCE: %s", reason)
                return {"is_triggered": True, "reason": reason, "action": "reduce"}

        return {"is_triggered": False, "reason": "", "action": "continue"}

    def reset_daily(self) -> None:
        """Reset daily counters. Call at the start of each trading day."""
        self.daily_pnl = 0.0
        self.consecutive_losses = 0
        self.daily_trade_count = 0
        logger.info("Circuit breaker daily counters reset")
