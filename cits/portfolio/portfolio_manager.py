"""PortfolioManager — SQLite-backed portfolio tracking for CITS.

Tracks open/closed positions and portfolio state (equity, cash, P&L).
Database stored at ``cits/logs/portfolio.db``.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_DB_DIR = Path(__file__).resolve().parent.parent / "logs"
_DB_PATH = _DB_DIR / "portfolio.db"

_CREATE_POSITIONS_SQL = """
CREATE TABLE IF NOT EXISTS positions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker       TEXT    NOT NULL,
    side         TEXT    NOT NULL CHECK (side IN ('long', 'short')),
    size         INTEGER NOT NULL,
    entry_price  REAL    NOT NULL,
    entry_date   TEXT    NOT NULL,
    stop_loss    REAL,
    take_profit  REAL,
    status       TEXT    NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
    exit_price   REAL,
    exit_date    TEXT,
    pnl          REAL
);
"""

_CREATE_STATE_SQL = """
CREATE TABLE IF NOT EXISTS portfolio_state (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    date               TEXT    NOT NULL,
    total_equity       REAL    NOT NULL,
    cash               REAL    NOT NULL,
    invested           REAL    NOT NULL DEFAULT 0,
    unrealized_pnl     REAL    NOT NULL DEFAULT 0,
    realized_pnl_today REAL    NOT NULL DEFAULT 0
);
"""


class PortfolioManager:
    """SQLite-backed portfolio manager for CITS."""

    def __init__(
        self,
        initial_capital: float = 100_000,
        db_path: str | Path | None = None,
    ) -> None:
        """
        Args:
            initial_capital: Starting capital in JPY (default 10,000,000).
            db_path: Override default SQLite path.
        """
        self.initial_capital = initial_capital
        self.db_path = Path(db_path) if db_path else _DB_PATH

        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_db()

        # Seed initial portfolio state if table is empty
        if not self._has_state():
            self._save_state(
                total_equity=initial_capital,
                cash=initial_capital,
                invested=0.0,
                unrealized_pnl=0.0,
                realized_pnl_today=0.0,
            )

    # ------------------------------------------------------------------
    # Database helpers
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute(_CREATE_POSITIONS_SQL)
                conn.execute(_CREATE_STATE_SQL)
                conn.commit()
            logger.debug("Portfolio DB initialised at %s", self.db_path)
        except sqlite3.Error as exc:
            logger.error("Failed to initialise portfolio DB: %s", exc)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _has_state(self) -> bool:
        try:
            with self._conn() as conn:
                row = conn.execute("SELECT COUNT(*) AS cnt FROM portfolio_state").fetchone()
                return row["cnt"] > 0
        except sqlite3.Error:
            return False

    def _save_state(
        self,
        total_equity: float,
        cash: float,
        invested: float,
        unrealized_pnl: float,
        realized_pnl_today: float,
    ) -> None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        try:
            with self._conn() as conn:
                conn.execute(
                    """
                    INSERT INTO portfolio_state
                        (date, total_equity, cash, invested, unrealized_pnl, realized_pnl_today)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (today, total_equity, cash, invested, unrealized_pnl, realized_pnl_today),
                )
                conn.commit()
        except sqlite3.Error as exc:
            logger.error("Failed to save portfolio state: %s", exc)

    def _latest_state(self) -> dict:
        try:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT * FROM portfolio_state ORDER BY id DESC LIMIT 1"
                ).fetchone()
                if row:
                    return dict(row)
        except sqlite3.Error as exc:
            logger.error("Failed to read portfolio state: %s", exc)
        return {
            "total_equity": self.initial_capital,
            "cash": self.initial_capital,
            "invested": 0.0,
            "unrealized_pnl": 0.0,
            "realized_pnl_today": 0.0,
        }

    # ------------------------------------------------------------------
    # Position management
    # ------------------------------------------------------------------

    def open_position(
        self,
        ticker: str,
        side: str,
        size: int,
        entry_price: float,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> dict:
        """Record a new position and deduct cash.

        Returns:
            Dict with position id and details.
        """
        entry_date = datetime.now(timezone.utc).isoformat()
        try:
            with self._conn() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO positions
                        (ticker, side, size, entry_price, entry_date,
                         stop_loss, take_profit, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'open')
                    """,
                    (ticker, side, size, entry_price, entry_date, stop_loss, take_profit),
                )
                conn.commit()
                position_id = cursor.lastrowid
        except sqlite3.Error as exc:
            logger.error("Failed to open position: %s", exc)
            return {"error": str(exc)}

        # Update cash
        notional = size * entry_price
        state = self._latest_state()
        new_cash = state["cash"] - notional
        new_invested = state["invested"] + notional
        self._save_state(
            total_equity=state["total_equity"],
            cash=new_cash,
            invested=new_invested,
            unrealized_pnl=state["unrealized_pnl"],
            realized_pnl_today=state["realized_pnl_today"],
        )

        logger.info(
            "Position opened: id=%s %s %s x%d @ %.2f  SL=%s TP=%s",
            position_id, side, ticker, size, entry_price, stop_loss, take_profit,
        )
        return {
            "position_id": position_id,
            "ticker": ticker,
            "side": side,
            "size": size,
            "entry_price": entry_price,
            "entry_date": entry_date,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "status": "open",
        }

    def close_position(self, position_id: int, exit_price: float) -> dict:
        """Close a position and calculate P&L.

        Returns:
            Dict with position details and realized P&L.
        """
        try:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT * FROM positions WHERE id = ? AND status = 'open'",
                    (position_id,),
                ).fetchone()
                if not row:
                    return {"error": f"Position {position_id} not found or already closed"}

                pos = dict(row)
                # Calculate P&L
                if pos["side"] == "long":
                    pnl = (exit_price - pos["entry_price"]) * pos["size"]
                else:  # short
                    pnl = (pos["entry_price"] - exit_price) * pos["size"]

                exit_date = datetime.now(timezone.utc).isoformat()
                conn.execute(
                    """
                    UPDATE positions
                    SET status = 'closed', exit_price = ?, exit_date = ?, pnl = ?
                    WHERE id = ?
                    """,
                    (exit_price, exit_date, pnl, position_id),
                )
                conn.commit()
        except sqlite3.Error as exc:
            logger.error("Failed to close position: %s", exc)
            return {"error": str(exc)}

        # Update portfolio state
        notional = pos["size"] * pos["entry_price"]
        state = self._latest_state()
        new_cash = state["cash"] + notional + pnl
        new_invested = state["invested"] - notional
        new_equity = new_cash + max(new_invested, 0) + state["unrealized_pnl"]
        new_realized = state["realized_pnl_today"] + pnl
        self._save_state(
            total_equity=new_equity,
            cash=new_cash,
            invested=max(new_invested, 0),
            unrealized_pnl=state["unrealized_pnl"],
            realized_pnl_today=new_realized,
        )

        logger.info(
            "Position closed: id=%s %s %s  PnL=%.2f",
            position_id, pos["side"], pos["ticker"], pnl,
        )
        return {
            "position_id": position_id,
            "ticker": pos["ticker"],
            "side": pos["side"],
            "size": pos["size"],
            "entry_price": pos["entry_price"],
            "exit_price": exit_price,
            "exit_date": exit_date,
            "pnl": round(pnl, 2),
            "status": "closed",
        }

    def get_open_positions(self) -> list[dict]:
        """Return all open positions."""
        try:
            with self._conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM positions WHERE status = 'open' ORDER BY id"
                ).fetchall()
                return [dict(r) for r in rows]
        except sqlite3.Error as exc:
            logger.error("Failed to query open positions: %s", exc)
            return []

    def get_position_by_ticker(self, ticker: str) -> dict | None:
        """Return the first open position for a given ticker, or None."""
        try:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT * FROM positions WHERE ticker = ? AND status = 'open' LIMIT 1",
                    (ticker,),
                ).fetchone()
                return dict(row) if row else None
        except sqlite3.Error as exc:
            logger.error("Failed to query position by ticker: %s", exc)
            return None

    def get_portfolio_summary(self) -> dict:
        """Return a summary of current portfolio state."""
        state = self._latest_state()
        positions = self.get_open_positions()

        # Basic sector exposure (ticker prefix grouping)
        sector_exposure: dict[str, float] = {}
        for pos in positions:
            # Use first 2 digits of ticker as a rough sector proxy
            sector_key = pos["ticker"][:2] if len(pos["ticker"]) >= 2 else pos["ticker"]
            notional = pos["size"] * pos["entry_price"]
            sector_exposure[sector_key] = sector_exposure.get(sector_key, 0) + notional

        return {
            "total_equity": state["total_equity"],
            "cash": state["cash"],
            "invested": state["invested"],
            "positions_count": len(positions),
            "sector_exposure": sector_exposure,
            "unrealized_pnl": state["unrealized_pnl"],
        }

    def update_market_prices(self, price_dict: dict[str, float]) -> None:
        """Update unrealized P&L for all open positions given current prices.

        Args:
            price_dict: Mapping of ticker -> current market price.
        """
        positions = self.get_open_positions()
        total_unrealized = 0.0

        for pos in positions:
            current_price = price_dict.get(pos["ticker"])
            if current_price is None:
                continue
            if pos["side"] == "long":
                unrealized = (current_price - pos["entry_price"]) * pos["size"]
            else:
                unrealized = (pos["entry_price"] - current_price) * pos["size"]
            total_unrealized += unrealized

        state = self._latest_state()
        new_equity = state["cash"] + state["invested"] + total_unrealized
        self._save_state(
            total_equity=new_equity,
            cash=state["cash"],
            invested=state["invested"],
            unrealized_pnl=total_unrealized,
            realized_pnl_today=state["realized_pnl_today"],
        )
        logger.info("Market prices updated: unrealized_pnl=%.2f", total_unrealized)

    def get_daily_pnl(self) -> float:
        """Return today's realized + unrealized P&L."""
        state = self._latest_state()
        return round(state["realized_pnl_today"] + state["unrealized_pnl"], 2)
