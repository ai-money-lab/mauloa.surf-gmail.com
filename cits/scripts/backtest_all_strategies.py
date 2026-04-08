"""Backtest ALL strategies from STRATEGY_PLAYBOOK.md

Plan A: CIS 9-ETF momentum breakout (current live strategy)
Plan B-1: Overnight Reversal (全銘柄ギャップリバーサル)
Plan B-2: ORB 60-min breakout (opening range breakout)
Plan B-3: Intraday Momentum (first 30min → last 30min)
Plan B-4: Regime Filter impact on Plan A

Usage:
    python -m cits.scripts.backtest_all_strategies --capital 100000
"""

from __future__ import annotations

import argparse
import logging
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

import pandas as pd
import yfinance as yf

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------
# Plan A tickers (current live)
# ---------------------------------------------------------------
PLAN_A_TICKERS = [
    "1357", "2558", "1570", "1540", "1489",
    "1321", "1306", "2644", "1343",
]

# ---------------------------------------------------------------
# Plan B-1: Overnight Reversal - 東証主要銘柄
# Large-cap + high-liquidity stocks for gap reversal
# ---------------------------------------------------------------
OVERNIGHT_TICKERS = [
    # 日経225主要構成銘柄 (高流動性)
    "7203", "6758", "8306", "9984", "6861",  # トヨタ,ソニー,三菱UFJ,ソフトバンクG,キーエンス
    "7267", "6902", "8035", "6501", "7974",  # ホンダ,デンソー,東京エレクトロン,日立,任天堂
    "9432", "9433", "4063", "6098", "3382",  # NTT,KDDI,信越化学,リクルート,セブン&アイ
    "4502", "4503", "6723", "8058", "8031",  # 武田,アステラス,ルネサス,三菱商事,三井物産
    "2801", "4901", "6367", "7751", "9613",  # キッコーマン,富士フイルム,ダイキン,キヤノン,NTTデータ
    "8766", "8801", "6273", "7741", "4568",  # 東京海上,三井不動産,SMC,HOYA,第一三共
    "6594", "7832", "6762", "2413", "4519",  # 日電産,バンナム,TDK,エムスリー,中外製薬
    # ETFs
    "1321", "1306", "1570", "1357", "2558",
    "1540", "2644", "1489", "1343",
]

# Remove duplicates
OVERNIGHT_TICKERS = list(dict.fromkeys(OVERNIGHT_TICKERS))


@dataclass
class TradeResult:
    ticker: str
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    pnl_pct: float
    strategy: str


@dataclass
class StrategyResult:
    name: str
    trades: list[TradeResult] = field(default_factory=list)
    total_return_pct: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    sharpe: float = 0.0
    max_drawdown_pct: float = 0.0
    monthly_return_pct: float = 0.0
    num_trades: int = 0
    avg_hold_days: float = 0.0


def _sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window).mean()


def fetch_data(tickers: list[str], period: str = "1y") -> dict[str, pd.DataFrame]:
    """Fetch historical data for all tickers."""
    data = {}
    symbols = [f"{t}.T" for t in tickers]
    for s in symbols:
        try:
            df = yf.download(s, period=period, progress=False, auto_adjust=True)
            if df is not None and len(df) > 20:
                ticker = s.replace(".T", "")
                data[ticker] = df
        except Exception:
            pass
    return data


