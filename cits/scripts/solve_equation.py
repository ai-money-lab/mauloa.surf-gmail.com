"""CITS Success Equation Solver

月利5%複利の成功方程式を解く。
全パラメータを網羅的に分析し、月次安定リターンを最大化する設定を特定する。

Usage:
    python3 -m cits.scripts.solve_equation --capital 100000
"""

from __future__ import annotations

import argparse
import itertools
import logging
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

import pandas as pd
import yfinance as yf

from cits.core.signals.candlestick_patterns import analyze_candlesticks
from cits.core.signals.chart_formations import analyze_formations
from cits.core.signals.mean_reversion import compute_mean_reversion
from cits.core.signals.support_resistance import analyze_support_resistance

logging.basicConfig(level=logging.WARNING)

# ---------------------------------------------------------------
# ETFs (curated for mean reversion)
# ---------------------------------------------------------------
TICKERS = [
    "1357",  # 日経ダブルインバース
    "2558",  # S&P500連動ETF
    "1570",  # 日経レバレッジ2倍
    "1540",  # 金ETF
    "1489",  # 日経高配当50 ETF
    "1321",  # 日経225 ETF
    "1306",  # TOPIX ETF
    "2644",  # 半導体ETF
    "1343",  # REIT ETF
]

# ---------------------------------------------------------------
# Parameter grid (focused on monthly consistency)
# ---------------------------------------------------------------
GRID = {
    "mr_entry_z": [1.0, 1.5, 2.0],
    "mr_period": [5, 10, 20],
    "trend_align": [True, False],
    "require_candle_confirm": [True],        # ローソク足確認ON固定（実証済み）
    "require_sr_confirm": [True],            # S/R確認ON固定（実証済み）
    "require_formation": [False],
    "hold_days": [3, 5, 10],               # スイング保持日数
    "target_pct": [2.0, 3.0, 5.0],         # 利確ターゲット%
    "stop_pct": [1.5, 2.0],
    "risk_pct": [0.03, 0.05],
}


# ---------------------------------------------------------------
# Data
# ---------------------------------------------------------------
def fetch_data() -> dict[str, pd.DataFrame]:
    end = date.today()
    start = end - timedelta(days=500)
    data = {}
    symbols = [f"{t}.T" for t in TICKERS] + ["^VIX", "USDJPY=X", "^N225"]
    print("データ取得中...")
    for s in symbols:
        key = s.replace(".T", "") if s.endswith(".T") else s
        try:
            df = yf.download(s, start=str(start), end=str(end),
                             auto_adjust=True, progress=False)
            if df is not None and not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                data[key] = df
                print(f"  {key}: {len(df)}行")
        except Exception as e:
            print(f"  {key}: エラー {e}")
    return data


# ---------------------------------------------------------------
# Single backtest
# ---------------------------------------------------------------
@dataclass
class Trade:
    ticker: str
    date: str
    direction: int
    entry: float
    exit: float
    size: int
    pnl: float


@dataclass
class Result:
    params: dict
    trades: list[Trade] = field(default_factory=list)
    monthly_pnl: dict[str, float] = field(default_factory=dict)

    @property
    def total_pnl(self) -> float:
        return sum(t.pnl for t in self.trades)

    @property
    def trade_count(self) -> int:
        return len(self.trades)

    @property
    def win_rate(self) -> float:
        if not self.trades:
            return 0
        return sum(1 for t in self.trades if t.pnl > 0) / len(self.trades) * 100

    @property
    def profit_factor(self) -> float:
        gross_win = sum(t.pnl for t in self.trades if t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in self.trades if t.pnl < 0))
        return gross_win / gross_loss if gross_loss > 0 else float("inf")

    @property
    def avg_monthly_return_pct(self) -> float:
        if not self.monthly_pnl:
            return 0
        cap = self.params.get("capital", 100_000)
        returns = [v / cap * 100 for v in self.monthly_pnl.values()]
        return statistics.mean(returns) if returns else 0

    @property
    def monthly_win_rate(self) -> float:
        if not self.monthly_pnl:
            return 0
        wins = sum(1 for v in self.monthly_pnl.values() if v > 0)
        return wins / len(self.monthly_pnl) * 100

    @property
    def worst_month_pct(self) -> float:
        if not self.monthly_pnl:
            return 0
        cap = self.params.get("capital", 100_000)
        return min(v / cap * 100 for v in self.monthly_pnl.values())

    @property
    def consistency_score(self) -> float:
        """Higher = more consistent monthly returns."""
        if len(self.monthly_pnl) < 3:
            return 0
        cap = self.params.get("capital", 100_000)
        returns = [v / cap * 100 for v in self.monthly_pnl.values()]
        mean_r = statistics.mean(returns)
        if mean_r <= 0:
            return 0
        std_r = statistics.stdev(returns) if len(returns) > 1 else 1
        # Sharpe-like: mean / std, penalize negative months
        neg_months = sum(1 for r in returns if r < 0)
        penalty = 1 - (neg_months / len(returns)) * 0.5
        return (mean_r / (std_r + 0.01)) * penalty * (self.trade_count ** 0.3)


