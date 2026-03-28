"""Backtest Engine — runs STRATEGY_PLAYBOOK strategies against historical data.

Uses daily OHLCV as proxy (intraday data requires kabuStation).
Strategies:
  1. Intraday Momentum: Open as 9:30 proxy, entry at Open, exit at Close
  2. Overnight Reversal: large gap reversal, entry at Open, exit at Close
  3. Premarket Trio: CME/USDJPY/VIX alignment, entry at Open, exit at Close

All trades use 100-share lots (売買単位) and apply execution costs.
"""

from __future__ import annotations

import logging
import math
import tempfile
from dataclasses import dataclass, field
import pandas as pd

from cits.core.signals.intraday_momentum import compute_intraday_momentum
from cits.core.signals.premarket_trio import compute_premarket_trio
from cits.core.signals.regime_filter import compute_regime
from cits.risk.circuit_breaker import CircuitBreaker
from cits.risk.position_sizer import PositionSizer
from cits.risk.win_rate_engine import WinRateEngine

logger = logging.getLogger(__name__)

LOT_SIZE = 100  # 東証売買単位


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
        max_position_ratio: float = 0.1,
        slippage_bps: float = 5.0,
        spread_bps: float = 3.0,
        overnight_gap_threshold: float = 1.0,
    ) -> None:
        self.initial_capital = initial_capital
        self.risk_per_trade = risk_per_trade
        self.max_position_ratio = max_position_ratio
        self.slippage_bps = slippage_bps
        self.spread_bps = spread_bps
        self.overnight_gap_threshold = overnight_gap_threshold

        self.sizer = PositionSizer(
            account_size=initial_capital,
            max_risk_per_trade=risk_per_trade,
            max_position_ratio=max_position_ratio,
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
        adjusted_size = max(int(raw_size * size_mult / LOT_SIZE) * LOT_SIZE, LOT_SIZE)

        # Check we can afford it
        notional = adjusted_size * open_price
        if notional > equity * self.max_position_ratio:
            adjusted_size = max(
                int(equity * self.max_position_ratio / open_price / LOT_SIZE) * LOT_SIZE,
                LOT_SIZE,
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
    # Main run
    # ------------------------------------------------------------------

    def run(
        self,
        tickers: list[str],
        start_date: str,
        end_date: str,
    ) -> BacktestResult:
        """Run backtest across all tickers and date range."""
        logger.info(
            "Backtest: %s → %s  tickers=%s  capital=¥%,.0f",
            start_date, end_date, tickers, self.initial_capital,
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

        # Build unified date index from first available ticker
        ref_ticker = available_tickers[0]
        all_dates = sorted(data[ref_ticker].index)

        equity = self.initial_capital
        all_trades: list[dict] = []
        equity_curve: list[dict] = []

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

            equity_curve.append({
                "date": trade_date,
                "equity": round(equity, 2),
                "daily_pnl": round(day_pnl, 2),
            })

        return self._build_result(all_trades, equity_curve)

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