# ---------------------------------------------------------------
# Plan A: CIS Momentum Breakout (current live)
# ---------------------------------------------------------------
def backtest_plan_a(data: dict[str, pd.DataFrame], capital: float,
                    stop_pct: float = 1.5, target_pct: float = 5.0,
                    breakout_days: int = 20) -> StrategyResult:
    """CIS-style 20-day breakout with volume confirmation."""
    trades = []

    for ticker, df in data.items():
        if len(df) < breakout_days + 5:
            continue

        high_n = df["High"].rolling(breakout_days).max()
        vol_avg = df["Volume"].rolling(breakout_days).mean()

        in_trade = False
        entry_price = 0.0
        entry_idx = 0

        for i in range(breakout_days, len(df)):
            if not in_trade:
                # Entry: close breaks above N-day high with volume spike
                close = df["Close"].iloc[i]
                prev_high = high_n.iloc[i - 1]
                vol = df["Volume"].iloc[i]
                avg_vol = vol_avg.iloc[i]

                if isinstance(close, pd.Series):
                    close = close.iloc[0]
                if isinstance(prev_high, pd.Series):
                    prev_high = prev_high.iloc[0]
                if isinstance(vol, pd.Series):
                    vol = vol.iloc[0]
                if isinstance(avg_vol, pd.Series):
                    avg_vol = avg_vol.iloc[0]

                if pd.notna(prev_high) and pd.notna(avg_vol) and avg_vol > 0:
                    if close > prev_high and vol > avg_vol * 1.2:
                        entry_price = close
                        entry_idx = i
                        in_trade = True
            else:
                # Check SL/TP
                close = df["Close"].iloc[i]
                if isinstance(close, pd.Series):
                    close = close.iloc[0]

                pnl = (close - entry_price) / entry_price * 100
                hold_days = i - entry_idx

                if pnl <= -stop_pct or pnl >= target_pct or hold_days >= 10:
                    trades.append(TradeResult(
                        ticker=ticker,
                        entry_date=str(df.index[entry_idx].date()),
                        exit_date=str(df.index[i].date()),
                        entry_price=entry_price,
                        exit_price=close,
                        pnl_pct=round(pnl, 2),
                        strategy="PlanA_CIS",
                    ))
                    in_trade = False

    return _compute_stats("Plan A: CIS 9-ETF Breakout", trades, capital)


# ---------------------------------------------------------------
# Plan B-1: Overnight Reversal
# ---------------------------------------------------------------
def backtest_overnight_reversal(data: dict[str, pd.DataFrame], capital: float,
                                 gap_threshold: float = 1.0,
                                 exit_intraday: bool = True) -> StrategyResult:
    """CO-OC Strategy: buy large gap-down, sell large gap-up at close."""
    trades = []

    for ticker, df in data.items():
        if len(df) < 30:
            continue

        for i in range(1, len(df)):
            prev_close = df["Close"].iloc[i - 1]
            today_open = df["Open"].iloc[i]
            today_close = df["Close"].iloc[i]

            if isinstance(prev_close, pd.Series):
                prev_close = prev_close.iloc[0]
            if isinstance(today_open, pd.Series):
                today_open = today_open.iloc[0]
            if isinstance(today_close, pd.Series):
                today_close = today_close.iloc[0]

            if prev_close <= 0:
                continue

            gap_pct = (today_open - prev_close) / prev_close * 100

            # Gap down reversal (buy at open, sell at close)
            if gap_pct < -gap_threshold:
                pnl = (today_close - today_open) / today_open * 100
                trades.append(TradeResult(
                    ticker=ticker,
                    entry_date=str(df.index[i].date()),
                    exit_date=str(df.index[i].date()),
                    entry_price=today_open,
                    exit_price=today_close,
                    pnl_pct=round(pnl, 2),
                    strategy="PlanB1_OvernightRev",
                ))

    return _compute_stats("Plan B-1: Overnight Reversal", trades, capital)


# ---------------------------------------------------------------
# Plan B-2: ORB 60-min Breakout (simulated with daily data)
# ---------------------------------------------------------------
def backtest_orb(data: dict[str, pd.DataFrame], capital: float) -> StrategyResult:
    """ORB approximation using daily High/Low range breakout.
    Since we don't have intraday data, we simulate:
    - If close > open + 60% of (high-low): bullish ORB breakout
    - Exit at close same day
    """
    trades = []

    for ticker, df in data.items():
        if len(df) < 30:
            continue

        sma20 = _sma(df["Close"], 20)

        for i in range(20, len(df)):
            o = df["Open"].iloc[i]
            h = df["High"].iloc[i]
            low = df["Low"].iloc[i]
            c = df["Close"].iloc[i]
            sma_val = sma20.iloc[i]

            for val in [o, h, low, c, sma_val]:
                if isinstance(val, pd.Series):
                    val = val.iloc[0]

            if isinstance(o, pd.Series): o = o.iloc[0]
            if isinstance(h, pd.Series): h = h.iloc[0]
            if isinstance(low, pd.Series): low = low.iloc[0]
            if isinstance(c, pd.Series): c = c.iloc[0]
            if isinstance(sma_val, pd.Series): sma_val = sma_val.iloc[0]

            if pd.isna(sma_val) or (h - low) == 0:
                continue

            day_range = h - low
            breakout_level = o + day_range * 0.6

            # Bullish ORB: close above breakout level + trend filter
            if c > breakout_level and c > sma_val:
                # Simulate entry at breakout, exit at close
                entry = breakout_level
                pnl = (c - entry) / entry * 100
                trades.append(TradeResult(
                    ticker=ticker,
                    entry_date=str(df.index[i].date()),
                    exit_date=str(df.index[i].date()),
                    entry_price=round(entry, 1),
                    exit_price=c,
                    pnl_pct=round(pnl, 2),
                    strategy="PlanB2_ORB60",
                ))

    return _compute_stats("Plan B-2: ORB 60-min Breakout", trades, capital)


