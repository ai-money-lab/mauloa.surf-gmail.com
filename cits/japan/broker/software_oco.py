"""
Software OCO (One-Cancels-Other) Order Manager

kabuステーション does not support native OCO orders, so this module
implements OCO logic in software:

- Take-Profit (TP): soft limit — polls current price, executes market
  order when price >= TP (for long) or price <= TP (for short).
- Stop-Loss (SL): placed as an actual reverse stop order via broker API
  and cancelled if TP fires first.

Each OCO pair runs in a background thread that monitors price at a
configurable interval.
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field

from cits.japan.broker.kabu_api import KabuStationAPI

logger = logging.getLogger(__name__)


@dataclass
class _OCOState:
    """Internal state for a single OCO order pair."""
    oco_id: str
    symbol: str
    side: str           # "buy" or "sell" — the direction of the ORIGINAL position
    qty: int
    take_profit: float
    stop_loss: float
    sl_order_id: str | None = None
    status: str = "active"   # active / filled_tp / filled_sl / cancelled
    thread: threading.Thread | None = field(default=None, repr=False)
    stop_event: threading.Event = field(default_factory=threading.Event, repr=False)


class SoftwareOCO:
    """Manages software-based OCO order pairs."""

    def __init__(self, broker: KabuStationAPI, check_interval: float = 1.0) -> None:
        """
        Args:
            broker: KabuStationAPI instance for market data and order execution.
            check_interval: Seconds between price checks (default 1s).
        """
        self.broker = broker
        self.check_interval = check_interval
        self._ocos: dict[str, _OCOState] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_oco(
        self,
        symbol: str,
        side: str,
        qty: int,
        take_profit: float,
        stop_loss: float,
    ) -> str:
        """
        Create an OCO order pair.

        For a long position (side="buy"):
          - TP triggers when current price >= take_profit
          - SL triggers when current price <= stop_loss
        For a short position (side="sell"):
          - TP triggers when current price <= take_profit
          - SL triggers when current price >= stop_loss

        Args:
            symbol: Security code.
            side: Side of the original position ("buy" or "sell").
            qty: Number of shares/contracts to close.
            take_profit: Take-profit price level.
            stop_loss: Stop-loss price level.

        Returns:
            The generated oco_id string.
        """
        oco_id = str(uuid.uuid4())[:8]

        # Determine the exit side (opposite of position side)
        exit_side = "sell" if side == "buy" else "buy"

        # Place the stop-loss as an actual order via broker
        sl_order_id: str | None = None
        try:
            sl_resp = self.broker.place_order(
                symbol=symbol,
                side=exit_side,
                qty=qty,
                order_type="limit",
                price=stop_loss,
            )
            sl_order_id = sl_resp.get("OrderId")
            if sl_order_id:
                logger.info("OCO %s: SL order placed (OrderId=%s) @ %.2f", oco_id, sl_order_id, stop_loss)
            else:
                logger.warning("OCO %s: SL order response missing OrderId: %s", oco_id, sl_resp)
        except Exception as exc:
            logger.error("OCO %s: Failed to place SL order: %s", oco_id, exc)

        state = _OCOState(
            oco_id=oco_id,
            symbol=symbol,
            side=side,
            qty=qty,
            take_profit=take_profit,
            stop_loss=stop_loss,
            sl_order_id=sl_order_id,
        )

        # Start monitoring thread
        thread = threading.Thread(
            target=self._monitor_oco,
            args=(oco_id,),
            name=f"oco-{oco_id}",
            daemon=True,
        )
        state.thread = thread

        with self._lock:
            self._ocos[oco_id] = state

        thread.start()
        logger.info(
            "OCO %s created: %s %s x%d  TP=%.2f  SL=%.2f",
            oco_id, side, symbol, qty, take_profit, stop_loss,
        )
        return oco_id

    def cancel_oco(self, oco_id: str) -> bool:
        """
        Cancel an active OCO order pair.

        Args:
            oco_id: The OCO identifier.

        Returns:
            True if the OCO was found and cancellation was initiated.
        """
        with self._lock:
            state = self._ocos.get(oco_id)
            if state is None or state.status != "active":
                logger.warning("OCO %s: not found or not active", oco_id)
                return False

            state.status = "cancelled"
            state.stop_event.set()

        # Cancel the SL order if it was placed
        if state.sl_order_id:
            try:
                self.broker.cancel_order(state.sl_order_id)
                logger.info("OCO %s: SL order %s cancelled", oco_id, state.sl_order_id)
            except Exception as exc:
                logger.error("OCO %s: Failed to cancel SL order: %s", oco_id, exc)

        logger.info("OCO %s: cancelled", oco_id)
        return True

    def get_active_ocos(self) -> list[dict]:
        """
        List all active OCO order pairs.

        Returns:
            List of dicts with oco_id, symbol, side, qty, take_profit,
            stop_loss, status.
        """
        with self._lock:
            return [
                {
                    "oco_id": s.oco_id,
                    "symbol": s.symbol,
                    "side": s.side,
                    "qty": s.qty,
                    "take_profit": s.take_profit,
                    "stop_loss": s.stop_loss,
                    "status": s.status,
                }
                for s in self._ocos.values()
                if s.status == "active"
            ]

    # ------------------------------------------------------------------
    # Background monitoring
    # ------------------------------------------------------------------

    def _monitor_oco(self, oco_id: str) -> None:
        """
        Background loop that monitors price and executes TP or SL.

        For TP: checks if price has reached take-profit, then fires a
        market order and cancels the standing SL order.

        For SL: if the broker-side SL fills, we detect it and mark done.
        """
        with self._lock:
            state = self._ocos.get(oco_id)
        if state is None:
            return

        exit_side = "sell" if state.side == "buy" else "buy"
        is_long = state.side == "buy"

        logger.info("OCO %s: monitoring started (interval=%.1fs)", oco_id, self.check_interval)

        while not state.stop_event.is_set():
            try:
                board = self.broker.get_board(state.symbol)
                current_price = board.get("CurrentPrice")

                if current_price is None:
                    logger.debug("OCO %s: no current price available", oco_id)
                    state.stop_event.wait(self.check_interval)
                    continue

                # Check take-profit
                tp_hit = (
                    (is_long and current_price >= state.take_profit) or
                    (not is_long and current_price <= state.take_profit)
                )

                if tp_hit:
                    logger.info(
                        "OCO %s: TP hit! price=%.2f >= TP=%.2f" if is_long
                        else "OCO %s: TP hit! price=%.2f <= TP=%.2f",
                        oco_id, current_price, state.take_profit,
                    )
                    # Execute TP as market order
                    try:
                        self.broker.place_order(
                            symbol=state.symbol,
                            side=exit_side,
                            qty=state.qty,
                            order_type="market",
                        )
                        logger.info("OCO %s: TP market order sent", oco_id)
                    except Exception as exc:
                        logger.error("OCO %s: TP order failed: %s", oco_id, exc)

                    # Cancel SL order
                    if state.sl_order_id:
                        try:
                            self.broker.cancel_order(state.sl_order_id)
                            logger.info("OCO %s: SL order cancelled after TP", oco_id)
                        except Exception as exc:
                            logger.error("OCO %s: SL cancel failed: %s", oco_id, exc)

                    with self._lock:
                        state.status = "filled_tp"
                    return

                # Check if SL order has been filled (by querying orders)
                if state.sl_order_id:
                    try:
                        orders = self.broker.get_orders()
                        for order in orders:
                            if order.get("OrderId") == state.sl_order_id:
                                # State 5 = 完了 (completed/filled)
                                if order.get("State") == 5:
                                    logger.info("OCO %s: SL order filled", oco_id)
                                    with self._lock:
                                        state.status = "filled_sl"
                                    return
                                break
                    except Exception as exc:
                        logger.error("OCO %s: order check failed: %s", oco_id, exc)

            except Exception as exc:
                logger.error("OCO %s: monitoring error: %s", oco_id, exc)

            state.stop_event.wait(self.check_interval)

        logger.info("OCO %s: monitoring stopped (status=%s)", oco_id, state.status)
