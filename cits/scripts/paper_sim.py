"""Paper Trading Simulation — historical backtest without live API keys.

Runs a paper trading simulation over the past N trading days using
yfinance data.  Uses the existing CITS signal, risk, and portfolio
modules to test the full pipeline.

Usage:
    python -m cits.scripts.paper_sim [--days 5] [--capital 100000] [--verbose]
"""

from __future__ import annotations

import argparse
import logging
import tempfile
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import yfinance as yf

from cits.core.signals.intraday_momentum import compute_intraday_momentum
from cits.core.signals.premarket_trio import compute_premarket_trio
from cits.core.signals.regime_filter import compute_regime
from cits.portfolio.paper_portfolio import PaperPortfolio
from cits.risk.circuit_breaker import CircuitBreaker
from cits.risk.position_sizer import PositionSizer

logger = logging.getLogger(__name__)

# Default TSE ticker watchlist
DEFAULT_WATCHLIST = ["7203", "8306", "6758", "9984"]

LOT_SIZE_STANDARD = 100  # Standard TSE trading lot (単元株)
LOT_SIZE_PETIT = 1       # プチ株 (単元未満株)


# ------------------------------------------------------------------
# Data helpers
# ------------------------------------------------------------------

def _fetch_historical(
    tickers: list[str],
    days: int,
) -> dict[str, "yf.Ticker"]:
    """Download historical OHLCV data for each ticker.

    Returns a mapping of ticker -> DataFrame with columns
    [Open, High, Low, Close, Volume] indexed by date.
    Extra margin of days is fetched so we have ``days`` *trading* days.
    """
    # Fetch extra calendar days to ensure enough trading days
    end = date.today()
    start = end - timedelta(days=days * 2 + 10)

    data: dict[str, object] = {}
    for ticker in tickers:
        symbol = f"{ticker}.T"
        try:
            df = yf.download(
                symbol,
                start=start.isoformat(),
                end=end.isoformat(),
                progress=False,
                auto_adjust=True,
            )
            if df.empty:
                logger.warning("No data for %s — skipping", symbol)
                continue
            # Flatten multi-level columns if present
            if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
                df.columns = df.columns.get_level_values(0)
            data[ticker] = df.tail(days + 1)  # +1 for prev_close reference
        except Exception as exc:
            logger.warning("Failed to fetch %s: %s", symbol, exc)
    return data


def _fetch_macro_data(days: int) -> dict[str, object]:
    """Fetch VIX and USD/JPY data for the simulation period."""
    end = date.today()
    start = end - timedelta(days=days * 2 + 10)

    result: dict[str, object] = {}
    for symbol, key in [("^VIX", "vix"), ("USDJPY=X", "usdjpy")]:
        try:
            df = yf.download(
                symbol,
                start=start.isoformat(),
                end=end.isoformat(),
                progress=False,
                auto_adjust=True,
            )
            if not df.empty:
                if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
                    df.columns = df.columns.get_level_values(0)
                result[key] = df
        except Exception as exc:
            logger.warning("Failed to fetch %s: %s", symbol, exc)
    return result


# ------------------------------------------------------------------
# Trade record
# ------------------------------------------------------------------

@dataclass
class TradeRecord:
    """A single paper trade."""

    day: str
    ticker: str
    action: str  # "buy" or "sell"
    side: str  # "long" or "short"
    size: int
    entry_price: float
    exit_price: float
    pnl: float
    signals: dict = field(default_factory=dict)


# ------------------------------------------------------------------
# Simulation engine
# ------------------------------------------------------------------

