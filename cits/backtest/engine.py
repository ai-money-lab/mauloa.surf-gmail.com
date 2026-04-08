"""Backtest Engine — runs STRATEGY_PLAYBOOK strategies against historical data.

Uses daily OHLCV as proxy (intraday data requires kabuStation).
Strategies:
  1. Intraday Momentum: Open as 9:30 proxy, entry at Open, exit at Close
  2. Overnight Reversal: large gap reversal, entry at Open, exit at Close
  3. Premarket Trio: CME/USDJPY/VIX alignment, entry at Open, exit at Close
  4. CIS Momentum: 20-day breakout + volume 1.5x, hold 5 days (swing)
  5. Kei-kun: 60-day sideways breakout, exit on 7 new highs (swing)

All trades use 100-share lots (売買単位) and apply execution costs.
"""

from __future__ import annotations

import logging
import math
import tempfile
from dataclasses import dataclass, field
import pandas as pd

from cits.core.chart_exit import compute_exit_score
from cits.core.signals.intraday_momentum import compute_intraday_momentum
from cits.core.signals.premarket_trio import compute_premarket_trio
from cits.core.signals.regime_filter import compute_regime
from cits.risk.circuit_breaker import CircuitBreaker
from cits.risk.position_sizer import PositionSizer
from cits.risk.win_rate_engine import WinRateEngine

logger = logging.getLogger(__name__)

LOT_SIZE_STANDARD = 100  # 東証売買単位（単元株）
LOT_SIZE_PETIT = 1       # プチ株（単元未満株）


# ------------------------------------------------------------------
# Result dataclass
# ------------------------------------------------------------------

@dataclass
class BacktestResult:
    """Holds all backtest output metrics."""

    initial_capital: float = 0.0
    final_equity: float = 0.0
    total_return_pct: float = 0.0
    annualized_return_pct: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    trading_days: int = 0
    per_strategy: dict = field(default_factory=dict)
    equity_curve: list[dict] = field(default_factory=list)
    trades: list[dict] = field(default_factory=list)

    def summary(self) -> str:
        """Print formatted summary in Japanese."""
        lines = [
            "",
            "=" * 60,
            "  バックテスト結果",
            "=" * 60,
            f"  初期資金:         ¥{self.initial_capital:>14,.0f}",
            f"  最終資金:         ¥{self.final_equity:>14,.0f}",
            f"  損益:             ¥{self.total_pnl:>+14,.0f} ({self.total_return_pct:+.2f}%)",
            f"  年率リターン:       {self.annualized_return_pct:+.2f}%",
            f"  シャープレシオ:     {self.sharpe_ratio:.2f}",
            f"  ソルティノレシオ:   {self.sortino_ratio:.2f}",
            f"  最大ドローダウン:   {self.max_drawdown_pct:.2f}%",
            "-" * 60,
            f"  取引数:           {self.total_trades}",
            f"  勝率:             {self.win_rate:.1f}%",
            f"  勝ちトレード:     {self.winning_trades}",
            f"  負けトレード:     {self.losing_trades}",
            f"  プロフィットファクター: {self.profit_factor:.2f}",
            f"  平均利益:         ¥{self.avg_win:>+,.0f}",
            f"  平均損失:         ¥{self.avg_loss:>+,.0f}",
            f"  取引日数:         {self.trading_days}",
        ]
        if self.per_strategy:
            lines.append("-" * 60)
            lines.append("  戦略別:")
            for name, stats in self.per_strategy.items():
                lines.append(
                    f"    {name:25s}  "
                    f"取引{stats['trades']:>3d}  "
                    f"勝率{stats['win_rate']:>5.1f}%  "
                    f"PnL ¥{stats['pnl']:>+,.0f}"
                )
        lines.append("=" * 60)
        return "\n".join(lines)


# ------------------------------------------------------------------
# Engine
# ------------------------------------------------------------------