# ---------------------------------------------------------------
# Plan B-3: Intraday Momentum (simulated)
# ---------------------------------------------------------------
def backtest_intraday_momentum(data: dict[str, pd.DataFrame], capital: float) -> StrategyResult:
    """Simulate intraday momentum with daily data.
    First half return predicts second half.
    Proxy: (Open→Midpoint) predicts (Midpoint→Close)
    """
    trades = []

    for ticker, df in data.items():
        if len(df) < 30:
            continue

        for i in range(1, len(df)):
            prev_close = df["Close"].iloc[i - 1]
            o = df["Open"].iloc[i]
            h = df["High"].iloc[i]
            low = df["Low"].iloc[i]
            c = df["Close"].iloc[i]

            if isinstance(prev_close, pd.Series): prev_close = prev_close.iloc[0]
            if isinstance(o, pd.Series): o = o.iloc[0]
            if isinstance(h, pd.Series): h = h.iloc[0]
            if isinstance(low, pd.Series): low = low.iloc[0]
            if isinstance(c, pd.Series): c = c.iloc[0]

            if prev_close <= 0 or o <= 0:
                continue

            # First half return: prev_close -> open
            first_half = (o - prev_close) / prev_close * 100

            # Only trade when first half move is significant
            if abs(first_half) < 0.3:
                continue

            # Prediction: same direction continues
            midpoint = (h + low) / 2
            if first_half > 0:
                # Bullish momentum: buy at midpoint, exit at close
                entry = midpoint
                pnl = (c - entry) / entry * 100
            else:
                # Bearish momentum: short at midpoint, cover at close
                entry = midpoint
                pnl = (entry - c) / entry * 100

            trades.append(TradeResult(
                ticker=ticker,
                entry_date=str(df.index[i].date()),
                exit_date=str(df.index[i].date()),
                entry_price=round(entry, 1),
                exit_price=c,
                pnl_pct=round(pnl, 2),
                strategy="PlanB3_IntradayMom",
            ))

    return _compute_stats("Plan B-3: Intraday Momentum", trades, capital)