def run_backtest(params: dict, data: dict, capital: float) -> Result:
    cost_bps = 6.5 / 10000  # slippage + spread
    lot_size = 1 if capital < 500_000 else 100
    equity = capital
    result = Result(params={**params, "capital": capital})
    closes_history: dict[str, list] = defaultdict(list)
    volumes_history: dict[str, list] = defaultdict(list)

    for ticker in TICKERS:
        df = data.get(ticker)
        if df is None:
            continue

        dates = sorted(df.index)
        closes_history[ticker] = []
        volumes_history[ticker] = []
        opens_history: list[float] = []
        highs_history: list[float] = []
        lows_history: list[float] = []

        for i in range(1, len(dates)):
            dt = dates[i]
            prev_dt = dates[i - 1]
            row = df.loc[dt]
            prev_row = df.loc[prev_dt]

            open_p = float(row["Open"])
            high_p = float(row["High"])
            low_p = float(row["Low"])
            close_p = float(row["Close"])
            prev_close = float(prev_row["Close"])
            volume = float(row.get("Volume", 0))

            closes_history[ticker].append(prev_close)
            volumes_history[ticker].append(volume)
            opens_history.append(open_p)
            highs_history.append(high_p)
            lows_history.append(low_p)

            if open_p <= 0 or close_p <= 0 or prev_close <= 0:
                continue

            closes_list = closes_history[ticker]

            # === STEP 1: Mean Reversion signal (base signal) ===
            mr_period = params["mr_period"]
            mr_entry_z = params["mr_entry_z"]

            mr_signal = compute_mean_reversion(
                closes_list, period=mr_period, entry_z=mr_entry_z,
            )
            if mr_signal.direction == 0 or mr_signal.confidence < 0.3:
                continue

            d = mr_signal.direction

            # === STEP 2: Trend align filter ===
            if params.get("trend_align", False):
                if len(closes_list) >= 3:
                    prev2 = closes_list[-3]
                    prev1 = closes_list[-2]
                    curr = closes_list[-1]
                    if d > 0:
                        if not (curr > prev1 or prev1 > prev2):
                            continue
                    else:
                        if not (curr < prev1 or prev1 < prev2):
                            continue

            # === STEP 3: Candlestick pattern confirmation ===
            if params.get("require_candle_confirm", False):
                if len(opens_history) >= 5:
                    candle = analyze_candlesticks(
                        opens_history[-5:], highs_history[-5:],
                        lows_history[-5:], closes_list[-5:],
                    )
                    # Candle pattern must agree with MR direction
                    if candle.signal_direction != 0 and candle.signal_direction != d:
                        continue

            # === STEP 4: Support/Resistance confirmation ===
            if params.get("require_sr_confirm", False):
                if len(closes_list) >= 20:
                    sr = analyze_support_resistance(
                        closes_list[-50:] if len(closes_list) >= 50 else closes_list,
                        highs_history[-50:] if len(highs_history) >= 50 else highs_history,
                        lows_history[-50:] if len(lows_history) >= 50 else lows_history,
                    )
                    # Buy only near support, sell only near resistance
                    if d > 0 and sr.position not in ("near_support", "mid_range"):
                        continue
                    if d < 0 and sr.position not in ("near_resistance", "mid_range"):
                        continue

            # === STEP 5: Chart formation confirmation ===
            if params.get("require_formation", False):
                if len(closes_list) >= 20:
                    formation = analyze_formations(
                        closes_list[-30:] if len(closes_list) >= 30 else closes_list,
                        highs_history[-30:] if len(highs_history) >= 30 else highs_history,
                        lows_history[-30:] if len(lows_history) >= 30 else lows_history,
                    )
                    # Formation must agree with direction
                    if formation.signal_direction != 0 and formation.signal_direction != d:
                        continue

            # Position sizing
            risk_amt = equity * params["risk_pct"]
            stop_dist = open_p * params["stop_pct"] / 100
            if stop_dist <= 0:
                continue
            raw_size = int(risk_amt / stop_dist)
            size = max(raw_size // lot_size * lot_size, lot_size)
            notional = size * open_p
            if notional > equity * 0.9:
                size = max(int(equity * 0.9 / open_p / lot_size) * lot_size, lot_size)
                notional = size * open_p
            if notional > equity:
                continue

            # === SWING TRADE: hold for N days, exit at target or stop ===
            entry_price = open_p * (1 + cost_bps) if d > 0 else open_p * (1 - cost_bps)
            target_pct = params.get("target_pct", 3.0)
            target_price = entry_price * (1 + target_pct / 100) if d > 0 \
                else entry_price * (1 - target_pct / 100)
            stop_price = entry_price * (1 - params["stop_pct"] / 100) if d > 0 \
                else entry_price * (1 + params["stop_pct"] / 100)

            max_hold = params.get("hold_days", 5)
            exit_price = None

            for j in range(i, min(i + max_hold, len(dates))):
                future_row = df.loc[dates[j]]
                f_high = float(future_row["High"])
                f_low = float(future_row["Low"])

                if d > 0:  # Long
                    if f_low <= stop_price:
                        exit_price = stop_price
                        break
                    if f_high >= target_price:
                        exit_price = target_price
                        break
                else:  # Short
                    if f_high >= stop_price:
                        exit_price = stop_price
                        break
                    if f_low <= target_price:
                        exit_price = target_price
                        break

            if exit_price is None:
                last_idx = min(i + max_hold - 1, len(dates) - 1)
                last_close = float(df.loc[dates[last_idx]]["Close"])
                exit_price = last_close * (1 - cost_bps) if d > 0 \
                    else last_close * (1 + cost_bps)

            pnl = (exit_price - entry_price) * size if d > 0 \
                else (entry_price - exit_price) * size

            trade_date = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)
            result.trades.append(Trade(ticker, trade_date, d, entry_price, exit_price, size, pnl))
            equity += pnl

            month = trade_date[:7]
            result.monthly_pnl[month] = result.monthly_pnl.get(month, 0) + pnl

    return result