class BacktestEngine:
    """Runs multi-strategy backtest on Japanese equities using daily OHLCV."""

    def __init__(
        self,
        initial_capital: float = 100_000,
        risk_per_trade: float = 0.02,
        max_position_ratio: float | None = None,
        slippage_bps: float = 5.0,
        spread_bps: float = 3.0,
        overnight_gap_threshold: float = 1.0,
    ) -> None:
        self.initial_capital = initial_capital
        self.risk_per_trade = risk_per_trade
        # Small accounts (<¥1M) need a higher ratio to afford 100-share lots
        if max_position_ratio is not None:
            self.max_position_ratio = max_position_ratio
        else:
            self.max_position_ratio = 0.9 if initial_capital < 1_000_000 else 0.1
        self.slippage_bps = slippage_bps
        self.spread_bps = spread_bps
        self.overnight_gap_threshold = overnight_gap_threshold
        # Small accounts use プチ株 (1-share lots) since 100-share lots are too expensive
        self.lot_size = LOT_SIZE_PETIT if initial_capital < 500_000 else LOT_SIZE_STANDARD

        self.sizer = PositionSizer(
            account_size=initial_capital,
            max_risk_per_trade=risk_per_trade,
            max_position_ratio=self.max_position_ratio,
        )
        self.breaker = CircuitBreaker(
            max_daily_loss=initial_capital * 0.02,
            max_consecutive_losses=3,
            max_daily_trades=10,
            volatility_threshold=30.0,
        )

        # Use temp DB to avoid polluting live data
        self._tmp_dir = tempfile.mkdtemp(prefix="cits_bt_")
        self.win_engine = WinRateEngine(
            min_trades=10,
            db_path=f"{self._tmp_dir}/bt_trades.db",
        )

    # ------------------------------------------------------------------
    # Data fetching
    # ------------------------------------------------------------------

    def _fetch_data(
        self,
        tickers: list[str],
        start_date: str,
        end_date: str,
    ) -> dict[str, pd.DataFrame]:
        """Fetch OHLCV + market data from yfinance."""
        import yfinance as yf

        data: dict[str, pd.DataFrame] = {}

        # Fetch individual tickers
        for ticker in tickers:
            symbol = f"{ticker}.T" if ticker.isdigit() else ticker
            logger.info("Fetching %s ...", symbol)
            df = yf.download(
                symbol, start=start_date, end=end_date,
                auto_adjust=True, progress=False,
            )
            if df is not None and not df.empty:
                # Flatten MultiIndex columns if present
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                data[ticker] = df

        # Fetch market indices
        for idx_symbol in ["^VIX", "USDJPY=X", "^N225"]:
            logger.info("Fetching %s ...", idx_symbol)
            df = yf.download(
                idx_symbol, start=start_date, end=end_date,
                auto_adjust=True, progress=False,
            )
            if df is not None and not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                data[idx_symbol] = df

        return data

    # ------------------------------------------------------------------
    # Execution cost
    # ------------------------------------------------------------------

    def _apply_cost(self, price: float, side: str) -> float:
        """Apply slippage + spread to get realistic fill price."""
        total_bps = self.slippage_bps + (self.spread_bps / 2)
        adj = price * total_bps / 10000
        if side == "buy":
            return round(price + adj, 2)
        return round(price - adj, 2)

    # ------------------------------------------------------------------
    # Single trade execution
    # ------------------------------------------------------------------

    def _execute_trade(
        self,
        signal_name: str,
        direction: int,
        ticker: str,
        open_price: float,
        close_price: float,
        trade_date: str,
        equity: float,
        vi_level: float,
    ) -> dict | None:
        """Simulate a single trade. Returns trade dict or None if skipped."""

        # Circuit breaker
        cb_result = self.breaker.check(
            portfolio={
                "daily_pnl": 0,
                "consecutive_losses": self.breaker.consecutive_losses,
                "daily_trade_count": self.breaker.daily_trade_count,
            },
            market_data={"volatility": vi_level, "date": trade_date},
        )
        if cb_result["action"] == "halt":
            return None

        # Regime-based size multiplier
        regime = compute_regime(vi_level, trade_date)
        size_mult = regime.position_size_multiplier

        if cb_result["action"] == "reduce":
            size_mult *= 0.5

        # Position sizing
        self.sizer.account_size = equity
        stop_distance = open_price * 0.01  # 1% default stop
        stop_loss = (
            open_price - stop_distance if direction > 0
            else open_price + stop_distance
        )
        sizing = self.sizer.calculate_size(
            entry_price=open_price,
            stop_loss=stop_loss,
        )
        raw_size = sizing["position_size"]
        lot = self.lot_size
        adjusted_size = max(int(raw_size * size_mult / lot) * lot, lot)

        # Check we can afford it
        notional = adjusted_size * open_price
        if notional > equity * self.max_position_ratio:
            adjusted_size = max(
                int(equity * self.max_position_ratio / open_price / lot) * lot,
                lot,
            )
            notional = adjusted_size * open_price

        if notional > equity:
            return None  # Not enough capital

        # Fill prices with costs
        if direction > 0:
            entry_fill = self._apply_cost(open_price, "buy")
            exit_fill = self._apply_cost(close_price, "sell")
            pnl = (exit_fill - entry_fill) * adjusted_size
        else:
            entry_fill = self._apply_cost(open_price, "sell")
            exit_fill = self._apply_cost(close_price, "buy")
            pnl = (entry_fill - exit_fill) * adjusted_size

        # Update circuit breaker state
        self.breaker.daily_trade_count += 1
        if pnl < 0:
            self.breaker.consecutive_losses += 1
        else:
            self.breaker.consecutive_losses = 0

        trade = {
            "date": trade_date,
            "ticker": ticker,
            "strategy": signal_name,
            "side": "buy" if direction > 0 else "sell",
            "size": adjusted_size,
            "entry_price": entry_fill,
            "exit_price": exit_fill,
            "pnl": round(pnl, 2),
            "symbol": ticker,
            "qty": adjusted_size,
        }

        self.win_engine.record_trade(trade)
        return trade

    # ------------------------------------------------------------------
    # Day runner
    # ------------------------------------------------------------------

    def _run_day(
        self,
        ticker: str,
        row: pd.Series,
        prev_row: pd.Series | None,
        vix_row: pd.Series | None,
        usdjpy_row: pd.Series | None,
        prev_usdjpy_row: pd.Series | None,
        n225_row: pd.Series | None,
        prev_n225_row: pd.Series | None,
        trade_date: str,
        equity: float,
    ) -> list[dict]:
        """Run all strategies for one ticker on one day."""
        trades: list[dict] = []

        if prev_row is None:
            return trades

        open_price = float(row["Open"])
        close_price = float(row["Close"])
        prev_close = float(prev_row["Close"])
        volume = float(row.get("Volume", 0))
        prev_volume = float(prev_row.get("Volume", 1)) or 1

        if open_price <= 0 or close_price <= 0 or prev_close <= 0:
            return trades

        # VIX level (proxy for 日経VI)
        vix_level = float(vix_row["Close"]) if vix_row is not None else 20.0

        # USD/JPY change
        usdjpy_change = 0.0
        if usdjpy_row is not None and prev_usdjpy_row is not None:
            prev_usd = float(prev_usdjpy_row["Close"])
            if prev_usd > 0:
                usdjpy_change = (float(usdjpy_row["Close"]) - prev_usd) / prev_usd * 100

        # N225 change (proxy for CME futures)
        nkd_change = 0.0
        if n225_row is not None and prev_n225_row is not None:
            prev_n225 = float(prev_n225_row["Close"])
            if prev_n225 > 0:
                nkd_change = (float(n225_row["Close"]) - prev_n225) / prev_n225 * 100

        vix_change = 0.0
        if vix_row is not None:
            vix_open = float(vix_row.get("Open", vix_level))
            if vix_open > 0:
                vix_change = (vix_level - vix_open) / vix_open * 100

        vol_ratio = volume / prev_volume if prev_volume > 0 else 1.0

        # --- Strategy 1: Intraday Momentum ---
        im_signal = compute_intraday_momentum(
            prev_close=prev_close,
            price_at_930=open_price,
            avg_volume_ratio=vol_ratio,
            nikkei_vi=vix_level,
        )
        if im_signal.direction != 0 and im_signal.confidence >= 0.3:
            trade = self._execute_trade(
                signal_name="intraday_momentum",
                direction=im_signal.direction,
                ticker=ticker,
                open_price=open_price,
                close_price=close_price,
                trade_date=trade_date,
                equity=equity,
                vi_level=vix_level,
            )
            if trade:
                trades.append(trade)
                equity += trade["pnl"]

        # --- Strategy 2: Overnight Reversal ---
        gap_pct = (open_price - prev_close) / prev_close * 100
        if abs(gap_pct) >= self.overnight_gap_threshold:
            reversal_dir = -1 if gap_pct > 0 else +1  # trade the reversal
            trade = self._execute_trade(
                signal_name="overnight_reversal",
                direction=reversal_dir,
                ticker=ticker,
                open_price=open_price,
                close_price=close_price,
                trade_date=trade_date,
                equity=equity,
                vi_level=vix_level,
            )
            if trade:
                trades.append(trade)
                equity += trade["pnl"]

        # --- Strategy 3: Premarket Trio ---
        pm_signal = compute_premarket_trio(
            nkd_change_pct=nkd_change,
            usdjpy_change_pct=usdjpy_change,
            vix_level=vix_level,
            vix_change_pct=vix_change,
        )
        if pm_signal.direction != 0 and pm_signal.signals_aligned >= 2:
            trade = self._execute_trade(
                signal_name="premarket_trio",
                direction=pm_signal.direction,
                ticker=ticker,
                open_price=open_price,
                close_price=close_price,
                trade_date=trade_date,
                equity=equity,
                vi_level=vix_level,
            )
            if trade:
                trades.append(trade)

        return trades

    # ------------------------------------------------------------------
    # CIS Momentum (swing: 20-day breakout + volume, hold 5 days)
    # ------------------------------------------------------------------

    def _run_cis_swing(
        self,
        ticker: str,
        df: pd.DataFrame,
        equity: float,
        stop_pct: float = 1.5,
        target_pct: float = 5.0,
        hold_days: int = 5,
    ) -> list[dict]:
        """CIS式: 20日高値ブレイク+出来高1.5倍→スイング5日保持."""
        trades: list[dict] = []
        dates = sorted(df.index)
        closes: list[float] = []
        volumes: list[float] = []
        opens_list: list[float] = []
        highs_list: list[float] = []
        lows_list: list[float] = []

        i = 0
        while i < len(dates):
            dt = dates[i]
            row = df.loc[dt]
            close_p = float(row["Close"])
            open_p = float(row["Open"])
            high_p = float(row["High"])
            low_p = float(row["Low"])
            vol = float(row.get("Volume", 0))
            closes.append(close_p)
            volumes.append(vol)
            opens_list.append(open_p)
            highs_list.append(high_p)
            lows_list.append(low_p)

            if open_p <= 0 or close_p <= 0 or len(closes) < 22:
                i += 1
                continue

            # Check CIS entry: price > 20-day high + volume > 1.5x avg
            high_20 = max(closes[-21:-1])
            avg_vol = sum(volumes[-21:-1]) / 20
            if close_p <= high_20 or avg_vol <= 0 or vol < 1.5 * avg_vol:
                i += 1
                continue

            # Position sizing
            entry_price = self._apply_cost(open_p, "buy")
            stop_dist = entry_price * stop_pct / 100
            if stop_dist <= 0:
                i += 1
                continue
            lot = self.lot_size
            raw_size = int(equity * 0.05 / stop_dist)
            size = max(raw_size // lot * lot, lot)
            notional = size * entry_price
            if notional > equity * self.max_position_ratio:
                size = max(int(equity * self.max_position_ratio / entry_price / lot) * lot, lot)
                notional = size * entry_price
            if notional > equity:
                i += 1
                continue

            # Simulate hold period with trailing stop + chart exit
            stop_price = entry_price * (1 - stop_pct / 100)
            target_price = entry_price * (1 + target_pct / 100)
            trailing_stop = stop_price
            exit_price = None
            current_high = entry_price
            hold_opens: list[float] = list(opens_list[max(0, i - 20):i + 1])
            hold_highs: list[float] = list(highs_list[max(0, i - 20):i + 1])
            hold_lows: list[float] = list(lows_list[max(0, i - 20):i + 1])
            hold_closes: list[float] = list(closes[max(0, i - 20):i + 1])
            hold_vols: list[float] = list(volumes[max(0, i - 20):i + 1])

            for j in range(i + 1, min(i + hold_days + 1, len(dates))):
                f_row = df.loc[dates[j]]
                f_high = float(f_row["High"])
                f_low = float(f_row["Low"])
                f_close = float(f_row["Close"])
                f_open = float(f_row["Open"])
                f_vol = float(f_row.get("Volume", 0))

                hold_opens.append(f_open)
                hold_highs.append(f_high)
                hold_lows.append(f_low)
                hold_closes.append(f_close)
                hold_vols.append(f_vol)

                if f_high > current_high:
                    current_high = f_high

                if f_low <= trailing_stop:
                    exit_price = trailing_stop
                    break
                if f_high >= target_price:
                    exit_price = target_price
                    break
                new_stop = f_high * (1 - stop_pct / 100)
                if new_stop > trailing_stop:
                    trailing_stop = new_stop

                # Chart-based exit: check after day 2 for early exit signals
                if j - i >= 2 and len(hold_closes) >= 10:
                    exit_eval = compute_exit_score(
                        hold_opens, hold_highs, hold_lows, hold_closes, hold_vols,
                        entry_price, current_high, j - i, strategy="CIS",
                    )
                    if exit_eval.recommendation == "EXIT_NOW":
                        exit_price = self._apply_cost(f_close, "sell")
                        break

            if exit_price is None:
                last_idx = min(i + hold_days, len(dates) - 1)
                exit_price = self._apply_cost(float(df.loc[dates[last_idx]]["Close"]), "sell")

            pnl = (exit_price - entry_price) * size
            trade_date = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)
            trade = {
                "date": trade_date, "ticker": ticker, "strategy": "cis_momentum",
                "side": "buy", "size": size, "entry_price": round(entry_price, 2),
                "exit_price": round(exit_price, 2), "pnl": round(pnl, 2),
                "symbol": ticker, "qty": size,
            }
            trades.append(trade)
            self.win_engine.record_trade(trade)
            equity += pnl
            i += hold_days + 1
            continue

            i += 1  # noqa: E501 -- unreachable

        return trades

    # ------------------------------------------------------------------
    # Kei-kun (swing: 60-day sideways breakout, exit on 7 new highs)
    # ------------------------------------------------------------------

    def _run_keikun_swing(
        self,
        ticker: str,
        df: pd.DataFrame,
        equity: float,
        sideways_days: int = 60,
        sideways_range_pct: float = 15.0,
        stop_pct: float = 5.0,
        max_hold: int = 30,
        new_high_exit_days: int = 7,
    ) -> list[dict]:
        """Kei-kun式: 60日横ばい→ブレイク→7日新高値で利確."""
        trades: list[dict] = []
        dates = sorted(df.index)
        closes: list[float] = []
        volumes: list[float] = []
        opens_list: list[float] = []
        highs_list: list[float] = []
        lows_list: list[float] = []

        i = 0
        while i < len(dates):
            dt = dates[i]
            row = df.loc[dt]
            close_p = float(row["Close"])
            open_p = float(row["Open"])
            high_p = float(row["High"])
            low_p = float(row["Low"])
            vol = float(row.get("Volume", 0))
            closes.append(close_p)
            volumes.append(vol)
            opens_list.append(open_p)
            highs_list.append(high_p)
            lows_list.append(low_p)

            if close_p <= 0 or len(closes) < sideways_days + 2:
                i += 1
                continue

            # Check sideways condition
            window = closes[-(sideways_days + 1):-1]
            w_min, w_max = min(window), max(window)
            if w_min <= 0:
                i += 1
                continue
            range_pct = (w_max - w_min) / w_min * 100
            if range_pct > sideways_range_pct:
                i += 1
                continue

            # Breakout check
            if close_p <= w_max * 1.005:
                i += 1
                continue

            # Filter: price >= 100, avg volume >= 5000
            if close_p < 100:
                i += 1
                continue
            avg_vol = sum(volumes[-21:-1]) / 20 if len(volumes) >= 21 else 0
            if avg_vol < 5000:
                i += 1
                continue

            # Position sizing
            entry_price = self._apply_cost(close_p, "buy")
            stop_dist = entry_price * stop_pct / 100
            lot = self.lot_size
            raw_size = int(equity * 0.05 / stop_dist)
            size = max(raw_size // lot * lot, lot)
            notional = size * entry_price
            if notional > equity * self.max_position_ratio:
                size = max(int(equity * self.max_position_ratio / entry_price / lot) * lot, lot)
                notional = size * entry_price
            if notional > equity:
                i += 1
                continue

            # Simulate hold with new-high exit + chart scoring
            stop_price = entry_price * (1 - stop_pct / 100)
            trade_high = entry_price
            new_high_count = 0
            exit_price = None
            exit_j = i
            hold_opens: list[float] = list(opens_list[max(0, i - 20):i + 1])
            hold_highs: list[float] = list(highs_list[max(0, i - 20):i + 1])
            hold_lows: list[float] = list(lows_list[max(0, i - 20):i + 1])
            hold_closes: list[float] = list(closes[max(0, i - 20):i + 1])
            hold_vols: list[float] = list(volumes[max(0, i - 20):i + 1])

            for j in range(i + 1, min(i + max_hold + 1, len(dates))):
                f_row = df.loc[dates[j]]
                f_close = float(f_row["Close"])
                f_low = float(f_row["Low"])
                f_open = float(f_row["Open"])
                f_high = float(f_row["High"])
                f_vol = float(f_row.get("Volume", 0))

                hold_opens.append(f_open)
                hold_highs.append(f_high)
                hold_lows.append(f_low)
                hold_closes.append(f_close)
                hold_vols.append(f_vol)

                if f_low <= stop_price:
                    exit_price = stop_price
                    exit_j = j
                    break
                if f_close > trade_high:
                    trade_high = f_close
                    new_high_count += 1
                if new_high_count >= new_high_exit_days:
                    exit_price = self._apply_cost(f_close, "sell")
                    exit_j = j
                    break

                # Chart-based early exit: check after 5 days
                if j - i >= 5 and len(hold_closes) >= 10:
                    exit_eval = compute_exit_score(
                        hold_opens, hold_highs, hold_lows, hold_closes, hold_vols,
                        entry_price, trade_high, j - i, strategy="KEI",
                    )
                    if exit_eval.recommendation == "EXIT_NOW":
                        exit_price = self._apply_cost(f_close, "sell")
                        exit_j = j
                        break

                exit_j = j

            if exit_price is None:
                last_idx = min(i + max_hold, len(dates) - 1)
                exit_price = self._apply_cost(float(df.loc[dates[last_idx]]["Close"]), "sell")

            pnl = (exit_price - entry_price) * size
            trade_date = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)
            trade = {
                "date": trade_date, "ticker": ticker, "strategy": "keikun",
                "side": "buy", "size": size, "entry_price": round(entry_price, 2),
                "exit_price": round(exit_price, 2), "pnl": round(pnl, 2),
                "symbol": ticker, "qty": size,
            }
            trades.append(trade)
            self.win_engine.record_trade(trade)
            equity += pnl
            i = exit_j + 1
            continue

            i += 1  # noqa: E501 -- unreachable

        return trades

    # ------------------------------------------------------------------
    # Main run
    # ------------------------------------------------------------------

    # Available strategy names
    INTRADAY_STRATEGIES = {"intraday_momentum", "overnight_reversal", "premarket_trio"}
    SWING_STRATEGIES = {"cis_momentum", "keikun"}
    ALL_STRATEGIES = INTRADAY_STRATEGIES | SWING_STRATEGIES

    def run(
        self,
        tickers: list[str],
        start_date: str,
        end_date: str,
        strategies: list[str] | None = None,
    ) -> BacktestResult:
        """Run backtest across all tickers and date range.

        Args:
            strategies: List of strategy names to run. If None, runs all.
                Available: intraday_momentum, overnight_reversal, premarket_trio,
                           cis_momentum, keikun
        """
        active = set(strategies) if strategies else self.ALL_STRATEGIES
        logger.info(
            "Backtest: %s → %s  tickers=%s  capital=¥%,.0f  strategies=%s",
            start_date, end_date, tickers, self.initial_capital, active,
        )

        data = self._fetch_data(tickers, start_date, end_date)

        if not data:
            logger.error("No data fetched — aborting backtest")
            return BacktestResult(initial_capital=self.initial_capital)

        # Get available tickers
        available_tickers = [t for t in tickers if t in data]
        if not available_tickers:
            logger.error("No ticker data available")
            return BacktestResult(initial_capital=self.initial_capital)

        equity = self.initial_capital
        all_trades: list[dict] = []

        # --- Swing strategies (CIS, Kei-kun): full-series per ticker ---
        run_swing = bool(active & self.SWING_STRATEGIES)
        if run_swing:
            for ticker in available_tickers:
                df = data[ticker]
                if "cis_momentum" in active:
                    cis_trades = self._run_cis_swing(ticker, df, equity)
                    for t in cis_trades:
                        equity += t["pnl"]
                    all_trades.extend(cis_trades)
                if "keikun" in active:
                    kei_trades = self._run_keikun_swing(ticker, df, equity)
                    for t in kei_trades:
                        equity += t["pnl"]
                    all_trades.extend(kei_trades)

        # --- Intraday strategies: day-by-day ---
        run_intraday = bool(active & self.INTRADAY_STRATEGIES)
        if run_intraday:
            # Reset equity for intraday pass (they run independently)
            if run_swing:
                # If swing also ran, intraday starts from swing's ending equity
                pass

            ref_ticker = available_tickers[0]
            all_dates = sorted(data[ref_ticker].index)

            for i, dt in enumerate(all_dates):
                trade_date = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)

                # Reset daily circuit breaker
                self.breaker.daily_pnl = 0.0
                self.breaker.daily_trade_count = 0

                day_pnl = 0.0

                for ticker in available_tickers:
                    ticker_df = data[ticker]
                    if dt not in ticker_df.index:
                        continue

                    row = ticker_df.loc[dt]
                    if pd.isna(row.get("Open")) or pd.isna(row.get("Close")):
                        continue

                    # Previous day
                    prev_dates = [d for d in ticker_df.index if d < dt]
                    prev_row = ticker_df.loc[prev_dates[-1]] if prev_dates else None

                    # Market data rows
                    vix_row = self._safe_row(data, "^VIX", dt)
                    usdjpy_row = self._safe_row(data, "USDJPY=X", dt)
                    n225_row = self._safe_row(data, "^N225", dt)

                    prev_usdjpy_row = self._safe_prev_row(data, "USDJPY=X", dt)
                    prev_n225_row = self._safe_prev_row(data, "^N225", dt)

                    day_trades = self._run_day(
                        ticker=ticker,
                        row=row,
                        prev_row=prev_row,
                        vix_row=vix_row,
                        usdjpy_row=usdjpy_row,
                        prev_usdjpy_row=prev_usdjpy_row,
                        n225_row=n225_row,
                        prev_n225_row=prev_n225_row,
                        trade_date=trade_date,
                        equity=equity,
                    )
                    for t in day_trades:
                        day_pnl += t["pnl"]
                        all_trades.append(t)

                equity += day_pnl
                self.breaker.daily_pnl = day_pnl

        # Build equity curve from sorted trades
        all_trades.sort(key=lambda t: t["date"])
        equity_curve = self._build_equity_curve(all_trades)

        return self._build_result(all_trades, equity_curve)

    def _build_equity_curve(self, trades: list[dict]) -> list[dict]:
        """Build equity curve from chronologically sorted trades."""
        curve: list[dict] = []
        eq = self.initial_capital
        daily_pnl: dict[str, float] = {}
        for t in trades:
            d = t["date"]
            daily_pnl[d] = daily_pnl.get(d, 0.0) + t["pnl"]
        for d in sorted(daily_pnl.keys()):
            eq += daily_pnl[d]
            curve.append({"date": d, "equity": round(eq, 2), "daily_pnl": round(daily_pnl[d], 2)})
        return curve

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_row(
        data: dict[str, pd.DataFrame], key: str, dt
    ) -> pd.Series | None:
        if key not in data:
            return None
        df = data[key]
        if dt in df.index:
            return df.loc[dt]
        return None

    @staticmethod
    def _safe_prev_row(
        data: dict[str, pd.DataFrame], key: str, dt
    ) -> pd.Series | None:
        if key not in data:
            return None
        df = data[key]
        prev_dates = [d for d in df.index if d < dt]
        if prev_dates:
            return df.loc[prev_dates[-1]]
        return None

    def _build_result(
        self,
        trades: list[dict],
        equity_curve: list[dict],
    ) -> BacktestResult:
        """Compute final metrics from trade list and equity curve."""
        result = BacktestResult(
            initial_capital=self.initial_capital,
            equity_curve=equity_curve,
            trades=trades,
            trading_days=len(equity_curve),
        )

        if not trades:
            result.final_equity = self.initial_capital
            return result

        pnls = [t["pnl"] for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]

        result.total_trades = len(trades)
        result.winning_trades = len(wins)
        result.losing_trades = len(losses)
        result.total_pnl = round(sum(pnls), 2)
        result.final_equity = round(self.initial_capital + result.total_pnl, 2)
        result.total_return_pct = round(
            result.total_pnl / self.initial_capital * 100, 2
        )
        result.win_rate = round(
            len(wins) / len(trades) * 100, 1
        ) if trades else 0.0
        result.avg_win = round(sum(wins) / len(wins), 2) if wins else 0.0
        result.avg_loss = round(sum(losses) / len(losses), 2) if losses else 0.0

        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        result.profit_factor = round(
            gross_profit / gross_loss, 2
        ) if gross_loss > 0 else float("inf")

        # Annualized return
        if result.trading_days > 0:
            years = result.trading_days / 252
            if years > 0 and result.final_equity > 0:
                result.annualized_return_pct = round(
                    ((result.final_equity / self.initial_capital) ** (1 / years) - 1) * 100,
                    2,
                )

        # Sharpe & Sortino
        if len(pnls) > 1:
            mean_pnl = sum(pnls) / len(pnls)
            variance = sum((p - mean_pnl) ** 2 for p in pnls) / (len(pnls) - 1)
            std_pnl = math.sqrt(variance)
            if std_pnl > 0:
                result.sharpe_ratio = round(
                    (mean_pnl / std_pnl) * math.sqrt(252), 2
                )

            # Sortino: only downside deviation
            downside = [min(p - mean_pnl, 0) ** 2 for p in pnls]
            downside_dev = math.sqrt(sum(downside) / len(downside))
            if downside_dev > 0:
                result.sortino_ratio = round(
                    (mean_pnl / downside_dev) * math.sqrt(252), 2
                )

        # Max drawdown from equity curve
        peak = self.initial_capital
        max_dd = 0.0
        for point in equity_curve:
            eq = point["equity"]
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak * 100 if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd
        result.max_drawdown_pct = round(max_dd, 2)

        # Per-strategy breakdown
        strategies: dict[str, list[float]] = {}
        for t in trades:
            name = t.get("strategy", "unknown")
            strategies.setdefault(name, []).append(t["pnl"])

        for name, strat_pnls in strategies.items():
            s_wins = [p for p in strat_pnls if p > 0]
            result.per_strategy[name] = {
                "trades": len(strat_pnls),
                "win_rate": round(len(s_wins) / len(strat_pnls) * 100, 1),
                "pnl": round(sum(strat_pnls), 2),
            }

        return result
