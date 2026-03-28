"""CITS Strategy Optimizer — exhaustive parameter sweep.

Runs thousands of parameter combinations against historical data
to find the optimal trading configuration.

Usage:
    python -m cits.scripts.optimize --capital 100000 --period 6mo
    python -m cits.scripts.optimize --capital 100000 --period 1y --top 20
"""

from __future__ import annotations

import argparse
import itertools
import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------
# Parameter grid
# ---------------------------------------------------------------

PARAM_GRID = {
    # Intraday momentum
    "im_confidence_threshold": [0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.5],
    "im_magnitude_threshold": [0.02, 0.05, 0.08, 0.1, 0.15, 0.2],

    # Premarket trio
    "pm_min_aligned": [1, 2, 3],
    "pm_nkd_band": [0.05, 0.1, 0.2, 0.3],
    "pm_usdjpy_band": [0.05, 0.1, 0.2, 0.3],

    # Overnight reversal
    "overnight_gap_threshold": [0.5, 0.8, 1.0, 1.5, 2.0, 2.5, 3.0],

    # Strategy enable/disable (original)
    "enable_im": [True, False],
    "enable_pm": [True, False],
    "enable_or": [True, False],

    # Strategy enable/disable (new)
    "enable_trend_mom": [True, False],
    "enable_mean_rev": [True, False],
    "enable_vol_breakout": [True, False],

    # New strategy parameters
    "mr_entry_z": [1.5, 2.0, 2.5, 3.0],
    "mr_period": [10, 15, 20],
    "trend_short_period": [3, 5, 8, 10],
    "trend_long_period": [10, 20, 30, 40],
    "vol_min_ratio": [0.8, 1.0, 1.2, 1.5],

    # Risk
    "risk_per_trade": [0.01, 0.02, 0.03, 0.05],
    "stop_distance_pct": [0.5, 1.0, 1.5, 2.0, 3.0],

    # Circuit breaker
    "max_consecutive_losses": [3, 5, 7, 10],
}

# Reduce grid for initial fast sweep (most impactful params only)
# Ultra-fast grid: mean_reversion variants with filters
FAST_GRID = {
    "im_confidence_threshold": [0.25],
    "pm_min_aligned": [2],
    "overnight_gap_threshold": [1.0],
    "enable_im": [False],
    "enable_pm": [False],
    "enable_or": [False],
    "enable_trend_mom": [False],
    "enable_mean_rev": [True],
    "enable_vol_breakout": [False],
    "mr_entry_z": [2.0, 2.5, 3.0],
    "mr_period": [15, 20],
    "mr_require_volume": [True, False],     # volume confirmation filter
    "mr_require_trend_align": [True, False], # trend must be recovering
    "trend_short_period": [5],
    "trend_long_period": [20],
    "vol_min_ratio": [1.0],
    "risk_per_trade": [0.02],
    "stop_distance_pct": [2.0, 3.0],
    "max_consecutive_losses": [10],
}


# ---------------------------------------------------------------
# Data fetcher
# ---------------------------------------------------------------

TICKERS = ["7203", "8306", "6758", "9984"]
MARKET_SYMBOLS = ["^VIX", "USDJPY=X", "^N225"]


def fetch_all_data(
    tickers: list[str],
    period: str,
) -> dict[str, pd.DataFrame]:
    """Fetch historical data once for all optimizations."""
    end = date.today()
    period_days = {"3mo": 90, "6mo": 180, "1y": 365, "2y": 730}
    days = period_days.get(period, 180)
    start = end - timedelta(days=days + 30)

    data: dict[str, pd.DataFrame] = {}

    all_symbols = [f"{t}.T" for t in tickers] + MARKET_SYMBOLS
    print(f"データ取得中: {', '.join(all_symbols)}")

    for symbol in all_symbols:
        key = symbol.replace(".T", "") if symbol.endswith(".T") else symbol
        try:
            df = yf.download(
                symbol,
                start=start.isoformat(),
                end=end.isoformat(),
                auto_adjust=True,
                progress=False,
            )
            if df is not None and not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                data[key] = df
                print(f"  ✅ {symbol}: {len(df)}行")
            else:
                print(f"  ❌ {symbol}: データなし")
        except Exception as exc:
            print(f"  ❌ {symbol}: {exc}")

    return data


