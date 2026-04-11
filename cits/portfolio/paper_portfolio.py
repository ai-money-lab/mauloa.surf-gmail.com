"""PaperPortfolio — simulated execution for paper trading.

Extends PortfolioManager to accept TradingGraph pipeline decisions and
simulate trade execution using current market prices from yfinance.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from cits.portfolio.portfolio_manager import PortfolioManager

logger = logging.getLogger(__name__)


class PaperPortfolio(PortfolioManager):
    """Paper trading portfolio that simulates order execution."""

    def __init__(
        self,
        initial_capital: float = 100_000,
        slippage_bps: float = 5.0,
        commission_per_trade: float = 0.0,
        spread_bps: float = 3.0,
        **kwargs,
    ) -> None:
        super().__init__(initial_capital=initial_capital, **kwargs)
        self.slippage_bps = slippage_bps  # basis points
        self.commission_per_trade = commission_per_trade  # flat fee per trade
        self.spread_bps = spread_bps  # bid-ask spread in bps

    def _apply_execution_costs(self, price: float, side: str) -> float:
        """Apply slippage and spread to simulate realistic fill price.

        For buys: price is adjusted UP (worse fill).
        For sells: price is adjusted DOWN (worse fill).
        """
        total_bps = self.slippage_bps + (self.spread_bps / 2)
        adjustment = price * total_bps / 10000

        if side in ("buy", "long"):
            return round(price + adjustment, 2)
        else:  # sell / short
            return round(price - adjustment, 2)

    def execute_paper_trade(self, decision_dict: dict) -> dict:
        """Simulate trade execution from a TradingGraph pipeline decision.

        Args:
            decision_dict: Pipeline output dict.  Expected keys:
                - ``ticker`` (str)
                - ``final_decision.final_action`` or ``final_decision.action`` (str)
                - ``final_decision.stop_loss`` (float, optional)
                - ``final_decision.take_profit`` (float, optional)
                - ``final_decision.final_size`` (int, optional)

        Returns:
            Execution result dict.
        """
        ticker = decision_dict.get("ticker", "")
        final_decision = decision_dict.get("final_decision", {})
        action = (
            final_decision.get("final_action")
            or final_decision.get("action", "hold")
        )

        if action == "hold":
            logger.info("Paper trade: HOLD for %s — no action taken", ticker)
            return {
                "status": "hold",
                "ticker": ticker,
                "message": "No action taken",
            }

        # Fetch current price via yfinance
        current_price = self._get_current_price(ticker)
        if current_price is None:
            logger.warning("Paper trade: could not fetch price for %s", ticker)
            return {
                "status": "error",
                "ticker": ticker,
                "message": f"Could not fetch price for {ticker}",
            }

        stop_loss = final_decision.get("stop_loss")
        take_profit = final_decision.get("take_profit")
        size = final_decision.get("final_size") or final_decision.get("size", 100)

        if action == "buy":
            # Apply execution costs
            fill_price = self._apply_execution_costs(current_price, "buy")
            result = self.open_position(
                ticker=ticker,
                side="long",
                size=size,
                entry_price=fill_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )
            # Deduct commission
            if self.commission_per_trade > 0:
                self.cash -= self.commission_per_trade
                logger.info(
                    "Commission charged: %.2f (cash remaining: %.2f)",
                    self.commission_per_trade, self.cash,
                )
            logger.info(
                "Paper BUY: %s x%d @ %.2f (market %.2f, slippage %.2fbps)",
                ticker, size, fill_price, current_price, self.slippage_bps,
            )
            return {
                "status": "filled",
                "action": "buy",
                "ticker": ticker,
                "side": "long",
                "size": size,
                "fill_price": fill_price,
                "market_price": current_price,
                "commission": self.commission_per_trade,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "position": result,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        if action == "sell":
            # Check for an existing open position to close
            existing = self.get_position_by_ticker(ticker)
            if existing:
                # Apply execution costs
                fill_price = self._apply_execution_costs(current_price, "sell")
                result = self.close_position(existing["id"], exit_price=fill_price)
                # Deduct commission
                if self.commission_per_trade > 0:
                    self.cash -= self.commission_per_trade
                    logger.info(
                        "Commission charged: %.2f (cash remaining: %.2f)",
                        self.commission_per_trade, self.cash,
                    )
                logger.info(
                    "Paper SELL (close): %s x%d @ %.2f (market %.2f)  PnL=%.2f",
                    ticker, existing["size"], fill_price, current_price,
                    result.get("pnl", 0),
                )
                return {
                    "status": "filled",
                    "action": "sell_close",
                    "ticker": ticker,
                    "size": existing["size"],
                    "fill_price": fill_price,
                    "market_price": current_price,
                    "commission": self.commission_per_trade,
                    "pnl": result.get("pnl", 0),
                    "position": result,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            else:
                # No existing position — open short
                fill_price = self._apply_execution_costs(current_price, "short")
                result = self.open_position(
                    ticker=ticker,
                    side="short",
                    size=size,
                    entry_price=fill_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                )
                # Deduct commission
                if self.commission_per_trade > 0:
                    self.cash -= self.commission_per_trade
                    logger.info(
                        "Commission charged: %.2f (cash remaining: %.2f)",
                        self.commission_per_trade, self.cash,
                    )
                logger.info(
                    "Paper SHORT: %s x%d @ %.2f (market %.2f)",
                    ticker, size, fill_price, current_price,
                )
                return {
                    "status": "filled",
                    "action": "sell_open",
                    "ticker": ticker,
                    "side": "short",
                    "size": size,
                    "fill_price": fill_price,
                    "market_price": current_price,
                    "commission": self.commission_per_trade,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "position": result,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

        logger.warning("Paper trade: unrecognised action '%s' for %s", action, ticker)
        return {
            "status": "error",
            "ticker": ticker,
            "message": f"Unrecognised action: {action}",
        }

    # ------------------------------------------------------------------
    # Price helper
    # ------------------------------------------------------------------

    @staticmethod
    def _get_current_price(ticker: str) -> float | None:
        """Fetch the latest price for *ticker* via yfinance.

        Appends ``.T`` for TSE tickers that are purely numeric.

        Returns:
            Current price as float, or None on failure.
        """
        try:
            import yfinance as yf  # noqa: E402

            symbol = f"{ticker}.T" if ticker.isdigit() else ticker
            data = yf.Ticker(symbol)
            hist = data.history(period="1d")
            if hist.empty:
                return None
            return float(hist["Close"].iloc[-1])
        except Exception as exc:
            logger.error("yfinance price fetch failed for %s: %s", ticker, exc)
            return None
