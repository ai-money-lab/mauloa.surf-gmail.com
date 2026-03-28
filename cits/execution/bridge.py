"""ExecutionBridge — routes fund-manager decisions to the appropriate broker.

Supports two modes:
  - **paper**: simulated execution via :class:`PaperPortfolio`
  - **live**: real execution via :class:`KabuStationAPI` with OCO management
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from cits.portfolio.portfolio_manager import PortfolioManager
from cits.portfolio.paper_portfolio import PaperPortfolio

logger = logging.getLogger(__name__)


class ExecutionBridge:
    """Bridges pipeline decisions to broker execution or paper simulation.

    Parameters
    ----------
    broker : object or None
        A :class:`KabuStationAPI` instance (required for live mode).
    portfolio_manager : PortfolioManager
        The portfolio manager that tracks positions and equity.
    mode : str
        ``"paper"`` (default) or ``"live"``.
    """

    def __init__(
        self,
        broker=None,
        portfolio_manager: PortfolioManager | None = None,
        mode: str = "paper",
    ) -> None:
        self.broker = broker
        self.mode = mode

        if mode == "paper":
            # Wrap the portfolio manager as a PaperPortfolio if it isn't already
            if isinstance(portfolio_manager, PaperPortfolio):
                self.portfolio = portfolio_manager
            else:
                self.portfolio = PaperPortfolio(
                    initial_capital=(
                        portfolio_manager.initial_capital if portfolio_manager else 100_000
                    ),
                )
        else:
            self.portfolio = portfolio_manager or PortfolioManager()

        logger.info("ExecutionBridge initialised: mode=%s", self.mode)

    # ------------------------------------------------------------------
    # Main execute
    # ------------------------------------------------------------------

    def execute(self, pipeline_result: dict) -> dict:
        """Execute a trade based on the pipeline result.

        Args:
            pipeline_result: Full output from :meth:`TradingGraph.run`.

        Returns:
            Execution result dict with order_id, fill_price, size, oco_status.
        """
        final_decision = pipeline_result.get("final_decision", {})
        action = (
            final_decision.get("final_action")
            or final_decision.get("action", "hold")
        )
        approved = final_decision.get("approved", False)

        if not approved:
            logger.info("Execution skipped: decision not approved")
            return {
                "status": "skipped",
                "reason": "not_approved",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        if action == "hold":
            logger.info("Execution: HOLD — no order")
            return {
                "status": "hold",
                "reason": "hold_decision",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        if self.mode == "paper":
            return self._execute_paper(pipeline_result)
        return self._execute_live(pipeline_result)

    # ------------------------------------------------------------------
    # Paper execution
    # ------------------------------------------------------------------

    def _execute_paper(self, pipeline_result: dict) -> dict:
        """Route to PaperPortfolio for simulated execution."""
        if not isinstance(self.portfolio, PaperPortfolio):
            logger.error("Paper mode requires a PaperPortfolio instance")
            return {"status": "error", "message": "PaperPortfolio not available"}

        result = self.portfolio.execute_paper_trade(pipeline_result)
        result["order_id"] = f"paper-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        result["oco_status"] = "simulated"
        return result

    # ------------------------------------------------------------------
    # Live execution
    # ------------------------------------------------------------------

    def _execute_live(self, pipeline_result: dict) -> dict:
        """Route to KabuStationAPI for real execution."""
        if self.broker is None:
            logger.error("Live mode requires a broker instance")
            return {"status": "error", "message": "Broker not configured"}

        final_decision = pipeline_result.get("final_decision", {})
        ticker = pipeline_result.get("ticker", "")
        action = (
            final_decision.get("final_action")
            or final_decision.get("action", "hold")
        )

        stop_loss = final_decision.get("stop_loss")
        take_profit = final_decision.get("take_profit")

        # Use PositionSizer for size calculation
        size = self._calculate_live_size(ticker, final_decision)

        # Map action to broker side
        side = "buy" if action == "buy" else "sell"

        try:
            order_resp = self.broker.place_order(
                symbol=ticker,
                side=side,
                qty=size,
                order_type="market",
            )
            order_id = order_resp.get("OrderId", "unknown")
        except Exception as exc:
            logger.error("Live order failed: %s", exc)
            return {"status": "error", "message": str(exc)}

        # Record in portfolio
        if action == "buy":
            board = self.broker.get_board(ticker)
            fill_price = board.get("CurrentPrice", 0)
            self.portfolio.open_position(
                ticker=ticker,
                side="long",
                size=size,
                entry_price=fill_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )
        elif action == "sell":
            existing = self.portfolio.get_position_by_ticker(ticker)
            if existing:
                board = self.broker.get_board(ticker)
                fill_price = board.get("CurrentPrice", 0)
                self.portfolio.close_position(existing["id"], exit_price=fill_price)
            else:
                board = self.broker.get_board(ticker)
                fill_price = board.get("CurrentPrice", 0)
                self.portfolio.open_position(
                    ticker=ticker,
                    side="short",
                    size=size,
                    entry_price=fill_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                )

        # Set up SoftwareOCO for TP/SL if both are specified
        oco_status = "none"
        if stop_loss and take_profit:
            try:
                from cits.japan.broker.software_oco import SoftwareOCO

                oco = SoftwareOCO(broker=self.broker)
                oco_id = oco.create_oco(
                    symbol=ticker,
                    side=side,
                    qty=size,
                    take_profit=take_profit,
                    stop_loss=stop_loss,
                )
                oco_status = f"active:{oco_id}"
                logger.info("OCO created: %s", oco_id)
            except Exception as exc:
                logger.error("OCO creation failed: %s", exc)
                oco_status = f"error:{exc}"

        return {
            "status": "filled",
            "order_id": order_id,
            "fill_price": fill_price,
            "size": size,
            "side": side,
            "oco_status": oco_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Position management
    # ------------------------------------------------------------------

    def check_and_manage_positions(self) -> dict:
        """Check open positions and update unrealized P&L.

        For live mode, also applies trailing-stop logic: if unrealized
        profit exceeds 2x the original risk (entry - stop_loss), the stop
        is moved to break-even.

        Returns:
            Summary dict with managed position count and actions taken.
        """
        positions = self.portfolio.get_open_positions()
        actions_taken: list[dict] = []

        if self.mode == "live" and self.broker is not None:
            price_dict: dict[str, float] = {}
            for pos in positions:
                board = self.broker.get_board(pos["ticker"])
                current_price = board.get("CurrentPrice")
                if current_price is not None:
                    price_dict[pos["ticker"]] = current_price

                    # Trailing stop logic
                    if pos["stop_loss"] is not None:
                        self._apply_trailing_stop(pos, current_price, actions_taken)

            self.portfolio.update_market_prices(price_dict)
        else:
            # Paper mode — fetch prices via yfinance
            price_dict = {}
            for pos in positions:
                price = PaperPortfolio._get_current_price(pos["ticker"])
                if price is not None:
                    price_dict[pos["ticker"]] = price
            if price_dict:
                self.portfolio.update_market_prices(price_dict)

        return {
            "positions_checked": len(positions),
            "actions_taken": actions_taken,
            "daily_pnl": self.portfolio.get_daily_pnl(),
        }

    def _apply_trailing_stop(
        self,
        pos: dict,
        current_price: float,
        actions_taken: list[dict],
    ) -> None:
        """Move stop to break-even once profit >= 2x original risk."""
        entry = pos["entry_price"]
        sl = pos["stop_loss"]
        if sl is None:
            return

        original_risk = abs(entry - sl)
        if original_risk <= 0:
            return

        if pos["side"] == "long":
            unrealized = current_price - entry
            if unrealized >= 2 * original_risk and sl < entry:
                # Move stop to break-even
                try:
                    with self.portfolio._conn() as conn:
                        conn.execute(
                            "UPDATE positions SET stop_loss = ? WHERE id = ?",
                            (entry, pos["id"]),
                        )
                        conn.commit()
                    actions_taken.append({
                        "position_id": pos["id"],
                        "action": "trailing_stop_to_breakeven",
                        "old_sl": sl,
                        "new_sl": entry,
                    })
                    logger.info(
                        "Trailing stop: pos %s SL moved %.2f -> %.2f (breakeven)",
                        pos["id"], sl, entry,
                    )
                except Exception as exc:
                    logger.error("Trailing stop update failed: %s", exc)
        else:  # short
            unrealized = entry - current_price
            if unrealized >= 2 * original_risk and sl > entry:
                try:
                    with self.portfolio._conn() as conn:
                        conn.execute(
                            "UPDATE positions SET stop_loss = ? WHERE id = ?",
                            (entry, pos["id"]),
                        )
                        conn.commit()
                    actions_taken.append({
                        "position_id": pos["id"],
                        "action": "trailing_stop_to_breakeven",
                        "old_sl": sl,
                        "new_sl": entry,
                    })
                    logger.info(
                        "Trailing stop: pos %s SL moved %.2f -> %.2f (breakeven)",
                        pos["id"], sl, entry,
                    )
                except Exception as exc:
                    logger.error("Trailing stop update failed: %s", exc)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _calculate_live_size(self, ticker: str, decision: dict) -> int:
        """Use PositionSizer if stop_loss is available, else fall back to decision size."""
        size = decision.get("final_size") or decision.get("size", 100)
        stop_loss = decision.get("stop_loss")

        if stop_loss is not None and self.broker is not None:
            try:
                from cits.risk.position_sizer import PositionSizer

                board = self.broker.get_board(ticker)
                entry_price = board.get("CurrentPrice", 0)
                if entry_price > 0:
                    sizer = PositionSizer(
                        account_size=self.portfolio._latest_state()["total_equity"],
                    )
                    sizing = sizer.calculate_size(
                        entry_price=entry_price,
                        stop_loss=stop_loss,
                    )
                    calculated = sizing.get("position_size", 0)
                    if calculated > 0:
                        return calculated
            except Exception as exc:
                logger.warning("PositionSizer failed, using default size: %s", exc)

        return size