# ---------------------------------------------------------------
# Solver
# ---------------------------------------------------------------
def solve(capital: float = 100_000):
    data = fetch_data()
    if len(data) < 3:
        print("データ不足")
        return

    keys = list(GRID.keys())
    values = list(GRID.values())
    combos = list(itertools.product(*values))
    total = len(combos)

    print(f"\n{'=' * 70}")
    print("CITS 成功方程式ソルバー")
    print(f"{'=' * 70}")
    print(f"ETF: {len(TICKERS)}銘柄")
    print(f"パラメータ: {total}パターン")
    print(f"初期資金: ¥{capital:,.0f}")
    print("目標: 月利5%複利")
    print(f"{'=' * 70}\n")

    results: list[Result] = []
    for i, combo in enumerate(combos):
        if (i + 1) % 50 == 0 or i == 0:
            print(f"  進捗: {i + 1}/{total}")
        params = dict(zip(keys, combo))
        r = run_backtest(params, data, capital)
        if r.trade_count >= 5:
            results.append(r)

    # Sort by consistency score
    results.sort(key=lambda r: r.consistency_score, reverse=True)

    # === RESULTS ===
    print(f"\n{'=' * 70}")
    print("成功方程式 — 解")
    print(f"{'=' * 70}")
    print(f"有効パターン: {len(results)} / {total}")

    if not results:
        print("取引が発生したパターンがありません")
        return

    # Top 10
    print(f"\n{'─' * 90}")
    print(f"{'#':>3} {'PnL':>9} {'PnL%':>6} {'取引':>5} {'勝率':>5} {'PF':>5} "
          f"{'月勝率':>6} {'平均月利':>7} {'最悪月':>7} {'Score':>6}")
    print(f"{'─' * 90}")

    for rank, r in enumerate(results[:10], 1):
        pnl_pct = r.total_pnl / capital * 100
        pf = min(r.profit_factor, 99.9)
        print(
            f"{rank:>3} ¥{r.total_pnl:>+8,.0f} {pnl_pct:>+5.1f}% "
            f"{r.trade_count:>4} {r.win_rate:>4.0f}% {pf:>5.2f} "
            f"{r.monthly_win_rate:>5.0f}% {r.avg_monthly_return_pct:>+6.2f}% "
            f"{r.worst_month_pct:>+6.2f}% {r.consistency_score:>5.1f}"
        )

    # Detailed #1
    best = results[0]
    print(f"\n{'=' * 70}")
    print("★ 最適設定（成功方程式の解）")
    print(f"{'=' * 70}")
    print(f"総損益: ¥{best.total_pnl:+,.0f} ({best.total_pnl / capital * 100:+.2f}%)")
    print(f"取引数: {best.trade_count}  勝率: {best.win_rate:.1f}%  PF: {best.profit_factor:.2f}")
    print(f"月次勝率: {best.monthly_win_rate:.0f}%")
    print(f"平均月利: {best.avg_monthly_return_pct:+.2f}%")
    print(f"最悪月: {best.worst_month_pct:+.2f}%")

    print("\nパラメータ:")
    for k, v in best.params.items():
        if k != "capital":
            print(f"  {k}: {v}")

    # Ticker breakdown
    print("\n銘柄別:")
    ticker_stats: dict[str, dict] = {}
    for t in best.trades:
        if t.ticker not in ticker_stats:
            ticker_stats[t.ticker] = {"count": 0, "wins": 0, "pnl": 0.0}
        ticker_stats[t.ticker]["count"] += 1
        ticker_stats[t.ticker]["pnl"] += t.pnl
        if t.pnl > 0:
            ticker_stats[t.ticker]["wins"] += 1
    for tk, ts in sorted(ticker_stats.items(), key=lambda x: x[1]["pnl"], reverse=True):
        wr = ts["wins"] / ts["count"] * 100 if ts["count"] > 0 else 0
        print(f"  {tk}: {ts['count']}取引 勝率{wr:.0f}% PnL ¥{ts['pnl']:+,.0f}")

    # Monthly breakdown
    print("\n月別損益:")
    compound = capital
    print(f"  {'月':>8} {'取引':>4} {'損益':>10} {'月利':>7} {'複利残高':>12}")
    print(f"  {'─' * 50}")
    for m in sorted(best.monthly_pnl.keys()):
        pnl = best.monthly_pnl[m]
        monthly_trades = sum(1 for t in best.trades if t.date.startswith(m))
        ret_pct = pnl / capital * 100
        compound += compound * (pnl / capital)
        hit = "★" if ret_pct >= 5.0 else ("○" if ret_pct > 0 else "×")
        print(f"  {m} {monthly_trades:>4} ¥{pnl:>+9,.0f} {ret_pct:>+6.2f}% ¥{compound:>11,.0f} {hit}")

    # Compound growth simulation
    print(f"\n{'=' * 70}")
    print("複利シミュレーション（月利{:.2f}%で継続した場合）".format(best.avg_monthly_return_pct))
    print(f"{'=' * 70}")
    avg_mr = best.avg_monthly_return_pct / 100
    bal = capital
    for year in range(1, 11):
        for _ in range(12):
            bal *= (1 + avg_mr)
        monthly_income = bal * avg_mr
        print(f"  {year}年後: ¥{bal:>12,.0f}  月収: ¥{monthly_income:>10,.0f}")
        if monthly_income >= 500_000:
            print("  → ★ 月収50万円達成!")
            break

    # Success equation summary
    print(f"\n{'=' * 70}")
    print("成功の方程式")
    print(f"{'=' * 70}")
    print(f"""
  戦略: ミーンリバージョン（ボリンジャーバンド）
  銘柄: {', '.join(tk for tk in ticker_stats.keys())}
  entry_z: {best.params['mr_entry_z']}σ (ボリンジャーバンド逸脱)
  period: {best.params['mr_period']}日
  trend_align: {best.params.get('trend_align', False)}
  stop: {best.params['stop_pct']}%
  risk/trade: {best.params['risk_pct'] * 100}%

  勝率: {best.win_rate:.0f}% × PF: {best.profit_factor:.2f} × 月{best.trade_count / max(len(best.monthly_pnl), 1):.1f}回
  = 月利{best.avg_monthly_return_pct:+.2f}%
  = 複利8年で月収50万円ペース（月利5%の場合）
""")

    # Reality check
    target_gap = 5.0 - best.avg_monthly_return_pct
    if target_gap > 0:
        print(f"  ⚠ 月利5%まであと{target_gap:.2f}%不足")
        print("  → 資金増額 or レバレッジETF(1570)の比重UP で補完可能")
    else:
        print("  ★ 月利5%目標達成!")


def main():
    parser = argparse.ArgumentParser(description="CITS 成功方程式ソルバー")
    parser.add_argument("--capital", type=float, default=100_000)
    args = parser.parse_args()
    solve(capital=args.capital)


if __name__ == "__main__":
    main()
