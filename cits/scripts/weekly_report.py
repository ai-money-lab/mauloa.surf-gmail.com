"""Generate a weekly performance report from trades.db.

Usage:
    python -m cits.scripts.weekly_report
"""

from __future__ import annotations

import logging
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("cits.scripts.weekly_report")

_DB_PATH = Path(__file__).resolve().parent.parent / "logs" / "trades.db"
_REPORTS_DIR = Path(__file__).resolve().parent.parent / "logs" / "reports"


def _get_per_strategy_breakdown(db_path: Path) -> dict[str, dict]:
    """Query per-strategy stats from the trades database."""
    breakdown: dict[str, dict] = {}
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        strategies = conn.execute(
            "SELECT DISTINCT strategy FROM trades"
        ).fetchall()

        for row in strategies:
            name = row["strategy"]
            trades = conn.execute(
                "SELECT pnl, is_win FROM trades WHERE strategy = ? ORDER BY id",
                (name,),
            ).fetchall()

            if not trades:
                continue

            total = len(trades)
            wins = sum(1 for t in trades if t["is_win"])
            pnls = [t["pnl"] for t in trades]
            gross_profit = sum(p for p in pnls if p > 0)
            gross_loss = abs(sum(p for p in pnls if p < 0))
            pf = gross_profit / gross_loss if gross_loss > 0 else float("inf")

            breakdown[name] = {
                "trades": total,
                "wins": wins,
                "win_rate": round(wins / total, 4) if total else 0.0,
                "total_pnl": round(sum(pnls), 2),
                "profit_factor": round(pf, 4),
            }

        conn.close()
    except sqlite3.Error as exc:
        logger.error("Failed to query per-strategy stats: %s", exc)

    return breakdown


def generate_report() -> str:
    """Generate a formatted weekly performance report.

    Returns
    -------
    str
        The full text of the report.
    """
    from cits.risk.win_rate_engine import WinRateEngine

    engine = WinRateEngine(db_path=_DB_PATH)
    stats = engine.get_stats()
    breakdown = _get_per_strategy_breakdown(_DB_PATH)

    today = datetime.now().strftime("%Y-%m-%d")

    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("CITS Weekly Performance Report")
    lines.append(f"Generated: {today}")
    lines.append("=" * 60)
    lines.append("")
    lines.append("--- Aggregate Statistics ---")
    lines.append(f"  Total Trades:   {stats['total_trades']}")
    lines.append(f"  Win Rate:       {stats['win_rate']:.2%}")
    lines.append(f"  Profit Factor:  {stats['profit_factor']:.4f}")
    lines.append(f"  Sharpe Ratio:   {stats['sharpe_ratio']:.4f}")
    lines.append(f"  Max Drawdown:   {stats['max_drawdown']:.2%}")
    lines.append(f"  Total PnL:      {stats['total_pnl']:,.2f}")
    lines.append("")

    if breakdown:
        lines.append("--- Per-Strategy Breakdown ---")
        for name, s in sorted(breakdown.items()):
            lines.append(f"  [{name}]")
            lines.append(f"    Trades:        {s['trades']}")
            lines.append(f"    Wins:          {s['wins']}")
            lines.append(f"    Win Rate:      {s['win_rate']:.2%}")
            lines.append(f"    Profit Factor: {s['profit_factor']:.4f}")
            lines.append(f"    Total PnL:     {s['total_pnl']:,.2f}")
            lines.append("")
    else:
        lines.append("(No per-strategy data available)")
        lines.append("")

    # Validation
    validation = engine.is_strategy_valid()
    lines.append("--- Strategy Validation ---")
    lines.append(f"  Valid: {validation['is_valid']}")
    if validation["reasons"]:
        for reason in validation["reasons"]:
            lines.append(f"    - {reason}")
    lines.append("")
    lines.append("=" * 60)

    report = "\n".join(lines)
    return report


def save_report(report: str) -> Path:
    """Save the report to cits/logs/reports/weekly_YYYY-MM-DD.txt."""
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    report_path = _REPORTS_DIR / f"weekly_{today}.txt"
    report_path.write_text(report, encoding="utf-8")
    logger.info("Report saved to %s", report_path)
    return report_path


def main() -> None:
    """CLI entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    report = generate_report()
    print(report)
    path = save_report(report)
    print(f"\nReport saved to: {path}")


if __name__ == "__main__":
    main()
