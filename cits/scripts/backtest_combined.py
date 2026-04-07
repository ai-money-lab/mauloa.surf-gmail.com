"""Backtest Combined -- ALL strategy combinations
Finds the winning formula from CIS / Kei-kun / Overnight / ORB combinations.

Usage:
    python cits/scripts/backtest_combined.py
"""
from __future__ import annotations

import json
import math
import random
import statistics
import warnings
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------
# Config
# ---------------------------------------------------------------
CAPITAL = 100_000
RISK_PCT = 0.05
SAMPLE_SIZE = 400  # sample from 3950 tickers for speed
BATCH_SIZE = 200
PERIOD_DAYS = 365
MIN_PRICE = 100
MIN_AVG_VOL = 5000

# CIS params
CIS_BREAKOUT_DAYS = 20
CIS_VOL_MULT = 1.2
CIS_STOP_PCT = -1.5
CIS_TARGET_PCT = 5.0
CIS_MAX_HOLD = 10

# Kei-kun params
KEI_SIDEWAYS_DAYS = 60
KEI_SIDEWAYS_RANGE_PCT = 15
KEI_NEW_HIGH_EXIT = 7
KEI_MAX_HOLD = 30
KEI_STOP_PCT = -5.0

# Overnight params
OVERNIGHT_GAP_PCT = -1.0  # gap down > 1%

# ORB params
ORB_LOOKBACK = 1  # use first day open/high/low as proxy (daily sim)

# VIX regime filter
VIX_THRESHOLD = 30


# ---------------------------------------------------------------
# Data
# ---------------------------------------------------------------
@dataclass
class Trade:
    ticker: str
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    pnl_pct: float
    strategy: str
    hold_days: int = 1


def load_tickers() -> list[str]:
    cache = Path(__file__).resolve().parent.parent / "data" / "tse_tickers.json"
    if cache.exists():
        data = json.loads(cache.read_text(encoding="utf-8"))
        tickers = data["tickers"]
    else:
        tickers = [
            "7203", "6758", "8306", "9984", "6861", "1321", "1306", "1570",
            "1357", "2558", "8035", "6501", "7974", "9432", "4063",
        ]
    random.seed(42)
    if len(tickers) > SAMPLE_SIZE:
        tickers = random.sample(tickers, SAMPLE_SIZE)
    return tickers