class PaperSimulation:
    """Runs the paper trading simulation over historical data."""

    def __init__(
        self,
        capital: float = 100_000,
        days: int = 5,
        watchlist: list[str] | None = None,
        verbose: bool = False,
    ) -> None:
        self.initial_capital = capital
        self.days = days
        self.watchlist = watchlist or DEFAULT_WATCHLIST
        self.verbose = verbose

        # Use a temporary DB so we don't pollute the real portfolio
        self._tmp_dir = tempfile.mkdtemp(prefix="cits_paper_sim_")
        self._db_path = Path(self._tmp_dir) / "paper_sim.db"

        self.portfolio = PaperPortfolio(
            initial_capital=capital,
            slippage_bps=5.0,
            commission_per_trade=0.0,
            spread_bps=3.0,
            db_path=self._db_path,
        )

        # Small accounts (<¥1M) need a higher ratio to afford 100-share lots
        _pos_ratio = 0.9 if capital < 1_000_000 else 0.2
        self.sizer = PositionSizer(
            account_size=capital,
            max_risk_per_trade=0.02,
            max_position_ratio=_pos_ratio,
        )
        self.breaker = CircuitBreaker(
            max_daily_loss=capital * 0.05,
            max_consecutive_losses=3,
            max_daily_trades=10,
        )

        # Small accounts use プチ株 (1-share lots)
        self.lot_size = LOT_SIZE_PETIT if capital < 500_000 else LOT_SIZE_STANDARD

        self.trades: list[TradeRecord] = []
        self.daily_reports: list[dict] = []
        self.equity_curve: list[float] = [capital]

        # Running state
        self._daily_pnl = 0.0
        self._consecutive_losses = 0
        self._daily_trade_count = 0

    # ---------------------------------------------------------------
    # Overridden price lookup for historical mode
    # ---------------------------------------------------------------

    def _override_price_lookup(
        self,
        price_map: dict[str, float],
    ) -> None:
        """Monkey-patch the portfolio's price lookup to use historical data."""

        def _hist_price(ticker: str) -> float | None:
            return price_map.get(ticker)

        # Override the static method on the instance
        self.portfolio._get_current_price = _hist_price  # type: ignore[assignment]

    # ---------------------------------------------------------------
    # Signal computation
    # ---------------------------------------------------------------

    @staticmethod
    def _compute_signals(
        ticker: str,
        prev_close: float,
        day_open: float,
        day_close: float,
        volume: float,
        avg_volume: float,
        vix_level: float,
        vix_change_pct: float,
        usdjpy_change_pct: float,
        sim_date: date,
    ) -> dict:
        """Compute all three signals for a ticker on a given day."""
        # 1. Intraday momentum — use open as "price at 9:30"
        im_signal = compute_intraday_momentum(
            prev_close=prev_close,
            price_at_930=day_open,
            avg_volume_ratio=volume / avg_volume if avg_volume > 0 else 1.0,
            nikkei_vi=None,
            is_macro_news_day=False,
        )

        # 2. Pre-market trio — simulate overnight futures change from prev_close
        nkd_change_pct = (day_open - prev_close) / prev_close * 100

        pm_signal = compute_premarket_trio(
            nkd_change_pct=nkd_change_pct,
            usdjpy_change_pct=usdjpy_change_pct,
            vix_level=vix_level,
            vix_change_pct=vix_change_pct,
        )

        # 3. Regime filter
        regime = compute_regime(vi_level=vix_level, today=sim_date)

        return {
            "intraday_momentum": im_signal,
            "premarket_trio": pm_signal,
            "regime": regime,
        }

    # ---------------------------------------------------------------
    # Consensus logic
    # ---------------------------------------------------------------

    @staticmethod
    def _consensus_direction(signals: dict) -> int:
        """Return trade direction if 2+ signals agree, else 0."""
        im = signals["intraday_momentum"].direction
        pm = signals["premarket_trio"].direction

        votes = [im, pm]
        bullish = sum(1 for v in votes if v > 0)
        bearish = sum(1 for v in votes if v < 0)

        if bullish >= 2:
            return +1
        if bearish >= 2:
            return -1
        return 0

    # ---------------------------------------------------------------
    # Run simulation
    # ---------------------------------------------------------------

    def run(self) -> dict:
        """Execute the full simulation. Returns summary dict."""
        print("データ取得中...")
        hist_data = _fetch_historical(self.watchlist, self.days)
        macro = _fetch_macro_data(self.days)

        if not hist_data:
            print("エラー: 株価データを取得できませんでした")
            return {"error": "No data"}

        # Determine common trading days across tickers
        all_dates: set[date] = set()
        for df in hist_data.values():
            all_dates.update(d.date() for d in df.index)

        trading_days = sorted(all_dates)[-self.days:]

        if not trading_days:
            print("エラー: 取引日が見つかりません")
            return {"error": "No trading days"}

        vix_df = macro.get("vix")
        usdjpy_df = macro.get("usdjpy")

        print(f"シミュレーション開始: {trading_days[0]} → {trading_days[-1]}")
        print(f"銘柄: {', '.join(self.watchlist)}")
        print(f"初期資金: ¥{self.initial_capital:,.0f}")
        print("-" * 60)

        for day in trading_days:
            self._simulate_day(day, hist_data, vix_df, usdjpy_df)

        return self._build_summary(trading_days)

    def _simulate_day(
        self,
        day: date,
        hist_data: dict,
        vix_df: object | None,
        usdjpy_df: object | None,
    ) -> None:
        """Simulate one trading day."""
        self.breaker.reset_daily()
        self._daily_pnl = 0.0
        self._daily_trade_count = 0
        self._consecutive_losses = 0  # Reset per day

        day_signals: list[dict] = []
        day_trades: list[TradeRecord] = []

        # Get VIX data for this day
        vix_level = 20.0  # default
        vix_change_pct = 0.0
        if vix_df is not None:
            vix_rows = vix_df[vix_df.index.date <= day]
            if len(vix_rows) >= 2:
                vix_level = float(vix_rows["Close"].iloc[-1])
                prev_vix = float(vix_rows["Close"].iloc[-2])
                if prev_vix > 0:
                    vix_change_pct = (vix_level - prev_vix) / prev_vix * 100

        # Get USD/JPY change
        usdjpy_change_pct = 0.0
        if usdjpy_df is not None:
            uj_rows = usdjpy_df[usdjpy_df.index.date <= day]
            if len(uj_rows) >= 2:
                curr_uj = float(uj_rows["Close"].iloc[-1])
                prev_uj = float(uj_rows["Close"].iloc[-2])
                if prev_uj > 0:
                    usdjpy_change_pct = (curr_uj - prev_uj) / prev_uj * 100

        for ticker in self.watchlist:
            df = hist_data.get(ticker)
            if df is None:
                continue

            # Find the row for this day
            day_rows = df[df.index.date == day]
            if day_rows.empty:
                continue

            # Find previous day's close
            prior_rows = df[df.index.date < day]
            if prior_rows.empty:
                continue

            prev_close = float(prior_rows["Close"].iloc[-1])
            day_open = float(day_rows["Open"].iloc[0])
            day_close = float(day_rows["Close"].iloc[0])
            volume = float(day_rows["Volume"].iloc[0])

            # Average volume (last 20 days available)
            avg_volume = float(df["Volume"].iloc[:-1].tail(20).mean()) or 1.0

            # Compute signals
            signals = self._compute_signals(
                ticker=ticker,
                prev_close=prev_close,
                day_open=day_open,
                day_close=day_close,
                volume=volume,
                avg_volume=avg_volume,
                vix_level=vix_level,
                vix_change_pct=vix_change_pct,
                usdjpy_change_pct=usdjpy_change_pct,
                sim_date=day,
            )

            day_signals.append({"ticker": ticker, "signals": signals})

            # Consensus
            direction = self._consensus_direction(signals)
            if direction == 0:
                if self.verbose:
                    print(
                        f"  {day} {ticker}: シグナル不一致 → HOLD"
                    )
                continue

            # Circuit breaker check
            cb_result = self.breaker.check(
                portfolio={
                    "daily_pnl": self._daily_pnl,
                    "consecutive_losses": self._consecutive_losses,
                    "daily_trade_count": self._daily_trade_count,
                },
                market_data={
                    "volatility": vix_change_pct,
                    "date": day.isoformat(),
                },
            )

            if cb_result["action"] == "halt":
                if self.verbose:
                    print(
                        f"  {day} {ticker}: サーキットブレーカー発動 "
                        f"→ {cb_result['reason']}"
                    )
                continue

            # Position sizing
            regime = signals["regime"]
            stop_distance = prev_close * 0.02  # 2% stop loss
            stop_loss = (
                day_open - stop_distance
                if direction > 0
                else day_open + stop_distance
            )

            sizing = self.sizer.calculate_size(
                entry_price=day_open,
                stop_loss=stop_loss,
            )

            raw_size = sizing["position_size"]
            # Apply regime multiplier and round to lot size
            lot = self.lot_size
            adjusted_size = int(raw_size * regime.position_size_multiplier)
            lot_count = max(adjusted_size // lot, 1)
            trade_size = lot_count * lot

            # Check if we can afford this trade
            state = self.portfolio._latest_state()
            notional = trade_size * day_open
            if notional > state["cash"] * 0.95:
                # Reduce to fit
                affordable = int(state["cash"] * 0.95 / day_open)
                lot_count = max(affordable // lot, 0)
                if lot_count == 0:
                    if self.verbose:
                        print(
                            f"  {day} {ticker}: 資金不足 → SKIP"
                        )
                    continue
                trade_size = lot_count * lot

            # Execute trade: buy at open, sell at close (intraday)
            action = "buy" if direction > 0 else "sell"
            side = "long" if direction > 0 else "short"

            # Override price lookup for the portfolio
            self._override_price_lookup({ticker: day_open})

            # Open position
            self.portfolio.execute_paper_trade({
                "ticker": ticker,
                "final_decision": {
                    "action": action,
                    "final_size": trade_size,
                    "stop_loss": stop_loss,
                    "take_profit": None,
                },
            })

            # Close at end of day
            self._override_price_lookup({ticker: day_close})

            # Get open position and close it
            pos = self.portfolio.get_position_by_ticker(ticker)
            if pos:
                close_result = self.portfolio.close_position(
                    pos["id"],
                    exit_price=self.portfolio._apply_execution_costs(
                        day_close,
                        "sell" if side == "long" else "buy",
                    ),
                )
                pnl = close_result.get("pnl", 0.0)
            else:
                pnl = 0.0

            # Record trade
            trade = TradeRecord(
                day=day.isoformat(),
                ticker=ticker,
                action=action,
                side=side,
                size=trade_size,
                entry_price=day_open,
                exit_price=day_close,
                pnl=pnl,
                signals={
                    "intraday_momentum": signals[
                        "intraday_momentum"
                    ].direction,
                    "premarket_trio": signals["premarket_trio"].direction,
                    "regime": regime.volatility_regime,
                },
            )
            self.trades.append(trade)
            day_trades.append(trade)

            # Update running state
            self._daily_pnl += pnl
            self._daily_trade_count += 1
            if pnl < 0:
                self._consecutive_losses += 1
            else:
                self._consecutive_losses = 0

            if self.verbose:
                direction_str = "ロング" if direction > 0 else "ショート"
                print(
                    f"  {day} {ticker}: {direction_str} "
                    f"x{trade_size} @ ¥{day_open:,.0f} "
                    f"→ ¥{day_close:,.0f}  "
                    f"損益: ¥{pnl:+,.0f}"
                )

        # Daily report
        state = self.portfolio._latest_state()
        equity = state["total_equity"]
        self.equity_curve.append(equity)

        report = {
            "date": day.isoformat(),
            "signals": day_signals,
            "trades": day_trades,
            "daily_pnl": self._daily_pnl,
            "equity": equity,
            "trade_count": len(day_trades),
            "circuit_breaker": self.breaker.check(
                portfolio={
                    "daily_pnl": self._daily_pnl,
                    "consecutive_losses": self._consecutive_losses,
                    "daily_trade_count": self._daily_trade_count,
                },
                market_data={"volatility": 0.0, "date": day.isoformat()},
            ),
        }
        self.daily_reports.append(report)

        print(
            f"[{day}] 取引: {len(day_trades)}件  "
            f"日次損益: ¥{self._daily_pnl:+,.0f}  "
            f"資産: ¥{equity:,.0f}"
        )

    # ---------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------

    def _build_summary(self, trading_days: list[date]) -> dict:
        """Build and print the final summary."""
        total_trades = len(self.trades)
        wins = [t for t in self.trades if t.pnl > 0]
        losses = [t for t in self.trades if t.pnl < 0]
        flat = [t for t in self.trades if t.pnl == 0]

        total_pnl = sum(t.pnl for t in self.trades)
        final_equity = self.equity_curve[-1]
        win_rate = len(wins) / total_trades * 100 if total_trades > 0 else 0.0
        pnl_pct = total_pnl / self.initial_capital * 100

        avg_win = (
            sum(t.pnl for t in wins) / len(wins) if wins else 0.0
        )
        avg_loss = (
            sum(t.pnl for t in losses) / len(losses) if losses else 0.0
        )
        profit_factor = (
            abs(sum(t.pnl for t in wins) / sum(t.pnl for t in losses))
            if losses and sum(t.pnl for t in losses) != 0
            else float("inf")
        )

        max_drawdown = 0.0
        peak = self.equity_curve[0]
        for eq in self.equity_curve:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak * 100 if peak > 0 else 0
            if dd > max_drawdown:
                max_drawdown = dd

        start_date = trading_days[0].isoformat()
        end_date = trading_days[-1].isoformat()

        print()
        print("=" * 60)
        print("=== ペーパートレード結果 ===")
        print("=" * 60)
        print(f"期間: {start_date} → {end_date}")
        print(f"初期資金: ¥{self.initial_capital:,.0f}")
        print(f"最終資金: ¥{final_equity:,.0f}")
        print(f"損益: ¥{total_pnl:+,.0f} ({pnl_pct:+.2f}%)")
        print(f"取引数: {total_trades}")
        print(
            f"勝率: {win_rate:.1f}% "
            f"({len(wins)}勝 {len(losses)}敗 {len(flat)}引分)"
        )
        print(f"平均利益: ¥{avg_win:+,.0f}")
        print(f"平均損失: ¥{avg_loss:+,.0f}")
        print(f"プロフィットファクター: {profit_factor:.2f}")
        print(f"最大ドローダウン: {max_drawdown:.2f}%")
        print()

        # Per-ticker breakdown
        print("--- 銘柄別 ---")
        for ticker in self.watchlist:
            ticker_trades = [t for t in self.trades if t.ticker == ticker]
            ticker_pnl = sum(t.pnl for t in ticker_trades)
            ticker_wins = sum(1 for t in ticker_trades if t.pnl > 0)
            ticker_total = len(ticker_trades)
            wr = ticker_wins / ticker_total * 100 if ticker_total > 0 else 0
            print(
                f"  {ticker}: {ticker_total}取引  "
                f"損益 ¥{ticker_pnl:+,.0f}  "
                f"勝率 {wr:.0f}%"
            )

        print()
        print("--- 日次損益 ---")
        for report in self.daily_reports:
            cb_status = (
                "発動" if report["circuit_breaker"]["is_triggered"] else "正常"
            )
            print(
                f"  {report['date']}: "
                f"¥{report['daily_pnl']:+,.0f}  "
                f"({report['trade_count']}取引)  "
                f"CB: {cb_status}"
            )

        print("=" * 60)

        return {
            "period_start": start_date,
            "period_end": end_date,
            "initial_capital": self.initial_capital,
            "final_equity": final_equity,
            "total_pnl": total_pnl,
            "pnl_pct": pnl_pct,
            "total_trades": total_trades,
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "max_drawdown": max_drawdown,
            "trades": self.trades,
            "daily_reports": self.daily_reports,
        }


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    """Entry point for paper trading simulation."""
    parser = argparse.ArgumentParser(
        prog="paper_sim",
        description="CITS ペーパートレードシミュレーション（過去データ使用）",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=5,
        help="シミュレーション日数 (default: 5)",
    )
    parser.add_argument(
        "--capital",
        type=float,
        default=100_000,
        help="初期資金 (default: ¥100,000)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="詳細ログ出力",
    )
    args = parser.parse_args(argv)

    log_level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    sim = PaperSimulation(
        capital=args.capital,
        days=args.days,
        verbose=args.verbose,
    )
    sim.run()


if __name__ == "__main__":
    main()
