"""CITS ポートフォリオ監視ダッシュボード — CLI版.

SQLite データベースから直接読み取り、フォーマット済みレポートを表示する。

Usage:
    python -m cits.scripts.dashboard            # コンパクト概要
    python -m cits.scripts.dashboard --full      # 全セクション表示
    python -m cits.scripts.dashboard --trades    # 取引履歴
    python -m cits.scripts.dashboard --signals   # シグナル成績
"""

from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

_LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"
_PORTFOLIO_DB = _LOGS_DIR / "portfolio.db"
_TRADES_DB = _LOGS_DIR / "trades.db"
_SIGNALS_DB = _LOGS_DIR / "signals.db"

_NO_DATA = "データなし"
_SEP_HEAVY = "=" * 68
_SEP_LIGHT = "-" * 68


# ------------------------------------------------------------------
# Formatting helpers
# ------------------------------------------------------------------

def _yen(value: float) -> str:
    """Format a number as Japanese yen with comma separators."""
    if value < 0:
        return f"-¥{abs(value):,.0f}"
    return f"¥{value:,.0f}"


def _pct(value: float) -> str:
    """Format a float ratio (0.55) as a percentage string (55.00%)."""
    return f"{value:.2%}"


def _pnl_color(value: float) -> str:
    """Return the PnL value with a directional marker."""
    if value > 0:
        return f"+{_yen(value)}"
    return _yen(value)


def _safe_conn(db_path: Path) -> sqlite3.Connection | None:
    """Open a read-only SQLite connection if the database file exists."""
    if not db_path.exists():
        return None
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error:
        return None


# ------------------------------------------------------------------
# 1. Portfolio Summary
# ------------------------------------------------------------------