# ---------------------------------------------------------------
# Fast backtest (no BacktestEngine overhead)
# ---------------------------------------------------------------

@dataclass
class TradeResult:
    pnl: float
    strategy: str
    ticker: str
    trade_date: str


@dataclass
class OptResult:
    params: dict
    total_pnl: float = 0.0
    trade_count: int = 0
    wins: int = 0
    losses: int = 0
    max_drawdown: float = 0.0
    sharpe: float = 0.0
    profit_factor: float = 0.0
    pnl_by_strategy: dict = field(default_factory=dict)

    @property
    def win_rate(self) -> float:
        return self.wins / self.trade_count * 100 if self.trade_count > 0 else 0.0

    @property
    def pnl_pct(self) -> float:
        cap = self.params.get("capital", 100_000)
        return self.total_pnl / cap * 100


def run_single_backtest(
    params: dict,
    data: dict[str, pd.DataFrame],
    tickers: list[str],
    capital: float,
) -> OptResult:
    """Run a single fast backtest with given parameters."""
    from cits.core.signals.intraday_momentum import compute_intraday_momentum
    from cits.core.signals.mean_reversion import compute_mean_reversion
    from cits.core.signals.premarket_trio import compute_premarket_trio
    from cits.core.signals.trend_filter import compute_trend_filter
    from cits.core.signals.volume_confirm import compute_volume_confirmation

    lot_size = 1 if capital < 500_000 else 100
    equity = capital
    trades: list[TradeResult] = []
    equity_curve = [capital]
    consecutive_losses = 0
    max_consec = params.get("max_consecutive_losses", 5)
    risk_pct = params.get("risk_per_trade", 0.02)
    stop_dist_pct = params.get("stop_distance_pct", 1.0) / 100.0

    # Slippage + spread cost
    cost_bps = 5.0 + 1.5  # slippage + half spread
    cost_mult = cost_bps / 10000

    # Historical price/volume per ticker for new signal modules
    closes_history: dict[str, list[float]] = defaultdict(list)
    volumes_history: dict[str, list[float]] = defaultdict(list)

    for ticker in tickers:
        df = data.get(ticker)
        if df is None:
            continue

        vix_df = data.get("^VIX")
        usdjpy_df = data.get("USDJPY=X")
        n225_df = data.get("^N225")

        dates = sorted(df.index)

        # Reset history for each ticker
        closes_history[ticker] = []
        volumes_history[ticker] = []

        for i in range(1, len(dates)):
            dt = dates[i]
            prev_dt = dates[i - 1]

            row = df.loc[dt]
            prev_row = df.loc[prev_dt]

            open_price = float(row["Open"])
            close_price = float(row["Close"])
            prev_close = float(prev_row["Close"])
            volume = float(row.get("Volume", 0))
            prev_volume = float(prev_row.get("Volume", 1)) or 1

            if open_price <= 0 or close_price <= 0 or prev_close <= 0:
                # Still record history for signal lookback
                closes_history[ticker].append(close_price if close_price > 0 else 0)
                volumes_history[ticker].append(volume)
                continue

            # Build historical arrays for new signal modules
            closes_history[ticker].append(prev_close)  # append prev day close first
            volumes_history[ticker].append(prev_volume)

            # Circuit breaker: consecutive losses
            if consecutive_losses >= max_consec:
                consecutive_losses = 0  # Reset each day attempt
                continue

            # VIX data
            vix_level = 20.0
            vix_change = 0.0
            if vix_df is not None and dt in vix_df.index:
                vix_level = float(vix_df.loc[dt]["Close"])
                vix_open = float(vix_df.loc[dt].get("Open", vix_level))
                if vix_open > 0:
                    vix_change = (vix_level - vix_open) / vix_open * 100

            # USD/JPY change
            usdjpy_change = 0.0
            if usdjpy_df is not None:
                uj_rows = usdjpy_df[usdjpy_df.index <= dt]
                if len(uj_rows) >= 2:
                    curr = float(uj_rows["Close"].iloc[-1])
                    prev = float(uj_rows["Close"].iloc[-2])
                    if prev > 0:
                        usdjpy_change = (curr - prev) / prev * 100

            # N225 change (proxy CME futures)
            nkd_change = 0.0
            if n225_df is not None:
                n_rows = n225_df[n225_df.index <= dt]
                if len(n_rows) >= 2:
                    curr = float(n_rows["Close"].iloc[-1])
                    prev = float(n_rows["Close"].iloc[-2])
                    if prev > 0:
                        nkd_change = (curr - prev) / prev * 100

            vol_ratio = volume / prev_volume if prev_volume > 0 else 1.0
            trade_date = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)

            # Position sizing
            risk_amount = equity * risk_pct
            stop_distance = open_price * stop_dist_pct
            if stop_distance <= 0:
                continue
            raw_size = int(risk_amount / stop_distance)
            trade_size = max(raw_size // lot_size * lot_size, lot_size)
            notional = trade_size * open_price
            if notional > equity * 0.9:
                trade_size = max(int(equity * 0.9 / open_price / lot_size) * lot_size, lot_size)
                notional = trade_size * open_price
            if notional > equity:
                continue

            day_trades: list[TradeResult] = []

            # --- Strategy 1: Intraday Momentum ---
            if params.get("enable_im", True):
                im_signal = compute_intraday_momentum(
                    prev_close=prev_close,
                    price_at_930=open_price,
                    avg_volume_ratio=vol_ratio,
                    nikkei_vi=vix_level,
                )
                im_thresh = params.get("im_confidence_threshold", 0.3)
                if im_signal.direction != 0 and im_signal.confidence >= im_thresh:
                    if im_signal.direction > 0:
                        entry = open_price * (1 + cost_mult)
                        exit_ = close_price * (1 - cost_mult)
                        pnl = (exit_ - entry) * trade_size
                    else:
                        entry = open_price * (1 - cost_mult)
                        exit_ = close_price * (1 + cost_mult)
                        pnl = (entry - exit_) * trade_size
                    day_trades.append(TradeResult(pnl, "intraday_momentum", ticker, trade_date))

            # --- Strategy 2: Overnight Reversal ---
            if params.get("enable_or", True):
                gap_pct = (open_price - prev_close) / prev_close * 100
                gap_thresh = params.get("overnight_gap_threshold", 1.0)
                if abs(gap_pct) >= gap_thresh:
                    direction = -1 if gap_pct > 0 else 1
                    if direction > 0:
                        entry = open_price * (1 + cost_mult)
                        exit_ = close_price * (1 - cost_mult)
                        pnl = (exit_ - entry) * trade_size
                    else:
                        entry = open_price * (1 - cost_mult)
                        exit_ = close_price * (1 + cost_mult)
                        pnl = (entry - exit_) * trade_size
                    day_trades.append(TradeResult(pnl, "overnight_reversal", ticker, trade_date))

            # --- Strategy 3: Premarket Trio ---
            if params.get("enable_pm", True):
                pm_signal = compute_premarket_trio(
                    nkd_change_pct=nkd_change,
                    usdjpy_change_pct=usdjpy_change,
                    vix_level=vix_level,
                    vix_change_pct=vix_change,
                )
                pm_min = params.get("pm_min_aligned", 2)
                if pm_signal.direction != 0 and pm_signal.signals_aligned >= pm_min:
                    if pm_signal.direction > 0:
                        entry = open_price * (1 + cost_mult)
                        exit_ = close_price * (1 - cost_mult)
                        pnl = (exit_ - entry) * trade_size
                    else:
                        entry = open_price * (1 - cost_mult)
                        exit_ = close_price * (1 + cost_mult)
                        pnl = (entry - exit_) * trade_size
                    day_trades.append(TradeResult(pnl, "premarket_trio", ticker, trade_date))

            # --- Strategy 4: Trend Momentum (trend filter + IM combined) ---
            closes_list = closes_history[ticker]
            volumes_list = volumes_history[ticker]

            trend_signal = None  # cache for reuse in vol_breakout
            if params.get("enable_trend_mom", True):
                trend_short_p = params.get("trend_short_period", 5)
                trend_long_p = params.get("trend_long_period", 20)
                trend_signal = compute_trend_filter(
                    closes_list,
                    short_period=trend_short_p,
                    long_period=trend_long_p,
                )
                if trend_signal.direction != 0:
                    im_signal = compute_intraday_momentum(
                        prev_close=prev_close,
                        price_at_930=open_price,
                        avg_volume_ratio=vol_ratio,
                        nikkei_vi=vix_level,
                    )
                    im_thresh = params.get("im_confidence_threshold", 0.3)
                    if (
                        im_signal.direction == trend_signal.direction
                        and im_signal.confidence >= im_thresh
                    ):
                        d = trend_signal.direction
                        if d > 0:
                            entry = open_price * (1 + cost_mult)
                            exit_ = close_price * (1 - cost_mult)
                            pnl = (exit_ - entry) * trade_size
                        else:
                            entry = open_price * (1 - cost_mult)
                            exit_ = close_price * (1 + cost_mult)
                            pnl = (entry - exit_) * trade_size
                        day_trades.append(
                            TradeResult(pnl, "trend_momentum", ticker, trade_date)
                        )

            # --- Strategy 5: Mean Reversion (Bollinger Band) ---
            if params.get("enable_mean_rev", True) and vix_level > 20:
                mr_period = params.get("mr_period", 20)
                mr_entry_z = params.get("mr_entry_z", 2.0)
                mr_signal = compute_mean_reversion(
                    closes_list,
                    period=mr_period,
                    entry_z=mr_entry_z,
                )
                if mr_signal.direction != 0 and mr_signal.confidence >= 0.3:
                    # Optional filter: volume confirmation
                    mr_pass = True
                    if params.get("mr_require_volume", False):
                        vol_confirm = compute_volume_confirmation(
                            closes_list,
                            volumes_list,
                            mr_signal.direction,
                            min_ratio=params.get("vol_min_ratio", 1.0),
                        )
                        if not vol_confirm.confirmed:
                            mr_pass = False

                    # Optional filter: trend recovering (price moving back toward mean)
                    if mr_pass and params.get("mr_require_trend_align", False):
                        if len(closes_list) >= 3:
                            # Price should be moving back toward mean
                            prev2 = closes_list[-3]
                            prev1 = closes_list[-2]
                            curr = closes_list[-1]
                            if mr_signal.direction > 0:
                                # Buying oversold: price should be recovering (going up)
                                mr_pass = curr > prev1 or prev1 > prev2
                            else:
                                # Selling overbought: price should be falling
                                mr_pass = curr < prev1 or prev1 < prev2

                    if mr_pass:
                        d = mr_signal.direction
                        if d > 0:
                            entry = open_price * (1 + cost_mult)
                            exit_ = close_price * (1 - cost_mult)
                            pnl = (exit_ - entry) * trade_size
                        else:
                            entry = open_price * (1 - cost_mult)
                            exit_ = close_price * (1 + cost_mult)
                            pnl = (entry - exit_) * trade_size
                        day_trades.append(
                            TradeResult(pnl, "mean_reversion", ticker, trade_date)
                        )

            # --- Strategy 6: Volume Breakout (trend + volume confirm) ---
            if params.get("enable_vol_breakout", True):
                # Reuse trend_signal if already computed, else compute now
                if trend_signal is None:
                    trend_short_p = params.get("trend_short_period", 5)
                    trend_long_p = params.get("trend_long_period", 20)
                    trend_signal = compute_trend_filter(
                        closes_list,
                        short_period=trend_short_p,
                        long_period=trend_long_p,
                    )
                if trend_signal.direction != 0:
                    vol_confirm = compute_volume_confirmation(
                        closes_list,
                        volumes_list,
                        trend_signal.direction,
                        min_ratio=params.get("vol_min_ratio", 1.0),
                    )
                    if vol_confirm.confirmed:
                        d = trend_signal.direction
                        if d > 0:
                            entry = open_price * (1 + cost_mult)
                            exit_ = close_price * (1 - cost_mult)
                            pnl = (exit_ - entry) * trade_size
                        else:
                            entry = open_price * (1 - cost_mult)
                            exit_ = close_price * (1 + cost_mult)
                            pnl = (entry - exit_) * trade_size
                        day_trades.append(
                            TradeResult(pnl, "volume_breakout", ticker, trade_date)
                        )

            # Update equity and stats
            for t in day_trades:
                equity += t.pnl
                trades.append(t)
                equity_curve.append(equity)
                if t.pnl < 0:
                    consecutive_losses += 1
                else:
                    consecutive_losses = 0

    # Build result
    result = OptResult(params={**params, "capital": capital})
    result.trade_count = len(trades)

    if result.trade_count == 0:
        return result

    result.wins = sum(1 for t in trades if t.pnl > 0)
    result.losses = sum(1 for t in trades if t.pnl <= 0)
    result.total_pnl = sum(t.pnl for t in trades)

    # Profit factor
    gross_profit = sum(t.pnl for t in trades if t.pnl > 0)
    gross_loss = abs(sum(t.pnl for t in trades if t.pnl < 0))
    result.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Max drawdown
    peak = capital
    max_dd = 0.0
    for eq in equity_curve:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak * 100 if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
    result.max_drawdown = max_dd

    # Sharpe (simplified daily)
    if len(equity_curve) > 1:
        returns = []
        for j in range(1, len(equity_curve)):
            r = (equity_curve[j] - equity_curve[j - 1]) / equity_curve[j - 1]
            returns.append(r)
        if returns:
            import statistics
            mean_r = statistics.mean(returns)
            std_r = statistics.stdev(returns) if len(returns) > 1 else 1.0
            result.sharpe = round((mean_r / std_r) * (252 ** 0.5), 2) if std_r > 0 else 0.0

    # PnL by strategy
    strat_pnl: dict[str, float] = {}
    strat_count: dict[str, int] = {}
    strat_wins: dict[str, int] = {}
    for t in trades:
        strat_pnl[t.strategy] = strat_pnl.get(t.strategy, 0) + t.pnl
        strat_count[t.strategy] = strat_count.get(t.strategy, 0) + 1
        if t.pnl > 0:
            strat_wins[t.strategy] = strat_wins.get(t.strategy, 0) + 1

    result.pnl_by_strategy = {
        s: {
            "pnl": round(strat_pnl[s], 0),
            "count": strat_count[s],
            "win_rate": round(strat_wins.get(s, 0) / strat_count[s] * 100, 1),
        }
        for s in strat_pnl
    }

    return result


# ---------------------------------------------------------------
# Optimizer
# ---------------------------------------------------------------

def generate_param_combos(grid: dict) -> list[dict]:
    """Generate all parameter combinations from grid."""
    keys = list(grid.keys())
    values = list(grid.values())
    combos = []
    for combo in itertools.product(*values):
        params = dict(zip(keys, combo))
        # Skip if all strategies disabled
        all_strat_keys = ["im", "pm", "or", "trend_mom", "mean_rev", "vol_breakout"]
        if not any(params.get(f"enable_{s}", True) for s in all_strat_keys):
            continue
        combos.append(params)
    return combos


def run_optimization(
    capital: float = 100_000,
    period: str = "6mo",
    top_n: int = 10,
    fast: bool = True,
) -> list[OptResult]:
    """Run full parameter optimization."""
    grid = FAST_GRID if fast else PARAM_GRID
    combos = generate_param_combos(grid)
    total = len(combos)

    print(f"\n{'=' * 60}")
    print("CITS パラメータ最適化")
    print(f"{'=' * 60}")
    print(f"パラメータ組み合わせ数: {total:,}")
    print(f"初期資金: ¥{capital:,.0f}")
    print(f"期間: {period}")
    print(f"モード: {'高速スイープ' if fast else 'フルスイープ'}")
    print(f"{'=' * 60}\n")

    # Fetch data once
    data = fetch_all_data(TICKERS, period)
    if len(data) < 2:
        print("エラー: 十分なデータが取得できませんでした")
        return []

    print(f"\n最適化実行中... ({total:,}パターン)")

    results: list[OptResult] = []
    for i, params in enumerate(combos):
        if (i + 1) % 100 == 0 or i == 0:
            print(f"  進捗: {i + 1}/{total} ({(i + 1) / total * 100:.0f}%)")

        result = run_single_backtest(params, data, TICKERS, capital)
        if result.trade_count > 0:
            results.append(result)

    # Sort by total PnL
    results.sort(key=lambda r: r.total_pnl, reverse=True)

    # Display results
    print(f"\n{'=' * 60}")
    print(f"最適化結果 TOP {top_n}")
    print(f"{'=' * 60}")
    print(f"テスト済み: {total:,}パターン")
    print(f"取引発生: {len(results):,}パターン")

    if not results:
        print("取引が発生したパターンがありません")
        return []

    # Top results
    print(f"\n{'─' * 80}")
    print(f"{'#':>3} {'損益':>10} {'損益%':>7} {'取引数':>6} {'勝率':>6} {'PF':>6} "
          f"{'DD':>6} {'Sharpe':>7} 戦略設定")
    print(f"{'─' * 80}")

    for rank, r in enumerate(results[:top_n], 1):
        strategies = []
        if r.params.get("enable_im", True):
            strategies.append("IM")
        if r.params.get("enable_pm", True):
            strategies.append("PM")
        if r.params.get("enable_or", True):
            strategies.append("OR")
        if r.params.get("enable_trend_mom", True):
            strategies.append("TM")
        if r.params.get("enable_mean_rev", True):
            strategies.append("MR")
        if r.params.get("enable_vol_breakout", True):
            strategies.append("VB")
        strat_str = "+".join(strategies)

        print(
            f"{rank:>3} ¥{r.total_pnl:>+9,.0f} {r.pnl_pct:>+6.1f}% "
            f"{r.trade_count:>5} {r.win_rate:>5.1f}% {r.profit_factor:>5.2f} "
            f"{r.max_drawdown:>5.1f}% {r.sharpe:>6.2f}  {strat_str}"
        )

    # Detailed top 3
    print(f"\n{'=' * 60}")
    print("TOP 3 詳細")
    print(f"{'=' * 60}")

    for rank, r in enumerate(results[:3], 1):
        print(f"\n--- #{rank} ---")
        print(f"損益: ¥{r.total_pnl:+,.0f} ({r.pnl_pct:+.2f}%)")
        print(f"取引数: {r.trade_count}  勝率: {r.win_rate:.1f}%  PF: {r.profit_factor:.2f}")
        print(f"最大DD: {r.max_drawdown:.2f}%  Sharpe: {r.sharpe:.2f}")
        print("パラメータ:")
        for k, v in r.params.items():
            if k != "capital":
                print(f"  {k}: {v}")
        print("戦略別:")
        for s, info in r.pnl_by_strategy.items():
            print(f"  {s}: {info['count']}取引 勝率{info['win_rate']:.0f}% PnL ¥{info['pnl']:+,.0f}")

    # Worst results for comparison
    print(f"\n{'=' * 60}")
    print("WORST 3（参考: 最悪パターン）")
    print(f"{'=' * 60}")
    for rank, r in enumerate(results[-3:], 1):
        strategies = []
        if r.params.get("enable_im", True):
            strategies.append("IM")
        if r.params.get("enable_pm", True):
            strategies.append("PM")
        if r.params.get("enable_or", True):
            strategies.append("OR")
        if r.params.get("enable_trend_mom", True):
            strategies.append("TM")
        if r.params.get("enable_mean_rev", True):
            strategies.append("MR")
        if r.params.get("enable_vol_breakout", True):
            strategies.append("VB")
        print(
            f"  ¥{r.total_pnl:>+9,.0f} {r.pnl_pct:>+6.1f}% "
            f"取引{r.trade_count} 勝率{r.win_rate:.0f}% PF{r.profit_factor:.2f} "
            f"{'+'.join(strategies)}"
        )

    # Save results
    output_dir = Path(__file__).parent.parent / "logs" / "optimization"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"opt_{date.today().isoformat()}.json"

    save_data = {
        "meta": {
            "capital": capital,
            "period": period,
            "total_combos": total,
            "date": date.today().isoformat(),
        },
        "top_results": [
            {
                "rank": i + 1,
                "params": r.params,
                "total_pnl": round(r.total_pnl, 0),
                "pnl_pct": round(r.pnl_pct, 2),
                "trade_count": r.trade_count,
                "win_rate": round(r.win_rate, 1),
                "profit_factor": round(r.profit_factor, 2),
                "max_drawdown": round(r.max_drawdown, 2),
                "sharpe": r.sharpe,
                "pnl_by_strategy": r.pnl_by_strategy,
            }
            for i, r in enumerate(results[:20])
        ],
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)
    print(f"\n結果保存: {output_file}")

    # Generate recommended config
    if results:
        best = results[0]
        print(f"\n{'=' * 60}")
        print("推奨設定（config.ymlに反映可能）")
        print(f"{'=' * 60}")
        print("""
trading:
  mode: paper
  strategies:""")
        if best.params.get("enable_im", True):
            print(f"    - intraday_momentum  # confidence >= {best.params.get('im_confidence_threshold', 0.3)}")
        if best.params.get("enable_pm", True):
            print(f"    - premarket_trio     # min_aligned >= {best.params.get('pm_min_aligned', 2)}")
        if best.params.get("enable_or", True):
            print(f"    - overnight_reversal # gap >= {best.params.get('overnight_gap_threshold', 1.0)}%")
        if best.params.get("enable_trend_mom", True):
            print(f"    - trend_momentum     # short={best.params.get('trend_short_period', 5)} long={best.params.get('trend_long_period', 20)}")
        if best.params.get("enable_mean_rev", True):
            print(f"    - mean_reversion     # period={best.params.get('mr_period', 20)} entry_z={best.params.get('mr_entry_z', 2.0)}")
        if best.params.get("enable_vol_breakout", True):
            print(f"    - volume_breakout    # min_ratio={best.params.get('vol_min_ratio', 1.0)}")
        print(f"""
risk:
  risk_per_trade: {best.params.get('risk_per_trade', 0.02)}
  stop_distance_pct: {best.params.get('stop_distance_pct', 1.0)}
  max_consecutive_losses: {best.params.get('max_consecutive_losses', 5)}
""")

    return results


# ---------------------------------------------------------------
# CLI
# ---------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog="optimize",
        description="CITS パラメータ最適化エンジン",
    )
    parser.add_argument(
        "--capital", type=float, default=100_000,
        help="初期資金 (default: ¥100,000)",
    )
    parser.add_argument(
        "--period", type=str, default="6mo",
        choices=["3mo", "6mo", "1y", "2y"],
        help="バックテスト期間 (default: 6mo)",
    )
    parser.add_argument(
        "--top", type=int, default=10,
        help="上位表示数 (default: 10)",
    )
    parser.add_argument(
        "--full", action="store_true",
        help="フルスイープ（数万パターン、時間がかかる）",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    run_optimization(
        capital=args.capital,
        period=args.period,
        top_n=args.top,
        fast=not args.full,
    )


if __name__ == "__main__":
    main()
