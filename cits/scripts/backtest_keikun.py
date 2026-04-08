"""Backtest: Kei-kun (山下勁) Strategy
3-month sideways -> breakout -> 7-day new high exit
Check at 14:30-15:00 (closing time only), chart-only, no fundamentals.
"""
import json
import statistics
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

SIDEWAYS_DAYS = 60
SIDEWAYS_RANGE_PCT = 15
NEW_HIGH_EXIT_DAYS = 7
MAX_HOLD_DAYS = 30
STOP_LOSS_PCT = -5.0

def load_tickers():
    cache = Path(__file__).resolve().parent.parent / "data" / "tse_tickers.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))["tickers"]
    return ["7203","6758","8306","9984","6861","1321","1306","1570","1357","2558"]

def fetch_data(tickers):
    data = {}
    symbols = [f"{t}.T" for t in tickers]
    end = date.today()
    start = end - timedelta(days=365)
    for i in range(0, len(symbols), 200):
        chunk = symbols[i:i+200]
        try:
            df_all = yf.download(chunk, start=str(start), end=str(end),
                                  auto_adjust=True, progress=False, threads=True)
            if df_all is None or df_all.empty:
                continue
            if isinstance(df_all.columns, pd.MultiIndex):
                for s in chunk:
                    key = s.replace(".T", "")
                    try:
                        df = df_all.xs(s, level=1, axis=1).dropna()
                        if len(df) >= 90:
                            data[key] = df
                    except (KeyError, ValueError):
                        pass
            else:
                key = chunk[0].replace(".T", "")
                if len(df_all.dropna()) >= 90:
                    data[key] = df_all.dropna()
        except Exception:
            pass
    return data

def backtest(data, capital=100000):
    trades = []
    for ticker, df in data.items():
        if len(df) < SIDEWAYS_DAYS + 30:
            continue
        closes = [float(x) for x in df["Close"]]
        volumes = [float(x) for x in df["Volume"]]
        in_trade = False
        entry_price = entry_idx = new_high_count = 0
        trade_high = 0.0

        for i in range(SIDEWAYS_DAYS, len(df)):
            if not in_trade:
                window = closes[i - SIDEWAYS_DAYS:i]
                w_min, w_max = min(window), max(window)
                if w_min <= 0:
                    continue
                range_pct = (w_max - w_min) / w_min * 100
                if range_pct > SIDEWAYS_RANGE_PCT:
                    continue
                if closes[i] > w_max * 1.005:
                    avg_vol = sum(volumes[i-20:i]) / 20 if i >= 20 else 1
                    if closes[i] < 100 or avg_vol < 5000:
                        continue
                    entry_price = closes[i]
                    entry_idx = i
                    in_trade = True
                    new_high_count = 0
                    trade_high = entry_price
            else:
                hold_days = i - entry_idx
                if closes[i] > trade_high:
                    trade_high = closes[i]
                    new_high_count += 1
                pnl_pct = (closes[i] - entry_price) / entry_price * 100
                exit_trade = False
                if new_high_count >= NEW_HIGH_EXIT_DAYS:
                    exit_trade = True
                    reason = "new_high_7"
                elif pnl_pct <= STOP_LOSS_PCT:
                    exit_trade = True
                    reason = "stop_loss"
                elif hold_days >= MAX_HOLD_DAYS:
                    exit_trade = True
                    reason = "max_hold"
                if exit_trade:
                    trades.append({
                        "ticker": ticker, "pnl_pct": round(pnl_pct, 2),
                        "hold_days": hold_days, "new_highs": new_high_count,
                        "exit_reason": reason,
                        "entry_date": str(df.index[entry_idx].date()),
                        "exit_date": str(df.index[i].date()),
                        "entry_price": round(entry_price, 1),
                        "exit_price": round(closes[i], 1),
                    })
                    in_trade = False
    return trades

def main():
    print("=" * 60)
    print("  KEI-KUN STRATEGY BACKTEST")
    print("  3mo sideways -> breakout -> 7-day new high exit")
    print("=" * 60)

    tickers = load_tickers()
    print(f"\nFetching {len(tickers)} tickers...")
    data = fetch_data(tickers)
    print(f"Loaded: {len(data)} tickers")

    trades = backtest(data)
    print(f"\n{'=' * 60}")
    print(f"  RESULTS")
    print(f"{'=' * 60}")
    print(f"  Total trades: {len(trades)}")

    if not trades:
        print("  No trades found.")
        return

    wins = [t for t in trades if t["pnl_pct"] > 0]
    losses = [t for t in trades if t["pnl_pct"] <= 0]
    win_rate = len(wins) / len(trades) * 100
    pnls = [t["pnl_pct"] for t in trades]
    avg_pnl = statistics.mean(pnls)
    gross_profit = sum(t["pnl_pct"] for t in wins) if wins else 0
    gross_loss = abs(sum(t["pnl_pct"] for t in losses)) if losses else 0.01
    pf = gross_profit / gross_loss
    avg_hold = statistics.mean([t["hold_days"] for t in trades])

    equity = 100000
    monthly_rets = defaultdict(float)
    for t in sorted(trades, key=lambda x: x["entry_date"]):
        eq_change = equity * (t["pnl_pct"] / 100) * 0.1
        equity += eq_change
        monthly_rets[t["entry_date"][:7]] += t["pnl_pct"] * 0.1
    total_ret = (equity - 100000) / 100000 * 100
    monthly_vals = list(monthly_rets.values())
    avg_monthly = statistics.mean(monthly_vals) if monthly_vals else 0

    print(f"  Win Rate:        {win_rate:.1f}%")
    print(f"  Avg PnL:         {avg_pnl:+.2f}%")
    print(f"  Profit Factor:   {pf:.2f}")
    print(f"  Total Return:    {total_ret:.2f}%")
    print(f"  Monthly Return:  {avg_monthly:.2f}%")
    print(f"  Avg Hold Days:   {avg_hold:.1f}")

    reasons = defaultdict(int)
    for t in trades:
        reasons[t["exit_reason"]] += 1
    print(f"\n  Exit reasons:")
    for r, c in sorted(reasons.items()):
        print(f"    {r}: {c}")

    top = sorted(trades, key=lambda t: t["pnl_pct"], reverse=True)[:10]
    print(f"\n  Top 10:")
    for t in top:
        print(f"    {t['ticker']} {t['entry_date']}->{t['exit_date']} {t['pnl_pct']:+.1f}% hold={t['hold_days']}d")

    worst = sorted(trades, key=lambda t: t["pnl_pct"])[:5]
    print(f"\n  Worst 5:")
    for t in worst:
        print(f"    {t['ticker']} {t['entry_date']}->{t['exit_date']} {t['pnl_pct']:+.1f}% reason={t['exit_reason']}")

    print(f"\n{'=' * 60}")
    print(f"  KEI-KUN vs CIS")
    print(f"{'=' * 60}")
    print(f"  KEI-KUN: {len(trades)} trades, WR={win_rate:.1f}%, PF={pf:.2f}, MonRet={avg_monthly:.2f}%")
    print(f"  CIS 9ETF: 81 trades, WR=50.6%, PF=1.81, MonRet=0.37%")

if __name__ == "__main__":
    main()
