"""
Win Rate Engine — tracks and validates strategy performance in real-time.

Stores trade history in SQLite (cits/logs/trades.db) and computes:
  - Win rate
  - Profit factor
  - Sharpe ratio (simplified, annualised)
  - Max drawdown
  - Per-strategy weights based on recent performance
"""

from __future__ import annotations

import logging
import math
import sqlite3
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_DB_DIR = Path(__file__).resolve().parent.parent / "logs"
_DB_PATH = _DB_DIR / "trades.db"

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS trades (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT    NOT NULL,
    strategy    TEXT    NOT NULL DEFAULT 'default',
    symbol      TEXT    NOT NULL,
    side        TEXT    NOT NULL,
    qty         INTEGER NOT NULL,
    entry_price REAL    NOT NULL,
    exit_price  REAL    NOT NULL,
    pnl         REAL    NOT NULL,
    is_win      INTEGER NOT NULL
);
"""


class WinRateEngine:
    """Tracks trade results and validates strategy performance."""

    def __init__(
        self,
        min_trades: int = 20,
        target_win_rate: float = 0.55,
        db_path: str | Path | None = None,
    ) -> None:
        """
        Args:
            min_trades: Minimum trades required before strategy validation.
            target_win_rate: Target win rate (0.0–1.0).
            db_path: Override default SQLite path.
        """
        self.min_trades = min_trades
        self.target_win_rate = target_win_rate
        self.db_path = Path(db_path) if db_path else _DB_PATH

        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_db()

    def _init_db(self) -> None:
        """Create the trades table if it doesn't exist."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute(_CREATE_TABLE_SQL)
                conn.commit()
            logger.debug("Trade DB initialised at %s", self.db_path)
        except sqlite3.Error as exc:
            logger.error("Failed to initialise trade DB: %s", exc)

    def _conn(self) -> sqlite3.Connection:
        """Return a new connection with row factory."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------------
    # Recording trades
    # ------------------------------------------------------------------

    def record_trade(self, trade: dict) -> None:
        """
        Record a completed trade.

        Args:
            trade: Dict with keys:
              - symbol (str)
              - side (str): "buy" or "sell"
              - qty (int)
              - entry_price (float)
              - exit_price (float)
              - pnl (float)
              - strategy (str, optional): strategy name
              - timestamp (str, optional): ISO timestamp
        """
        pnl = trade.get("pnl", 0.0)
        is_win = 1 if pnl > 0 else 0
        timestamp = trade.get("timestamp", datetime.utcnow().isoformat())
        strategy = trade.get("strategy", "default")

        try:
            with self._conn() as conn:
                conn.execute(
                    """
                    INSERT INTO trades
                        (timestamp, strategy, symbol, side, qty,
                         entry_price, exit_price, pnl, is_win)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        timestamp,
                        strategy,
                        trade["symbol"],
                        trade["side"],
                        trade["qty"],
                        trade["entry_price"],
                        trade["exit_price"],
                        pnl,
                        is_win,
                    ),
                )
                conn.commit()
            logger.info(
                "Trade recorded: %s %s x%d  PnL=%.2f (%s)",
                trade["symbol"], trade["side"], trade["qty"],
                pnl, "WIN" if is_win else "LOSS",
            )
        except (sqlite3.Error, KeyError) as exc:
            logger.error("Failed to record trade: %s", exc)

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """
        Compute aggregate trading statistics.

        Returns:
            Dict with win_rate, profit_factor, sharpe_ratio, max_drawdown,
            total_trades, total_pnl.
        """
        try:
            with self._conn() as conn:
                rows = conn.execute(
                    "SELECT pnl, is_win FROM trades ORDER BY id"
                ).fetchall()
        except sqlite3.Error as exc:
            logger.error("Failed to query trades: %s", exc)
            return {
                "win_rate": 0.0, "profit_factor": 0.0,
                "sharpe_ratio": 0.0, "max_drawdown": 0.0,
                "total_trades": 0, "total_pnl": 0.0,
            }

        if not rows:
            return {
                "win_rate": 0.0, "profit_factor": 0.0,
                "sharpe_ratio": 0.0, "max_drawdown": 0.0,
                "total_trades": 0, "total_pnl": 0.0,
            }

        pnls = [r["pnl"] for r in rows]
        wins = sum(1 for r in rows if r["is_win"])
        total = len(rows)

        # Win rate
        win_rate = wins / total if total else 0.0

        # Profit factor = gross_profit / gross_loss
        gross_profit = sum(p for p in pnls if p > 0)
        gross_loss = abs(sum(p for p in pnls if p < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        # Sharpe ratio (simplified annualised, assuming ~252 trading days)
        mean_pnl = sum(pnls) / total
        if total > 1:
            variance = sum((p - mean_pnl) ** 2 for p in pnls) / (total - 1)
            std_pnl = math.sqrt(variance)
            sharpe_ratio = (mean_pnl / std_pnl) * math.sqrt(252) if std_pnl > 0 else 0.0
        else:
            sharpe_ratio = 0.0

        # Max drawdown
        cumulative = 0.0
        peak = 0.0
        max_dd = 0.0
        for p in pnls:
            cumulative += p
            if cumulative > peak:
                peak = cumulative
            dd = (peak - cumulative) / peak if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd

        return {
            "win_rate": round(win_rate, 4),
            "profit_factor": round(profit_factor, 4),
            "sharpe_ratio": round(sharpe_ratio, 4),
            "max_drawdown": round(max_dd, 4),
            "total_trades": total,
            "total_pnl": round(sum(pnls), 2),
        }

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def is_strategy_valid(self) -> dict:
        """
        Check if the current strategy meets minimum performance criteria.

        Criteria:
          - win_rate >= 55%
          - profit_factor >= 1.3
          - max_drawdown <= 10%
          - Enough trades (>= min_trades)

        Returns:
            Dict with is_valid (bool), reasons (list[str]), stats (dict).
        """
        stats = self.get_stats()
        reasons: list[str] = []
        is_valid = True

        if stats["total_trades"] < self.min_trades:
            reasons.append(
                f"Insufficient trades: {stats['total_trades']}/{self.min_trades}"
            )
            is_valid = False

        if stats["win_rate"] < self.target_win_rate:
            reasons.append(
                f"Win rate {stats['win_rate']:.1%} below target {self.target_win_rate:.1%}"
            )
            is_valid = False

        if stats["profit_factor"] < 1.3:
            reasons.append(f"Profit factor {stats['profit_factor']:.2f} below 1.30")
            is_valid = False

        if stats["max_drawdown"] > 0.10:
            reasons.append(f"Max drawdown {stats['max_drawdown']:.1%} exceeds 10%")
            is_valid = False

        if is_valid:
            logger.info("Strategy VALID: %s", stats)
        else:
            logger.warning("Strategy INVALID: %s", reasons)

        return {"is_valid": is_valid, "reasons": reasons, "stats": stats}

    # ------------------------------------------------------------------
    # Strategy weights
    # ------------------------------------------------------------------

    def get_strategy_weights(self) -> dict:
        """
        Calculate allocation weights per strategy based on recent performance.

        Uses the last 5 trades for each strategy. Strategies with higher
        win rates and profit factors get larger weights.

        Returns:
            Dict mapping strategy_name -> weight (0.0–1.0), normalised to sum=1.
        """
        try:
            with self._conn() as conn:
                strategies = conn.execute(
                    "SELECT DISTINCT strategy FROM trades"
                ).fetchall()
        except sqlite3.Error as exc:
            logger.error("Failed to query strategies: %s", exc)
            return {}

        if not strategies:
            return {}

        raw_scores: dict[str, float] = {}

        for row in strategies:
            name = row["strategy"]
            try:
                with self._conn() as conn:
                    recent = conn.execute(
                        """
                        SELECT pnl, is_win FROM trades
                        WHERE strategy = ?
                        ORDER BY id DESC LIMIT 5
                        """,
                        (name,),
                    ).fetchall()
            except sqlite3.Error:
                continue

            if not recent:
                continue

            wins = sum(1 for r in recent if r["is_win"])
            total = len(recent)
            win_rate = wins / total

            gross_profit = sum(r["pnl"] for r in recent if r["pnl"] > 0)
            gross_loss = abs(sum(r["pnl"] for r in recent if r["pnl"] < 0))
            pf = gross_profit / gross_loss if gross_loss > 0 else 2.0

            # Score = win_rate * profit_factor (simple composite)
            score = win_rate * min(pf, 5.0)  # cap PF contribution
            raw_scores[name] = max(score, 0.01)  # floor to avoid zero weight

        # Normalise
        total_score = sum(raw_scores.values())
        if total_score <= 0:
            return {k: 1.0 / len(raw_scores) for k in raw_scores}

        return {k: round(v / total_score, 4) for k, v in raw_scores.items()}