# ---------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------
def _compute_stats(name: str, trades: list[TradeResult], capital: float) -> StrategyResult:
    if not trades:
        return StrategyResult(name=name)

    wins = [t for t in trades if t.pnl_pct > 0]
    losses = [t for t in trades if t.pnl_pct <= 0]

    win_rate = len(wins) / len(trades) * 100
    gross_profit = sum(t.pnl_pct for t in wins)
    gross_loss = abs(sum(t.pnl_pct for t in losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Compound returns
    equity = capital
    equity_curve = [capital]
    monthly_returns = defaultdict(float)

    for t in sorted(trades, key=lambda x: x.entry_date):
        pnl_amount = equity * (t.pnl_pct / 100) * 0.05  # 5% risk per trade
        equity += pnl_amount
        equity_curve.append(equity)
        month_key = t.entry_date[:7]
        monthly_returns[month_key] += t.pnl_pct * 0.05

    total_return = (equity - capital) / capital * 100

    # Max drawdown
    peak = capital
    max_dd = 0
    for eq in equity_curve:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak * 100
        if dd > max_dd:
            max_dd = dd

    # Monthly return
    monthly_vals = list(monthly_returns.values())
    avg_monthly = statistics.mean(monthly_vals) if monthly_vals else 0

    # Sharpe (annualized from monthly)
    if len(monthly_vals) > 1:
        sharpe = (statistics.mean(monthly_vals) / statistics.stdev(monthly_vals)) * (12 ** 0.5)
    else:
        sharpe = 0

    return StrategyResult(
        name=name,
        trades=trades,
        total_return_pct=round(total_return, 2),
        win_rate=round(win_rate, 1),
        profit_factor=round(profit_factor, 2),
        sharpe=round(sharpe, 2),
        max_drawdown_pct=round(max_dd, 2),
        monthly_return_pct=round(avg_monthly, 2),
        num_trades=len(trades),
    )


def print_result(r: StrategyResult):
    print(f"\n{'='*60}")
    print(f"  {r.name}")
    print(f"{'='*60}")
    print(f"  Trades:          {r.num_trades}")
    print(f"  Win Rate:        {r.win_rate}%")
    print(f"  Profit Factor:   {r.profit_factor}")
    print(f"  Total Return:    {r.total_return_pct}%")
    print(f"  Monthly Return:  {r.monthly_return_pct}%")
    print(f"  Sharpe Ratio:    {r.sharpe}")
    print(f"  Max Drawdown:    {r.max_drawdown_pct}%")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--capital", type=float, default=100000)
    args = parser.parse_args()

    print("=" * 60)
    print("  CITS ALL-STRATEGY BACKTEST")
    print(f"  Capital: JPY{args.capital:,.0f}")
    print("=" * 60)

    # Fetch data
    print("\n[1/4] Fetching Plan A data (9 ETFs)...")
    plan_a_data = fetch_data(PLAN_A_TICKERS, period="1y")
    print(f"  -> {len(plan_a_data)} tickers loaded")

    print("\n[2/4] Fetching Plan B data (主要銘柄)...")
    plan_b_data = fetch_data(OVERNIGHT_TICKERS, period="1y")
    print(f"  -> {len(plan_b_data)} tickers loaded")

    # Run all backtests
    print("\n[3/4] Running backtests...")
    results = []

    r_a = backtest_plan_a(plan_a_data, args.capital)
    results.append(r_a)
    print(f"  Plan A done: {r_a.num_trades} trades")

    r_b1 = backtest_overnight_reversal(plan_b_data, args.capital)
    results.append(r_b1)
    print(f"  Plan B-1 done: {r_b1.num_trades} trades")

    r_b2 = backtest_orb(plan_b_data, args.capital)
    results.append(r_b2)
    print(f"  Plan B-2 done: {r_b2.num_trades} trades")

    r_b3 = backtest_intraday_momentum(plan_b_data, args.capital)
    results.append(r_b3)
    print(f"  Plan B-3 done: {r_b3.num_trades} trades")

    # Print all results
    print("\n[4/4] Results")
    for r in results:
        print_result(r)

    # Comparison table
    print(f"\n{'='*60}")
    print("  COMPARISON TABLE")
    print(f"{'='*60}")
    print(f"{'Strategy':<30} {'Trades':>6} {'WinR':>6} {'PF':>6} {'MonRet':>8} {'Sharpe':>7} {'MaxDD':>7}")
    print("-" * 78)
    for r in results:
        print(f"{r.name:<30} {r.num_trades:>6} {r.win_rate:>5.1f}% {r.profit_factor:>6.2f} {r.monthly_return_pct:>7.2f}% {r.sharpe:>7.2f} {r.max_drawdown_pct:>6.2f}%")

    # Recommendation
    print(f"\n{'='*60}")
    print("  RECOMMENDATION")
    print(f"{'='*60}")
    best = max(results, key=lambda r: r.sharpe if r.num_trades > 5 else -999)
    print(f"  Best Sharpe: {best.name} (Sharpe={best.sharpe})")
    best_pf = max(results, key=lambda r: r.profit_factor if r.num_trades > 5 else -999)
    print(f"  Best PF:     {best_pf.name} (PF={best_pf.profit_factor})")


if __name__ == "__main__":
    main()