def fetch_all_data(tickers: list[str]) -> tuple[dict[str, pd.DataFrame], pd.DataFrame | None]:
    """Batch download all tickers + VIX. Return (stock_data, vix_df)."""
    data: dict[str, pd.DataFrame] = {}
    end = date.today()
    start = end - timedelta(days=PERIOD_DAYS + 90)  # extra for sideways calc

    symbols = [f"{t}.T" for t in tickers]
    total = len(symbols)
    print(f"Downloading {total} tickers in batches of {BATCH_SIZE}...")

    for i in range(0, total, BATCH_SIZE):
        chunk = symbols[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        print(f"  Batch {batch_num}/{math.ceil(total / BATCH_SIZE)} ({len(chunk)} tickers)...")
        try:
            df_all = yf.download(
                chunk, start=str(start), end=str(end),
                auto_adjust=True, progress=False, threads=True,
            )
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
                # single ticker
                key = chunk[0].replace(".T", "")
                df_clean = df_all.dropna()
                if len(df_clean) >= 90:
                    data[key] = df_clean
        except Exception as e:
            print(f"    Batch error: {e}")

    # Fetch VIX
    vix_df = None
    try:
        vix = yf.download("^VIX", start=str(start), end=str(end),
                          auto_adjust=True, progress=False)
        if vix is not None and not vix.empty:
            if isinstance(vix.columns, pd.MultiIndex):
                vix.columns = vix.columns.get_level_values(0)
            vix_df = vix
    except Exception:
        pass

    print(f"Loaded: {len(data)} tickers, VIX={'yes' if vix_df is not None else 'no'}")
    return data, vix_df


def _safe_float(val) -> float:
    if isinstance(val, pd.Series):
        return float(val.iloc[0])
    return float(val)


# ---------------------------------------------------------------
# Strategy: CIS Breakout
# ---------------------------------------------------------------
def run_cis(data: dict[str, pd.DataFrame], vix_df=None, use_vix=False) -> list[Trade]:
    trades = []
    for ticker, df in data.items():
        if len(df) < CIS_BREAKOUT_DAYS + CIS_MAX_HOLD + 5:
            continue
        closes = [_safe_float(x) for x in df["Close"]]
        volumes = [_safe_float(x) for x in df["Volume"]]
        dates = df.index

        # skip penny / thin
        avg_price = statistics.mean(closes[-60:]) if len(closes) >= 60 else statistics.mean(closes)
        avg_vol = statistics.mean(volumes[-60:]) if len(volumes) >= 60 else statistics.mean(volumes)
        if avg_price < MIN_PRICE or avg_vol < MIN_AVG_VOL:
            continue

        in_trade = False
        entry_price = 0.0
        entry_idx = 0

        for i in range(CIS_BREAKOUT_DAYS + 1, len(df) - 1):
            if use_vix and vix_df is not None:
                d = dates[i]
                vix_before = vix_df[vix_df.index <= d]
                if len(vix_before) > 0:
                    vix_val = _safe_float(vix_before["Close"].iloc[-1])
                    if vix_val > VIX_THRESHOLD:
                        continue

            if not in_trade:
                high_20 = max(closes[i - CIS_BREAKOUT_DAYS:i])
                avg_v = statistics.mean(volumes[i - CIS_BREAKOUT_DAYS:i])
                if avg_v <= 0:
                    continue
                if closes[i] > high_20 and volumes[i] > avg_v * CIS_VOL_MULT:
                    entry_price = closes[i]
                    entry_idx = i
                    in_trade = True
            else:
                hold = i - entry_idx
                pnl_pct = (closes[i] - entry_price) / entry_price * 100
                exit_it = False
                if pnl_pct <= CIS_STOP_PCT:
                    exit_it = True
                elif pnl_pct >= CIS_TARGET_PCT:
                    exit_it = True
                elif hold >= CIS_MAX_HOLD:
                    exit_it = True
                if exit_it:
                    trades.append(Trade(
                        ticker=ticker,
                        entry_date=str(dates[entry_idx].date()),
                        exit_date=str(dates[i].date()),
                        entry_price=round(entry_price, 1),
                        exit_price=round(closes[i], 1),
                        pnl_pct=round(pnl_pct, 2),
                        strategy="CIS",
                        hold_days=hold,
                    ))
                    in_trade = False
    return trades


# ---------------------------------------------------------------
# Strategy: Kei-kun
# ---------------------------------------------------------------
def _is_sideways(closes: list[float], end_idx: int) -> bool:
    """Check if last KEI_SIDEWAYS_DAYS is within range."""
    if end_idx < KEI_SIDEWAYS_DAYS:
        return False
    window = closes[end_idx - KEI_SIDEWAYS_DAYS:end_idx]
    w_min, w_max = min(window), max(window)
    if w_min <= 0:
        return False
    range_pct = (w_max - w_min) / w_min * 100
    return range_pct <= KEI_SIDEWAYS_RANGE_PCT


def run_keikun(data: dict[str, pd.DataFrame], vix_df=None, use_vix=False,
               require_volume_spike=False, vol_spike_mult=2.0,
               require_candle_confirm=False) -> list[Trade]:
    trades = []
    for ticker, df in data.items():
        if len(df) < KEI_SIDEWAYS_DAYS + KEI_MAX_HOLD + 5:
            continue
        closes = [_safe_float(x) for x in df["Close"]]
        volumes = [_safe_float(x) for x in df["Volume"]]
        opens = [_safe_float(x) for x in df["Open"]]
        dates = df.index

        avg_price = statistics.mean(closes[-60:]) if len(closes) >= 60 else statistics.mean(closes)
        avg_vol_all = statistics.mean(volumes[-60:]) if len(volumes) >= 60 else statistics.mean(volumes)
        if avg_price < MIN_PRICE or avg_vol_all < MIN_AVG_VOL:
            continue

        in_trade = False
        entry_price = 0.0
        entry_idx = 0
        new_high_count = 0
        trade_high = 0.0

        for i in range(KEI_SIDEWAYS_DAYS, len(df) - 1):
            if use_vix and vix_df is not None:
                d = dates[i]
                vix_before = vix_df[vix_df.index <= d]
                if len(vix_before) > 0:
                    vix_val = _safe_float(vix_before["Close"].iloc[-1])
                    if vix_val > VIX_THRESHOLD:
                        continue

            if not in_trade:
                if not _is_sideways(closes, i):
                    continue
                w_max = max(closes[i - KEI_SIDEWAYS_DAYS:i])
                if closes[i] > w_max * 1.005:
                    # Volume spike filter
                    if require_volume_spike:
                        avg_v = statistics.mean(volumes[max(0, i - 20):i]) if i >= 20 else 1
                        if avg_v <= 0 or volumes[i] < avg_v * vol_spike_mult:
                            continue

                    # Candle confirmation filter
                    if require_candle_confirm and i >= 2:
                        # Bullish engulfing or three white soldiers
                        is_engulfing = (closes[i] > opens[i] and
                                        closes[i - 1] < opens[i - 1] and
                                        closes[i] > opens[i - 1] and
                                        opens[i] < closes[i - 1])
                        is_three_white = (i >= 3 and
                                          closes[i] > opens[i] and
                                          closes[i - 1] > opens[i - 1] and
                                          closes[i - 2] > opens[i - 2])
                        is_strong_green = (closes[i] > opens[i] and
                                           (closes[i] - opens[i]) / opens[i] * 100 > 1.5)
                        if not (is_engulfing or is_three_white or is_strong_green):
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
                exit_it = False
                if new_high_count >= KEI_NEW_HIGH_EXIT:
                    exit_it = True
                elif pnl_pct <= KEI_STOP_PCT:
                    exit_it = True
                elif hold_days >= KEI_MAX_HOLD:
                    exit_it = True
                if exit_it:
                    trades.append(Trade(
                        ticker=ticker,
                        entry_date=str(dates[entry_idx].date()),
                        exit_date=str(dates[i].date()),
                        entry_price=round(entry_price, 1),
                        exit_price=round(closes[i], 1),
                        pnl_pct=round(pnl_pct, 2),
                        strategy="KEI",
                        hold_days=hold_days,
                    ))
                    in_trade = False
    return trades


# ---------------------------------------------------------------
# Strategy: Overnight Reversal
# ---------------------------------------------------------------
def run_overnight(data: dict[str, pd.DataFrame], vix_df=None, use_vix=False) -> list[Trade]:
    """Buy at open after gap-down > 1%, sell at close same day."""
    trades = []
    for ticker, df in data.items():
        if len(df) < 30:
            continue
        closes = [_safe_float(x) for x in df["Close"]]
        opens = [_safe_float(x) for x in df["Open"]]
        volumes = [_safe_float(x) for x in df["Volume"]]
        dates = df.index

        avg_price = statistics.mean(closes[-60:]) if len(closes) >= 60 else statistics.mean(closes)
        avg_vol_all = statistics.mean(volumes[-60:]) if len(volumes) >= 60 else statistics.mean(volumes)
        if avg_price < MIN_PRICE or avg_vol_all < MIN_AVG_VOL:
            continue

        for i in range(1, len(df)):
            if use_vix and vix_df is not None:
                d = dates[i]
                vix_before = vix_df[vix_df.index <= d]
                if len(vix_before) > 0:
                    vix_val = _safe_float(vix_before["Close"].iloc[-1])
                    if vix_val > VIX_THRESHOLD:
                        continue

            prev_close = closes[i - 1]
            if prev_close <= 0:
                continue
            gap_pct = (opens[i] - prev_close) / prev_close * 100
            if gap_pct <= OVERNIGHT_GAP_PCT:  # gap down > 1%
                entry = opens[i]
                exit_p = closes[i]
                pnl_pct = (exit_p - entry) / entry * 100
                trades.append(Trade(
                    ticker=ticker,
                    entry_date=str(dates[i].date()),
                    exit_date=str(dates[i].date()),
                    entry_price=round(entry, 1),
                    exit_price=round(exit_p, 1),
                    pnl_pct=round(pnl_pct, 2),
                    strategy="OVERNIGHT",
                    hold_days=1,
                ))
    return trades


# ---------------------------------------------------------------
# Strategy: ORB 60min (daily proxy)
# ---------------------------------------------------------------
def run_orb(data: dict[str, pd.DataFrame], vix_df=None, use_vix=False) -> list[Trade]:
    """Opening Range Breakout proxy: if close > open by > 0.5% after prev day narrow range, buy next day."""
    trades = []
    for ticker, df in data.items():
        if len(df) < 30:
            continue
        closes = [_safe_float(x) for x in df["Close"]]
        opens = [_safe_float(x) for x in df["Open"]]
        highs = [_safe_float(x) for x in df["High"]]
        lows = [_safe_float(x) for x in df["Low"]]
        volumes = [_safe_float(x) for x in df["Volume"]]
        dates = df.index

        avg_price = statistics.mean(closes[-60:]) if len(closes) >= 60 else statistics.mean(closes)
        avg_vol_all = statistics.mean(volumes[-60:]) if len(volumes) >= 60 else statistics.mean(volumes)
        if avg_price < MIN_PRICE or avg_vol_all < MIN_AVG_VOL:
            continue

        for i in range(2, len(df) - 1):
            if use_vix and vix_df is not None:
                d = dates[i]
                vix_before = vix_df[vix_df.index <= d]
                if len(vix_before) > 0:
                    vix_val = _safe_float(vix_before["Close"].iloc[-1])
                    if vix_val > VIX_THRESHOLD:
                        continue

            # Prev day was narrow range (< 1.5%)
            if lows[i - 1] <= 0:
                continue
            prev_range_pct = (highs[i - 1] - lows[i - 1]) / lows[i - 1] * 100
            if prev_range_pct > 1.5:
                continue

            # Today breaks above prev high
            if closes[i] > highs[i - 1]:
                entry = closes[i]
                # Exit next day close
                exit_p = closes[i + 1]
                pnl_pct = (exit_p - entry) / entry * 100
                trades.append(Trade(
                    ticker=ticker,
                    entry_date=str(dates[i].date()),
                    exit_date=str(dates[i + 1].date()),
                    entry_price=round(entry, 1),
                    exit_price=round(exit_p, 1),
                    pnl_pct=round(pnl_pct, 2),
                    strategy="ORB",
                    hold_days=1,
                ))
    return trades


# ---------------------------------------------------------------
# Combination B: CIS + Kei-kun (parallel -- union of both)
# ---------------------------------------------------------------
def run_cis_plus_keikun(data, vix_df=None, use_vix=False):
    cis_trades = run_cis(data, vix_df, use_vix)
    kei_trades = run_keikun(data, vix_df, use_vix)
    combined = cis_trades + kei_trades
    combined.sort(key=lambda t: t.entry_date)
    return combined


# ---------------------------------------------------------------
# Combination C: CIS filtered by sideways (only CIS on sideways stocks)
# ---------------------------------------------------------------
def run_cis_filtered_sideways(data, vix_df=None, use_vix=False):
    trades = []
    for ticker, df in data.items():
        if len(df) < max(CIS_BREAKOUT_DAYS, KEI_SIDEWAYS_DAYS) + CIS_MAX_HOLD + 5:
            continue
        closes = [_safe_float(x) for x in df["Close"]]
        volumes = [_safe_float(x) for x in df["Volume"]]
        dates = df.index

        avg_price = statistics.mean(closes[-60:]) if len(closes) >= 60 else statistics.mean(closes)
        avg_vol = statistics.mean(volumes[-60:]) if len(volumes) >= 60 else statistics.mean(volumes)
        if avg_price < MIN_PRICE or avg_vol < MIN_AVG_VOL:
            continue

        in_trade = False
        entry_price = 0.0
        entry_idx = 0

        start_i = max(CIS_BREAKOUT_DAYS + 1, KEI_SIDEWAYS_DAYS)
        for i in range(start_i, len(df) - 1):
            if use_vix and vix_df is not None:
                d = dates[i]
                vix_before = vix_df[vix_df.index <= d]
                if len(vix_before) > 0:
                    vix_val = _safe_float(vix_before["Close"].iloc[-1])
                    if vix_val > VIX_THRESHOLD:
                        continue

            if not in_trade:
                # Must be sideways (Kei-kun filter)
                if not _is_sideways(closes, i):
                    continue
                # CIS breakout
                high_20 = max(closes[i - CIS_BREAKOUT_DAYS:i])
                avg_v = statistics.mean(volumes[i - CIS_BREAKOUT_DAYS:i])
                if avg_v <= 0:
                    continue
                if closes[i] > high_20 and volumes[i] > avg_v * CIS_VOL_MULT:
                    entry_price = closes[i]
                    entry_idx = i
                    in_trade = True
            else:
                hold = i - entry_idx
                pnl_pct = (closes[i] - entry_price) / entry_price * 100
                exit_it = False
                if pnl_pct <= CIS_STOP_PCT:
                    exit_it = True
                elif pnl_pct >= CIS_TARGET_PCT:
                    exit_it = True
                elif hold >= CIS_MAX_HOLD:
                    exit_it = True
                if exit_it:
                    trades.append(Trade(
                        ticker=ticker,
                        entry_date=str(dates[entry_idx].date()),
                        exit_date=str(dates[i].date()),
                        entry_price=round(entry_price, 1),
                        exit_price=round(closes[i], 1),
                        pnl_pct=round(pnl_pct, 2),
                        strategy="CIS+SW",
                        hold_days=hold,
                    ))
                    in_trade = False
    return trades


# ---------------------------------------------------------------
# Metrics calculation
# ---------------------------------------------------------------
@dataclass
class Metrics:
    name: str
    num_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_pnl_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe: float = 0.0
    monthly_return_pct: float = 0.0
    trades_per_month: float = 0.0
    total_return_pct: float = 0.0
    avg_hold_days: float = 0.0


def calc_metrics(name: str, trades: list[Trade]) -> Metrics:
    m = Metrics(name=name)
    if not trades:
        return m

    m.num_trades = len(trades)
    pnls = [t.pnl_pct for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    m.win_rate = len(wins) / len(pnls) * 100
    m.avg_pnl_pct = statistics.mean(pnls)
    m.avg_hold_days = statistics.mean([t.hold_days for t in trades])

    gross_win = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 0.01
    m.profit_factor = gross_win / gross_loss if gross_loss > 0 else 999.0

    # Compound equity curve for drawdown
    equity = CAPITAL
    peak = CAPITAL
    max_dd = 0.0
    monthly_rets: dict[str, float] = defaultdict(float)

    sorted_trades = sorted(trades, key=lambda t: t.entry_date)
    for t in sorted_trades:
        trade_pnl = equity * RISK_PCT * (t.pnl_pct / 100)
        equity += trade_pnl
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak * 100
        if dd > max_dd:
            max_dd = dd
        monthly_rets[t.entry_date[:7]] += t.pnl_pct * RISK_PCT

    m.max_drawdown_pct = round(max_dd, 2)
    m.total_return_pct = round((equity - CAPITAL) / CAPITAL * 100, 2)

    # Monthly stats
    if monthly_rets:
        vals = list(monthly_rets.values())
        m.monthly_return_pct = round(statistics.mean(vals), 2)

        # Count months in the data
        if sorted_trades:
            first = sorted_trades[0].entry_date
            last = sorted_trades[-1].entry_date
            # rough month count
            from datetime import datetime
            d1 = datetime.strptime(first, "%Y-%m-%d")
            d2 = datetime.strptime(last, "%Y-%m-%d")
            months = max(1, (d2 - d1).days / 30)
            m.trades_per_month = round(m.num_trades / months, 1)

    # Sharpe (annualized from daily PnL proxy)
    if len(pnls) > 1:
        mean_r = statistics.mean(pnls)
        std_r = statistics.stdev(pnls)
        if std_r > 0:
            m.sharpe = round((mean_r / std_r) * (252 ** 0.5) / (m.avg_hold_days ** 0.5), 2)

    return m


# ---------------------------------------------------------------
# Main
# ---------------------------------------------------------------
def main():
    print("=" * 70)
    print("  COMBINED STRATEGY BACKTEST -- Finding the Winning Formula")
    print("  Capital: 100,000 JPY | Risk: 5% | Period: 1 year")
    print("=" * 70)

    tickers = load_tickers()
    print(f"\nSampled {len(tickers)} tickers from TSE cache")
    data, vix_df = fetch_all_data(tickers)

    if not data:
        print("ERROR: No data loaded. Exiting.")
        return

    # Run all strategies
    print("\n--- Running strategies ---")
    results: dict[str, Metrics] = {}

    # A. Standalone strategies
    print("[A-1] CIS Breakout (standalone)...")
    trades_cis = run_cis(data)
    results["A1_CIS"] = calc_metrics("A1: CIS Breakout", trades_cis)

    print("[A-2] Kei-kun (standalone)...")
    trades_kei = run_keikun(data)
    results["A2_KEI"] = calc_metrics("A2: Kei-kun", trades_kei)

    print("[A-3] Overnight Reversal (standalone)...")
    trades_ovn = run_overnight(data)
    results["A3_OVN"] = calc_metrics("A3: Overnight Rev", trades_ovn)

    print("[A-4] ORB 60min (standalone)...")
    trades_orb = run_orb(data)
    results["A4_ORB"] = calc_metrics("A4: ORB 60min", trades_orb)

    # B. CIS + Kei-kun parallel
    print("[B] CIS + Kei-kun combined...")
    trades_b = run_cis_plus_keikun(data)
    results["B_CIS+KEI"] = calc_metrics("B: CIS+Kei parallel", trades_b)

    # C. CIS filtered by sideways
    print("[C] CIS filtered by Kei-kun sideways...")
    trades_c = run_cis_filtered_sideways(data)
    results["C_CIS_SW"] = calc_metrics("C: CIS+Sideways", trades_c)

    # D. Kei-kun + volume spike 2x
    print("[D] Kei-kun + volume spike 2x...")
    trades_d = run_keikun(data, require_volume_spike=True, vol_spike_mult=2.0)
    results["D_KEI_VOL"] = calc_metrics("D: Kei+VolSpike", trades_d)

    # E. All strategies with VIX filter
    print("[E-1] CIS + VIX filter...")
    trades_e1 = run_cis(data, vix_df, use_vix=True)
    results["E1_CIS_VIX"] = calc_metrics("E1: CIS+VIX<30", trades_e1)

    print("[E-2] Kei-kun + VIX filter...")
    trades_e2 = run_keikun(data, vix_df, use_vix=True)
    results["E2_KEI_VIX"] = calc_metrics("E2: Kei+VIX<30", trades_e2)

    print("[E-3] Overnight + VIX filter...")
    trades_e3 = run_overnight(data, vix_df, use_vix=True)
    results["E3_OVN_VIX"] = calc_metrics("E3: OVN+VIX<30", trades_e3)

    # F. Kei-kun + candle confirmation
    print("[F] Kei-kun + candle patterns...")
    trades_f = run_keikun(data, require_candle_confirm=True)
    results["F_KEI_CDL"] = calc_metrics("F: Kei+Candle", trades_f)

    # G. CIS+Sideways + VIX (ultimate combo)
    print("[G] CIS+Sideways+VIX (ultimate combo)...")
    trades_g = run_cis_filtered_sideways(data, vix_df, use_vix=True)
    results["G_ULTIMATE"] = calc_metrics("G: CIS+SW+VIX", trades_g)

    # H. Kei-kun + volume + VIX
    print("[H] Kei-kun+Vol+VIX...")
    trades_h = run_keikun(data, vix_df, use_vix=True, require_volume_spike=True, vol_spike_mult=2.0)
    results["H_KEI_ALL"] = calc_metrics("H: Kei+Vol+VIX", trades_h)

    # I. Kei-kun + candle + VIX
    print("[I] Kei-kun+Candle+VIX...")
    trades_i = run_keikun(data, vix_df, use_vix=True, require_candle_confirm=True)
    results["I_KEI_CDL_VIX"] = calc_metrics("I: Kei+Cdl+VIX", trades_i)

    # ---------------------------------------------------------------
    # Print comparison table
    # ---------------------------------------------------------------
    print("\n" + "=" * 120)
    print("  RESULTS COMPARISON TABLE")
    print("=" * 120)

    header = (
        f"{'Strategy':<25} {'Trades':>7} {'WR%':>7} {'PF':>7} "
        f"{'AvgPnL%':>8} {'MaxDD%':>8} {'Sharpe':>7} {'Mo.Ret%':>8} "
        f"{'Tr/Mo':>6} {'TotRet%':>9} {'AvgHold':>8}"
    )
    print(header)
    print("-" * 120)

    # Sort by profit factor descending
    sorted_keys = sorted(results.keys(), key=lambda k: results[k].profit_factor, reverse=True)

    for k in sorted_keys:
        m = results[k]
        row = (
            f"{m.name:<25} {m.num_trades:>7} {m.win_rate:>7.1f} {m.profit_factor:>7.2f} "
            f"{m.avg_pnl_pct:>8.2f} {m.max_drawdown_pct:>8.2f} {m.sharpe:>7.2f} {m.monthly_return_pct:>8.2f} "
            f"{m.trades_per_month:>6.1f} {m.total_return_pct:>9.2f} {m.avg_hold_days:>8.1f}"
        )
        print(row)

    print("-" * 120)

    # Find winner
    # Score = PF * 0.3 + WR * 0.2 + Sharpe * 0.2 + MonthlyRet * 0.15 - MaxDD * 0.15
    print("\n" + "=" * 70)
    print("  SCORING (PF*30 + WR*20 + Sharpe*20 + MoRet*15 - MaxDD*15)")
    print("=" * 70)

    scores: dict[str, float] = {}
    for k, m in results.items():
        if m.num_trades < 5:
            scores[k] = -999
            continue
        score = (
            m.profit_factor * 30
            + m.win_rate * 0.2
            + m.sharpe * 20
            + m.monthly_return_pct * 15
            - m.max_drawdown_pct * 0.15
        )
        scores[k] = round(score, 1)

    score_sorted = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    for rank, (k, s) in enumerate(score_sorted, 1):
        m = results[k]
        marker = " <-- WINNER" if rank == 1 else ""
        print(f"  #{rank}: {m.name:<25} Score={s:>8.1f}{marker}")

    # Winner details
    winner_key = score_sorted[0][0]
    w = results[winner_key]
    print("\n" + "=" * 70)
    print("  WINNING FORMULA")
    print("=" * 70)
    print(f"  Strategy:        {w.name}")
    print(f"  Win Rate:        {w.win_rate:.1f}%")
    print(f"  Profit Factor:   {w.profit_factor:.2f}")
    print(f"  Avg PnL/trade:   {w.avg_pnl_pct:+.2f}%")
    print(f"  Max Drawdown:    {w.max_drawdown_pct:.2f}%")
    print(f"  Sharpe Ratio:    {w.sharpe:.2f}")
    print(f"  Monthly Return:  {w.monthly_return_pct:.2f}%")
    print(f"  Trades/Month:    {w.trades_per_month:.1f}")
    print(f"  Total Return:    {w.total_return_pct:.2f}% (1yr, 5% risk/trade)")
    print(f"  Avg Hold Days:   {w.avg_hold_days:.1f}")
    print(f"  Total Trades:    {w.num_trades}")
    print("=" * 70)


if __name__ == "__main__":
    main()
