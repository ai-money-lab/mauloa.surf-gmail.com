"""Signal Tracker — records predictions and verifies against actual results.

The core principle: "今日立てた予想が今日のチャートに反映されてたか？"
Each signal is recorded with its prediction BEFORE the outcome is known,
then verified after market close.  Win rates are computed per signal.

Schema
------
signals table:
    date, signal_name, predicted_direction (+1/-1/0),
    confidence (0.0-1.0), actual_return (filled after close),
    is_win (filled after close)
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_DB_DIR = Path(__file__).resolve().parent.parent / "logs"
_DB_PATH = _DB_DIR / "signals.db"

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS signals (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    date                TEXT    NOT NULL,
    timestamp           TEXT    NOT NULL,
    signal_name         TEXT    NOT NULL,
    predicted_direction INTEGER NOT NULL,  -- +1=bullish, -1=bearish, 0=neutral
    confidence          REAL    NOT NULL DEFAULT 0.5,
    context_json        TEXT,              -- raw signal data for audit
    actual_return       REAL,              -- filled after close
    is_win              INTEGER,           -- filled after close
    UNIQUE(date, signal_name)
);
"""


class SignalTracker:
    """Records pre-market predictions and verifies them against actual results."""

    # Minimum signals required before a signal is considered validated
    MIN_SIGNALS_FOR_VALIDATION = 20

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else _DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute(_CREATE_TABLE_SQL)
                conn.commit()
            logger.debug("Signal DB initialised at %s", self.db_path)
        except sqlite3.Error as exc:
            logger.error("Failed to initialise signal DB: %s", exc)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_prediction(
        self,
        signal_name: str,
        predicted_direction: int,
        confidence: float = 0.5,
        context: str = "",
        date: str | None = None,
    ) -> None:
        """Record a signal prediction BEFORE the outcome is known.

        Args:
            signal_name: e.g. "intraday_momentum", "orb_60", "overnight_reversal"
            predicted_direction: +1 (bullish), -1 (bearish), 0 (neutral)
            confidence: 0.0 to 1.0
            context: JSON string with raw signal data for audit trail
            date: ISO date string (defaults to today)
        """
        date = date or datetime.now().strftime("%Y-%m-%d")
        timestamp = datetime.now().isoformat()

        try:
            with self._conn() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO signals
                        (date, timestamp, signal_name, predicted_direction,
                         confidence, context_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (date, timestamp, signal_name, predicted_direction,
                     confidence, context),
                )
                conn.commit()
            logger.info(
                "Signal recorded: %s direction=%+d confidence=%.2f date=%s",
                signal_name, predicted_direction, confidence, date,
            )
        except sqlite3.Error as exc:
            logger.error("Failed to record signal: %s", exc)

    def verify_prediction(
        self,
        signal_name: str,
        actual_return: float,
        date: str | None = None,
    ) -> dict:
        """Verify a prediction against the actual return after market close.

        Args:
            signal_name: Must match a previously recorded prediction
            actual_return: Actual percentage return for the period
            date: ISO date string (defaults to today)

        Returns:
            Dict with is_win, predicted_direction, actual_return
        """
        date = date or datetime.now().strftime("%Y-%m-%d")

        try:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT predicted_direction FROM signals WHERE date=? AND signal_name=?",
                    (date, signal_name),
                ).fetchone()

                if not row:
                    logger.warning("No prediction found for %s on %s", signal_name, date)
                    return {"error": "no_prediction"}

                predicted = row["predicted_direction"]

                # Win if direction matches (or neutral prediction with near-zero return)
                if predicted == 0:
                    is_win = 1 if abs(actual_return) < 0.1 else 0
                else:
                    is_win = 1 if (predicted > 0 and actual_return > 0) or \
                                  (predicted < 0 and actual_return < 0) else 0

                conn.execute(
                    """
                    UPDATE signals SET actual_return=?, is_win=?
                    WHERE date=? AND signal_name=?
                    """,
                    (actual_return, is_win, date, signal_name),
                )
                conn.commit()

            result = {
                "signal_name": signal_name,
                "date": date,
                "predicted_direction": predicted,
                "actual_return": actual_return,
                "is_win": bool(is_win),
            }
            logger.info(
                "Signal verified: %s %s (predicted=%+d actual=%.2f%%)",
                signal_name, "WIN" if is_win else "LOSS", predicted, actual_return,
            )
            return result

        except sqlite3.Error as exc:
            logger.error("Failed to verify signal: %s", exc)
            return {"error": str(exc)}

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_signal_stats(self, signal_name: str | None = None) -> list[dict]:
        """Get win rate statistics per signal (or for a specific signal).

        Returns:
            List of dicts with signal_name, total, wins, win_rate,
            avg_confidence, avg_return, profit_factor.
        """
        try:
            with self._conn() as conn:
                if signal_name:
                    rows = conn.execute(
                        """
                        SELECT signal_name,
                               COUNT(*) as total,
                               SUM(CASE WHEN is_win=1 THEN 1 ELSE 0 END) as wins,
                               AVG(confidence) as avg_confidence,
                               AVG(actual_return) as avg_return,
                               SUM(CASE WHEN actual_return > 0 THEN actual_return ELSE 0 END) as gross_profit,
                               ABS(SUM(CASE WHEN actual_return < 0 THEN actual_return ELSE 0 END)) as gross_loss
                        FROM signals
                        WHERE signal_name=? AND is_win IS NOT NULL
                        GROUP BY signal_name
                        """,
                        (signal_name,),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT signal_name,
                               COUNT(*) as total,
                               SUM(CASE WHEN is_win=1 THEN 1 ELSE 0 END) as wins,
                               AVG(confidence) as avg_confidence,
                               AVG(actual_return) as avg_return,
                               SUM(CASE WHEN actual_return > 0 THEN actual_return ELSE 0 END) as gross_profit,
                               ABS(SUM(CASE WHEN actual_return < 0 THEN actual_return ELSE 0 END)) as gross_loss
                        FROM signals
                        WHERE is_win IS NOT NULL
                        GROUP BY signal_name
                        ORDER BY wins * 1.0 / COUNT(*) DESC
                        """,
                    ).fetchall()
        except sqlite3.Error as exc:
            logger.error("Failed to query signal stats: %s", exc)
            return []

        results = []
        for r in rows:
            total = r["total"]
            wins = r["wins"]
            gross_profit = r["gross_profit"] or 0.0
            gross_loss = r["gross_loss"] or 0.0

            results.append({
                "signal_name": r["signal_name"],
                "total": total,
                "wins": wins,
                "win_rate": round(wins / total, 4) if total else 0.0,
                "avg_confidence": round(r["avg_confidence"] or 0, 4),
                "avg_return": round(r["avg_return"] or 0, 4),
                "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss > 0 else float("inf"),
                "is_validated": total >= self.MIN_SIGNALS_FOR_VALIDATION,
            })

        return results

    def get_active_signals(self) -> list[str]:
        """Return signal names with win_rate >= 55% and enough data."""
        stats = self.get_signal_stats()
        return [
            s["signal_name"] for s in stats
            if s["is_validated"] and s["win_rate"] >= 0.55
        ]

    def get_disabled_signals(self) -> list[str]:
        """Return signal names with win_rate < 55% (validated but underperforming)."""
        stats = self.get_signal_stats()
        return [
            s["signal_name"] for s in stats
            if s["is_validated"] and s["win_rate"] < 0.55
        ]