def _portfolio_summary() -> list[str]:
    lines: list[str] = []
    lines.append("")
    lines.append("  【ポートフォリオ概要】")
    lines.append(_SEP_LIGHT)

    conn = _safe_conn(_PORTFOLIO_DB)
    if conn is None:
        lines.append(f"  {_NO_DATA} (portfolio.db が見つかりません)")
        return lines

    try:
        # Latest state
        row = conn.execute(
            "SELECT * FROM portfolio_state ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row is None:
            lines.append(f"  {_NO_DATA}")
            conn.close()
            return lines

        state = dict(row)
        lines.append(f"  総資産:         {_yen(state['total_equity'])}")
        lines.append(f"  現金:           {_yen(state['cash'])}")
        lines.append(f"  投資額:         {_yen(state['invested'])}")
        lines.append(f"  含み損益:       {_pnl_color(state['unrealized_pnl'])}")
        lines.append(f"  本日確定損益:   {_pnl_color(state['realized_pnl_today'])}")

        # Open positions
        positions = conn.execute(
            "SELECT * FROM positions WHERE status = 'open' ORDER BY id"
        ).fetchall()

        lines.append("")
        if positions:
            lines.append(f"  【建玉一覧】 ({len(positions)}件)")
            lines.append(
                f"  {'銘柄':<8} {'方向':<6} {'数量':>6} "
                f"{'建値':>10} {'SL':>10} {'TP':>10}"
            )
            lines.append(f"  {'─' * 58}")
            for p in positions:
                pos = dict(p)
                sl_str = _yen(pos["stop_loss"]) if pos["stop_loss"] else "---"
                tp_str = _yen(pos["take_profit"]) if pos["take_profit"] else "---"
                side_jp = "買" if pos["side"] == "long" else "売"
                lines.append(
                    f"  {pos['ticker']:<8} {side_jp:<6} {pos['size']:>6,} "
                    f"{_yen(pos['entry_price']):>10} {sl_str:>10} {tp_str:>10}"
                )
        else:
            lines.append("  建玉なし")

        conn.close()
    except sqlite3.Error as exc:
        lines.append(f"  読み取りエラー: {exc}")

    return lines


# ------------------------------------------------------------------
# 2. Trading Performance
# ------------------------------------------------------------------

def _trading_performance(show_trades: bool = False) -> list[str]:
    lines: list[str] = []
    lines.append("")
    lines.append("  【トレード成績】")
    lines.append(_SEP_LIGHT)

    conn = _safe_conn(_TRADES_DB)
    if conn is None:
        lines.append(f"  {_NO_DATA} (trades.db が見つかりません)")
        return lines

    try:
        # Aggregate stats
        rows = conn.execute(
            "SELECT pnl, is_win FROM trades ORDER BY id"
        ).fetchall()

        if not rows:
            lines.append(f"  {_NO_DATA} (トレード記録なし)")
            conn.close()
            return lines

        pnls = [r["pnl"] for r in rows]
        total = len(rows)
        wins = sum(1 for r in rows if r["is_win"])
        win_rate = wins / total if total else 0.0
        gross_profit = sum(p for p in pnls if p > 0)
        gross_loss = abs(sum(p for p in pnls if p < 0))
        pf = gross_profit / gross_loss if gross_loss > 0 else float("inf")

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

        # Sharpe (simplified)
        import math

        mean_pnl = sum(pnls) / total
        if total > 1:
            variance = sum((p - mean_pnl) ** 2 for p in pnls) / (total - 1)
            std_pnl = math.sqrt(variance)
            sharpe = (mean_pnl / std_pnl) * math.sqrt(252) if std_pnl > 0 else 0.0
        else:
            sharpe = 0.0

        lines.append(f"  総トレード数:   {total}")
        lines.append(f"  勝率:           {_pct(win_rate)} ({wins}勝 / {total - wins}敗)")
        lines.append(f"  プロフィット:   {pf:.2f}")
        lines.append(f"  シャープ比:     {sharpe:.2f}")
        lines.append(f"  最大DD:         {_pct(max_dd)}")
        lines.append(f"  合計損益:       {_pnl_color(sum(pnls))}")

        # Per-strategy breakdown
        strategies = conn.execute(
            "SELECT DISTINCT strategy FROM trades"
        ).fetchall()

        if strategies:
            lines.append("")
            lines.append("  【戦略別成績】")
            lines.append(
                f"  {'戦略':<24} {'勝率':>8} {'PF':>8} "
                f"{'損益':>14} {'件数':>6}"
            )
            lines.append(f"  {'─' * 62}")
            for srow in strategies:
                name = srow["strategy"]
                st = conn.execute(
                    "SELECT pnl, is_win FROM trades WHERE strategy = ?",
                    (name,),
                ).fetchall()
                s_total = len(st)
                s_wins = sum(1 for t in st if t["is_win"])
                s_pnls = [t["pnl"] for t in st]
                s_wr = s_wins / s_total if s_total else 0.0
                s_gp = sum(p for p in s_pnls if p > 0)
                s_gl = abs(sum(p for p in s_pnls if p < 0))
                s_pf = s_gp / s_gl if s_gl > 0 else float("inf")
                lines.append(
                    f"  {name:<24} {_pct(s_wr):>8} {s_pf:>8.2f} "
                    f"{_pnl_color(sum(s_pnls)):>14} {s_total:>6}"
                )

        # Last 10 trades
        if show_trades:
            recent = conn.execute(
                "SELECT * FROM trades ORDER BY id DESC LIMIT 10"
            ).fetchall()
            if recent:
                lines.append("")
                lines.append("  【直近10件のトレード】")
                lines.append(
                    f"  {'日時':<20} {'銘柄':<8} {'方向':<6} "
                    f"{'数量':>6} {'損益':>12} {'結果':>6}"
                )
                lines.append(f"  {'─' * 62}")
                for t in recent:
                    td = dict(t)
                    ts = td["timestamp"][:16] if td["timestamp"] else "---"
                    result = "勝" if td["is_win"] else "負"
                    lines.append(
                        f"  {ts:<20} {td['symbol']:<8} {td['side']:<6} "
                        f"{td['qty']:>6,} {_pnl_color(td['pnl']):>12} {result:>6}"
                    )

        conn.close()
    except sqlite3.Error as exc:
        lines.append(f"  読み取りエラー: {exc}")

    return lines


# ------------------------------------------------------------------
# 3. Signal Performance
# ------------------------------------------------------------------

def _signal_performance() -> list[str]:
    lines: list[str] = []
    lines.append("")
    lines.append("  【シグナル成績】")
    lines.append(_SEP_LIGHT)

    conn = _safe_conn(_SIGNALS_DB)
    if conn is None:
        lines.append(f"  {_NO_DATA} (signals.db が見つかりません)")
        return lines

    try:
        rows = conn.execute(
            """
            SELECT signal_name,
                   COUNT(*) as total,
                   SUM(CASE WHEN is_win = 1 THEN 1 ELSE 0 END) as wins,
                   AVG(confidence) as avg_conf,
                   AVG(actual_return) as avg_ret,
                   SUM(CASE WHEN actual_return > 0 THEN actual_return ELSE 0 END) as gp,
                   ABS(SUM(CASE WHEN actual_return < 0 THEN actual_return ELSE 0 END)) as gl
            FROM signals
            WHERE is_win IS NOT NULL
            GROUP BY signal_name
            ORDER BY wins * 1.0 / COUNT(*) DESC
            """
        ).fetchall()

        if not rows:
            lines.append(f"  {_NO_DATA} (検証済みシグナルなし)")
            conn.close()
            return lines

        # Count pending (unverified) signals
        pending = conn.execute(
            "SELECT COUNT(*) as cnt FROM signals WHERE is_win IS NULL"
        ).fetchone()
        pending_cnt = pending["cnt"] if pending else 0

        min_validated = 20
        active = []
        disabled = []
        for r in rows:
            wr = r["wins"] / r["total"] if r["total"] else 0.0
            validated = r["total"] >= min_validated
            if validated and wr >= 0.55:
                active.append(r["signal_name"])
            elif validated:
                disabled.append(r["signal_name"])

        lines.append(
            f"  有効シグナル:   {len(active)}件  "
            f"無効シグナル: {len(disabled)}件  "
            f"未検証: {pending_cnt}件"
        )
        lines.append("")
        lines.append(
            f"  {'シグナル名':<24} {'勝率':>8} {'PF':>8} "
            f"{'平均リターン':>12} {'件数':>6} {'状態':>8}"
        )
        lines.append(f"  {'─' * 68}")
        for r in rows:
            total = r["total"]
            wins_count = r["wins"]
            wr = wins_count / total if total else 0.0
            gp = r["gp"] or 0.0
            gl = r["gl"] or 0.0
            pf = gp / gl if gl > 0 else float("inf")
            avg_ret = r["avg_ret"] or 0.0
            validated = total >= min_validated
            if validated and wr >= 0.55:
                status = "有効"
            elif validated:
                status = "無効"
            else:
                status = "検証中"
            lines.append(
                f"  {r['signal_name']:<24} {_pct(wr):>8} {pf:>8.2f} "
                f"{avg_ret:>11.4f}% {total:>6} {status:>8}"
            )

        conn.close()
    except sqlite3.Error as exc:
        lines.append(f"  読み取りエラー: {exc}")

    return lines


# ------------------------------------------------------------------
# 4. Risk Status
# ------------------------------------------------------------------

def _risk_status() -> list[str]:
    lines: list[str] = []
    lines.append("")
    lines.append("  【リスク状況】")
    lines.append(_SEP_LIGHT)

    # Read circuit breaker state from portfolio and trades
    portfolio_conn = _safe_conn(_PORTFOLIO_DB)
    trades_conn = _safe_conn(_TRADES_DB)

    daily_pnl = 0.0
    consecutive_losses = 0
    daily_trade_count = 0

    if portfolio_conn:
        try:
            row = portfolio_conn.execute(
                "SELECT * FROM portfolio_state ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if row:
                state = dict(row)
                daily_pnl = state.get("realized_pnl_today", 0.0) + state.get(
                    "unrealized_pnl", 0.0
                )
            portfolio_conn.close()
        except sqlite3.Error:
            pass

    if trades_conn:
        try:
            today_str = datetime.now().strftime("%Y-%m-%d")
            row = trades_conn.execute(
                "SELECT COUNT(*) as cnt FROM trades WHERE timestamp LIKE ?",
                (f"{today_str}%",),
            ).fetchone()
            daily_trade_count = row["cnt"] if row else 0

            # Consecutive losses from tail
            recent = trades_conn.execute(
                "SELECT is_win FROM trades ORDER BY id DESC LIMIT 20"
            ).fetchall()
            for r in recent:
                if r["is_win"]:
                    break
                consecutive_losses += 1

            trades_conn.close()
        except sqlite3.Error:
            pass

    # Evaluate circuit breaker rules (inline, no instantiation needed)
    max_daily_loss = 50_000
    max_consec = 3
    max_trades = 10

    cb_triggered = False
    cb_reasons: list[str] = []

    if daily_pnl <= -abs(max_daily_loss):
        cb_triggered = True
        cb_reasons.append(
            f"日次損失 {_yen(abs(daily_pnl))} が上限 {_yen(max_daily_loss)} 超過"
        )
    if consecutive_losses >= max_consec:
        cb_triggered = True
        cb_reasons.append(f"連敗 {consecutive_losses}回 (上限: {max_consec})")
    if daily_trade_count >= max_trades:
        cb_triggered = True
        cb_reasons.append(
            f"本日取引 {daily_trade_count}件 (上限: {max_trades})"
        )

    if cb_triggered:
        lines.append("  サーキットブレーカー: *** 発動中 ***")
        for reason in cb_reasons:
            lines.append(f"    理由: {reason}")
    else:
        lines.append("  サーキットブレーカー: 正常")

    lines.append(f"  本日損益:       {_pnl_color(daily_pnl)}")
    lines.append(f"  連敗数:         {consecutive_losses}")
    lines.append(f"  本日取引数:     {daily_trade_count}")

    # Regime assessment (simple heuristic based on drawdown / PnL)
    if daily_pnl <= -abs(max_daily_loss):
        regime = "危険 (大幅損失)"
    elif consecutive_losses >= 2:
        regime = "注意 (連敗中)"
    elif daily_pnl > 0:
        regime = "良好 (利益確保)"
    else:
        regime = "通常"

    lines.append(f"  相場判定:       {regime}")

    return lines


# ------------------------------------------------------------------
# Main renderer
# ------------------------------------------------------------------

def render_dashboard(
    *,
    full: bool = False,
    show_trades: bool = False,
    show_signals: bool = False,
) -> str:
    """Render the complete dashboard text.

    Args:
        full: Show all sections including trade history and signal details.
        show_trades: Show last 10 trades detail.
        show_signals: Show signal performance section.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    out: list[str] = []
    out.append("")
    out.append(_SEP_HEAVY)
    out.append("  CITS ポートフォリオ監視ダッシュボード")
    out.append(f"  生成日時: {now}")
    out.append(_SEP_HEAVY)

    # Always show portfolio summary and risk
    out.extend(_portfolio_summary())
    out.extend(_risk_status())

    # Trading performance (always show summary; trades detail on request)
    out.extend(_trading_performance(show_trades=full or show_trades))

    # Signal performance
    if full or show_signals:
        out.extend(_signal_performance())

    out.append("")
    out.append(_SEP_HEAVY)
    out.append("")

    return "\n".join(out)


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def main() -> None:
    """CLI entry point for the dashboard."""
    parser = argparse.ArgumentParser(
        prog="cits.scripts.dashboard",
        description="CITS ポートフォリオ監視ダッシュボード",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="全セクション表示（トレード履歴・シグナル成績含む）",
    )
    parser.add_argument(
        "--trades",
        action="store_true",
        help="直近トレード履歴を表示",
    )
    parser.add_argument(
        "--signals",
        action="store_true",
        help="シグナル成績を表示",
    )

    args = parser.parse_args()

    output = render_dashboard(
        full=args.full,
        show_trades=args.trades,
        show_signals=args.signals,
    )
    print(output)


if __name__ == "__main__":
    main()
