"""CITS Success Equation Solver v2 -- Japanese Pro Trader Edition

TESTA / CIS / BNF の手法をモデル化:
  A. CIS Mode (Momentum):  20-day breakout + volume spike
  B. BNF Mode (Mean Reversion): oversold bounce near support
  C. Hybrid Mode: regime detection -> auto switch A/B

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

from cits.core.signals.mean_reversion import compute_mean_reversion
from cits.core.signals.candlestick_patterns import analyze_candlesticks
from cits.core.signals.chart_formations import analyze_formations
from cits.core.signals.support_resistance import analyze_support_resistance

try:
    from cits.core.signals.ny_nikkei_correlation import compute_ny_nikkei_signal

    HAS_NY_SIGNAL = True
except ImportError:
    HAS_NY_SIGNAL = False

try:
    from cits.core.signals.market_regime import detect_regime

    HAS_REGIME = True
except ImportError:
    HAS_REGIME = False

logging.basicConfig(level=logging.WARNING)

# ---------------------------------------------------------------
# ETFs (curated for mean reversion + momentum)
# ---------------------------------------------------------------
TICKERS = [
    "1357",  # Nikkei Double Inverse
    "2558",  # S&P500 ETF
    "1570",  # Nikkei Leverage 2x
    "1540",  # Gold ETF
    "1489",  # Nikkei High Dividend 50 ETF
    "1321",  # Nikkei 225 ETF
    "1306",  # TOPIX ETF
    "2644",  # Semiconductor ETF
    "1343",  # REIT ETF
]

# ---------------------------------------------------------------
# Parameter grid -- CIS/BNF/Hybrid
# ---------------------------------------------------------------
GRID = {
    "mode": ["cis", "bnf", "hybrid"],
    "stop_pct": [1.0, 1.5],
    "target_pct": [3.0, 5.0],
    "hold_days": [5, 10],
    "risk_pct": [0.05],
    "use_ny_signal": [True, False],
    "use_volume_confirm": [True],
    "use_chart_datsu": [True, False],       # チャート打法: ローソク足+S/R+形状確認
}


# ---------------------------------------------------------------
# Data
# ---------------------------------------------------------------
def fetch_data() -> dict[str, pd.DataFrame]:
    end = date.today()
    start = end - timedelta(days=500)
    data: dict[str, pd.DataFrame] = {}
    symbols = [f"{t}.T" for t in TICKERS] + ["^VIX", "USDJPY=X", "^N225", "^GSPC"]
    print("Fetching data...")
    for s in symbols:
        key = s.replace(".T", "") if s.endswith(".T") else s
        try:
            df = yf.download(
                s, start=str(start), end=str(end),
                auto_adjust=True, progress=False,
            )
            if df is not None and not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                data[key] = df
                print(f"  {key}: {len(df)} rows")
        except Exception as e:
            print(f"  {key}: error {e}")
    return data


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------

def _sma(values: list[float], period: int) -> float:
    seg = values[-period:]
    return sum(seg) / len(seg)


def _rsi(closes: list[float], period: int = 14) -> float:
    """Compute RSI from closing prices."""
    if len(closes) < period + 1:
        return 50.0  # neutral default
    gains: list[float] = []
    losses: list[float] = []
    for i in range(-period, 0):
        diff = closes[i] - closes[i - 1]
        if diff > 0:
            gains.append(diff)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(abs(diff))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


# ---------------------------------------------------------------
# NY signal helper (uses previous day's ^GSPC and ^N225)
# ---------------------------------------------------------------

def _get_ny_signal_direction(
    data: dict[str, pd.DataFrame],
    current_date: pd.Timestamp,
) -> int:
    """Return +1 (bullish), -1 (bearish), or 0 (neutral) from NY-Nikkei signal."""
    if not HAS_NY_SIGNAL:
        return 0
    sp_df = data.get("^GSPC")
    nk_df = data.get("^N225")
    if sp_df is None or nk_df is None:
        return 0
    sp_before = sp_df[sp_df.index <= current_date]
    nk_before = nk_df[nk_df.index <= current_date]
    if len(sp_before) < 22 or len(nk_before) < 22:
        return 0
    sp_closes = [float(x) for x in sp_before["Close"].iloc[-25:]]
    nk_closes = [float(x) for x in nk_before["Close"].iloc[-25:]]
    sig = compute_ny_nikkei_signal(sp_closes, nk_closes, lookback=20)
    return sig.direction


# ---------------------------------------------------------------
# Regime helper
# ---------------------------------------------------------------

def _get_regime(
    closes: list[float],
    highs: list[float],
    lows: list[float],
) -> str:
    """Return regime string: uptrend / downtrend / range / volatile."""
    if not HAS_REGIME:
        return "range"
    if len(closes) < 51 or len(highs) < 51 or len(lows) < 51:
        return "range"
    try:
        regime = detect_regime(closes[-60:], highs[-60:], lows[-60:])
        return regime.regime
    except (ValueError, Exception):
        return "range"


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
    mode: str  # "cis" or "bnf"


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
        neg_months = sum(1 for r in returns if r < 0)
        penalty = 1 - (neg_months / len(returns)) * 0.5
        return (mean_r / (std_r + 0.01)) * penalty * (self.trade_count ** 0.3)

    @property
    def mode_breakdown(self) -> dict[str, int]:
        """Count trades per mode (cis/bnf)."""
        counts: dict[str, int] = defaultdict(int)
        for t in self.trades:
            counts[t.mode] += 1
        return dict(counts)


def _check_cis_entry(
    closes: list[float],
    volumes: list[float],
    use_volume_confirm: bool,
) -> bool:
    """CIS mode: price breakout above 20-day high with volume spike."""
    if len(closes) < 21 or len(volumes) < 21:
        return False
    current_price = closes[-1]
    high_20 = max(closes[-21:-1])
    if current_price <= high_20:
        return False
    if use_volume_confirm:
        avg_vol = sum(volumes[-21:-1]) / 20
        if avg_vol <= 0:
            return False
        if volumes[-1] < 1.5 * avg_vol:
            return False
    return True


def _check_bnf_entry(
    closes: list[float],
) -> bool:
    """BNF mode: oversold bounce near 20-day low. RSI<30 or z_score<-1.5."""
    if len(closes) < 21:
        return False
    current_price = closes[-1]
    low_20 = min(closes[-21:-1])
    # Price near 20-day low (within 2%)
    if current_price > low_20 * 1.02:
        return False
    # Check RSI or z-score
    rsi_val = _rsi(closes, period=14)
    mr = compute_mean_reversion(closes, period=20, entry_z=1.5)
    if rsi_val < 30 or mr.z_score < -1.5:
        return True
    return False


def run_backtest(params: dict, data: dict, capital: float) -> Result:
    cost_bps = 6.5 / 10000  # slippage + spread
    lot_size = 1 if capital < 500_000 else 100
    equity = capital
    result = Result(params={**params, "capital": capital})
    mode = params["mode"]

    for ticker in TICKERS:
        df = data.get(ticker)
        if df is None:
            continue

        dates = sorted(df.index)
        opens_hist: list[float] = []
        closes_hist: list[float] = []
        volumes_hist: list[float] = []
        highs_hist: list[float] = []
        lows_hist: list[float] = []

        i = 0
        while i < len(dates):
            dt = dates[i]
            row = df.loc[dt]
            open_p = float(row["Open"])
            high_p = float(row["High"])
            low_p = float(row["Low"])
            close_p = float(row["Close"])
            volume = float(row.get("Volume", 0))

            opens_hist.append(open_p)
            closes_hist.append(close_p)
            volumes_hist.append(volume)
            highs_hist.append(high_p)
            lows_hist.append(low_p)

            if open_p <= 0 or close_p <= 0:
                i += 1
                continue

            # Need enough history
            if len(closes_hist) < 22:
                i += 1
                continue

            # --- NY signal filter ---
            ny_direction = 0
            if params["use_ny_signal"]:
                ny_direction = _get_ny_signal_direction(data, dt)

            # --- Determine active mode ---
            active_mode = mode
            if mode == "hybrid":
                regime = _get_regime(closes_hist, highs_hist, lows_hist)
                if regime == "uptrend":
                    active_mode = "cis"
                elif regime in ("downtrend", "range"):
                    active_mode = "bnf"
                else:
                    # volatile -> stay out
                    i += 1
                    continue

            # --- Entry check ---
            entry_signal = False
            direction = 0

            if active_mode == "cis":
                if _check_cis_entry(
                    closes_hist, volumes_hist, params["use_volume_confirm"],
                ):
                    entry_signal = True
                    direction = 1  # always long for momentum breakout
                    # NY filter: must be bullish or no filter
                    if params["use_ny_signal"] and ny_direction < 0:
                        entry_signal = False

            elif active_mode == "bnf":
                if _check_bnf_entry(closes_hist):
                    entry_signal = True
                    direction = 1  # buy oversold bounce
                    # NY filter: skip if NY strongly bearish
                    if params["use_ny_signal"] and ny_direction < -0:
                        # Allow neutral, block only explicit bearish
                        if ny_direction < 0:
                            entry_signal = False

            if not entry_signal or direction == 0:
                i += 1
                continue

            # --- チャート打法: ローソク足 + S/R + チャート形状 ---
            if params.get("use_chart_datsu", False):
                chart_pass = True

                # ローソク足パターン確認
                if len(opens_hist) >= 5:
                    candle = analyze_candlesticks(
                        opens_hist[-5:], highs_hist[-5:],
                        lows_hist[-5:], closes_hist[-5:],
                    )
                    if candle.signal_direction != 0 and candle.signal_direction != direction:
                        chart_pass = False

                # 支持線・抵抗線確認
                if chart_pass and len(closes_hist) >= 20:
                    sr = analyze_support_resistance(
                        closes_hist[-50:] if len(closes_hist) >= 50 else closes_hist,
                        highs_hist[-50:] if len(highs_hist) >= 50 else highs_hist,
                        lows_hist[-50:] if len(lows_hist) >= 50 else lows_hist,
                    )
                    if direction > 0 and sr.position == "near_resistance":
                        chart_pass = False
                    if direction < 0 and sr.position == "near_support":
                        chart_pass = False

                # チャート形状確認
                if chart_pass and len(closes_hist) >= 20:
                    formation = analyze_formations(
                        closes_hist[-30:] if len(closes_hist) >= 30 else closes_hist,
                        highs_hist[-30:] if len(highs_hist) >= 30 else highs_hist,
                        lows_hist[-30:] if len(lows_hist) >= 30 else lows_hist,
                    )
                    if formation.signal_direction != 0 and formation.signal_direction != direction:
                        chart_pass = False

                if not chart_pass:
                    i += 1
                    continue

            # --- Position sizing (TESTA: fast stops, tight risk) ---
            risk_amt = equity * params["risk_pct"]
            stop_dist = open_p * params["stop_pct"] / 100
            if stop_dist <= 0:
                i += 1
                continue
            raw_size = int(risk_amt / stop_dist)
            size = max(raw_size // lot_size * lot_size, lot_size)
            notional = size * open_p
            if notional > equity * 0.9:
                size = max(
                    int(equity * 0.9 / open_p / lot_size) * lot_size, lot_size,
                )
                notional = size * open_p
            if notional > equity:
                i += 1
                continue

            # --- Entry price ---
            entry_price = open_p * (1 + cost_bps)

            # --- Target and stop ---
            target_pct = params["target_pct"]
            if active_mode == "bnf":
                # BNF: target = SMA20 (mean reversion target)
                sma20 = _sma(closes_hist, 20)
                target_price = max(sma20, entry_price * (1 + target_pct / 100))
            else:
                target_price = entry_price * (1 + target_pct / 100)
            stop_price = entry_price * (1 - params["stop_pct"] / 100)

            # --- Trailing stop for CIS mode ---
            max_hold = params["hold_days"]
            exit_price = None
            trailing_stop = stop_price

            for j in range(i + 1, min(i + max_hold + 1, len(dates))):
                future_row = df.loc[dates[j]]
                f_high = float(future_row["High"])
                f_low = float(future_row["Low"])

                # Check stop first (TESTA: fast stop loss)
                if f_low <= trailing_stop:
                    exit_price = trailing_stop
                    break
                # Check target
                if f_high >= target_price:
                    exit_price = target_price
                    break
                # CIS: update trailing stop
                if active_mode == "cis":
                    new_stop = f_high * (1 - params["stop_pct"] / 100)
                    if new_stop > trailing_stop:
                        trailing_stop = new_stop

            if exit_price is None:
                last_idx = min(i + max_hold, len(dates) - 1)
                last_close = float(df.loc[dates[last_idx]]["Close"])
                exit_price = last_close * (1 - cost_bps)

            pnl = (exit_price - entry_price) * size

            trade_date = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)
            result.trades.append(
                Trade(ticker, trade_date, direction, entry_price, exit_price,
                      size, pnl, active_mode),
            )
            equity += pnl

            month = trade_date[:7]
            result.monthly_pnl[month] = result.monthly_pnl.get(month, 0) + pnl

            # Skip ahead past hold period to avoid overlapping trades
            i += max_hold + 1
            continue

            i += 1  # noqa: E501 -- unreachable but kept for clarity

        # end while

    return result


# ---------------------------------------------------------------
# Solver
# ---------------------------------------------------------------
def solve(capital: float = 100_000):
    data = fetch_data()
    if len(data) < 3:
        print("Insufficient data")
        return

    keys = list(GRID.keys())
    values = list(GRID.values())
    combos = list(itertools.product(*values))
    total = len(combos)

    print(f"\n{'=' * 70}")
    print("CITS Success Equation Solver v2 -- CIS/BNF/Hybrid")
    print(f"{'=' * 70}")
    print(f"ETFs: {len(TICKERS)} tickers")
    print(f"Parameters: {total} combinations")
    print(f"Initial capital: Y{capital:,.0f}")
    print("Strategy modes: CIS (momentum) / BNF (mean-reversion) / Hybrid")
    print(f"NY-Nikkei signal: {'available' if HAS_NY_SIGNAL else 'N/A'}")
    print(f"Regime detection: {'available' if HAS_REGIME else 'N/A'}")
    print(f"{'=' * 70}\n")

    results: list[Result] = []
    for idx, combo in enumerate(combos):
        if (idx + 1) % 50 == 0 or idx == 0:
            print(f"  Progress: {idx + 1}/{total}")
        params = dict(zip(keys, combo))
        r = run_backtest(params, data, capital)
        if r.trade_count >= 5:
            results.append(r)

    results.sort(key=lambda r: r.consistency_score, reverse=True)

    # === RESULTS ===
    print(f"\n{'=' * 70}")
    print("Success Equation -- Solutions")
    print(f"{'=' * 70}")
    print(f"Valid patterns: {len(results)} / {total}")

    if not results:
        print("No patterns generated enough trades")
        return

    # Top 10
    print(f"\n{'~' * 100}")
    print(
        f"{'#':>3} {'Mode':>6} {'PnL':>9} {'PnL%':>6} {'Trades':>6} {'WR':>5} "
        f"{'PF':>5} {'MoWR':>6} {'AvgMo':>7} {'Worst':>7} {'Score':>6}",
    )
    print(f"{'~' * 100}")

    for rank, r in enumerate(results[:10], 1):
        pnl_pct = r.total_pnl / capital * 100
        pf = min(r.profit_factor, 99.9)
        mode_label = r.params["mode"].upper()
        print(
            f"{rank:>3} {mode_label:>6} Y{r.total_pnl:>+8,.0f} {pnl_pct:>+5.1f}% "
            f"{r.trade_count:>5} {r.win_rate:>4.0f}% {pf:>5.2f} "
            f"{r.monthly_win_rate:>5.0f}% {r.avg_monthly_return_pct:>+6.2f}% "
            f"{r.worst_month_pct:>+6.2f}% {r.consistency_score:>5.1f}",
        )

    # Detailed #1
    best = results[0]
    print(f"\n{'=' * 70}")
    mode_names = {"cis": "CIS (Momentum)", "bnf": "BNF (Mean Reversion)", "hybrid": "Hybrid"}
    print(f"BEST: {mode_names.get(best.params['mode'], best.params['mode'])}")
    print(f"{'=' * 70}")
    print(f"Total PnL: Y{best.total_pnl:+,.0f} ({best.total_pnl / capital * 100:+.2f}%)")
    print(f"Trades: {best.trade_count}  WinRate: {best.win_rate:.1f}%  PF: {best.profit_factor:.2f}")
    print(f"Monthly WR: {best.monthly_win_rate:.0f}%")
    print(f"Avg Monthly Return: {best.avg_monthly_return_pct:+.2f}%")
    print(f"Worst Month: {best.worst_month_pct:+.2f}%")

    # Mode breakdown
    mb = best.mode_breakdown
    if mb:
        print(f"\nMode breakdown: {mb}")

    print("\nParameters:")
    for k, v in best.params.items():
        if k != "capital":
            print(f"  {k}: {v}")

    # Ticker breakdown
    print("\nTicker breakdown:")
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
        print(f"  {tk}: {ts['count']} trades WR {wr:.0f}% PnL Y{ts['pnl']:+,.0f}")

    # Monthly breakdown
    print("\nMonthly PnL:")
    compound = capital
    print(f"  {'Month':>8} {'Trades':>6} {'PnL':>10} {'Return':>7} {'Balance':>12}")
    print(f"  {'~' * 50}")
    for m in sorted(best.monthly_pnl.keys()):
        pnl = best.monthly_pnl[m]
        monthly_trades = sum(1 for t in best.trades if t.date.startswith(m))
        ret_pct = pnl / capital * 100
        compound += compound * (pnl / capital)
        hit = "(*)" if ret_pct >= 5.0 else ("(+)" if ret_pct > 0 else "(-)")
        print(
            f"  {m} {monthly_trades:>6} Y{pnl:>+9,.0f} {ret_pct:>+6.2f}% "
            f"Y{compound:>11,.0f} {hit}",
        )

    # Compound growth simulation
    print(f"\n{'=' * 70}")
    print(f"Compound simulation (monthly {best.avg_monthly_return_pct:.2f}%)")
    print(f"{'=' * 70}")
    avg_mr = best.avg_monthly_return_pct / 100
    bal = capital
    for year in range(1, 11):
        for _ in range(12):
            bal *= (1 + avg_mr)
        monthly_income = bal * avg_mr
        print(f"  Year {year}: Y{bal:>12,.0f}  Monthly: Y{monthly_income:>10,.0f}")
        if monthly_income >= 500_000:
            print("  -> Monthly income Y500K achieved!")
            break

    # Success equation summary
    print(f"\n{'=' * 70}")
    print("Success Equation")
    print(f"{'=' * 70}")
    tickers_used = ", ".join(tk for tk in ticker_stats.keys())
    avg_trades_mo = best.trade_count / max(len(best.monthly_pnl), 1)
    print(f"""
  Mode: {mode_names.get(best.params['mode'], best.params['mode'])}
  Tickers: {tickers_used}
  stop: {best.params['stop_pct']}%
  target: {best.params['target_pct']}%
  hold_days: {best.params['hold_days']}
  risk/trade: {best.params['risk_pct'] * 100}%
  NY signal: {best.params['use_ny_signal']}
  Volume confirm: {best.params['use_volume_confirm']}

  WinRate {best.win_rate:.0f}% x PF {best.profit_factor:.2f} x {avg_trades_mo:.1f} trades/mo
  = Monthly {best.avg_monthly_return_pct:+.2f}%
""")

    # Reality check
    target_gap = 5.0 - best.avg_monthly_return_pct
    if target_gap > 0:
        print(f"  Gap to 5%/mo target: {target_gap:.2f}%")
        print("  -> Increase capital or leverage ETF (1570) weight")
    else:
        print("  (*) Monthly 5% target achieved!")


def main():
    parser = argparse.ArgumentParser(description="CITS Success Equation Solver v2")
    parser.add_argument("--capital", type=float, default=100_000)
    args = parser.parse_args()
    solve(capital=args.capital)


if __name__ == "__main__":
    main()
