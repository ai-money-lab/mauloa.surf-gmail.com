"""Tests for backtest engine."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from cits.backtest.engine import BacktestEngine, BacktestResult


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_ohlcv(rows: list[dict]) -> pd.DataFrame:
    """Create a DataFrame mimicking yfinance output."""
    df = pd.DataFrame(rows)
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.set_index("Date")
    return df


@pytest.fixture()
def sample_data():
    """Two days of data for one ticker + market indices."""
    dates = ["2026-01-05", "2026-01-06", "2026-01-07"]
    ticker_rows = [
        {"Date": d, "Open": o, "High": h, "Low": lo, "Close": c, "Volume": v}
        for d, o, h, lo, c, v in [
            ("2026-01-05", 2500, 2550, 2480, 2520, 1000000),
            ("2026-01-06", 2530, 2580, 2510, 2570, 1200000),
            ("2026-01-07", 2560, 2600, 2540, 2550, 900000),
        ]
    ]
    vix_rows = [
        {"Date": d, "Open": 18.0, "High": 19.0, "Low": 17.0, "Close": 18.0, "Volume": 0}
        for d in dates
    ]
    usdjpy_rows = [
        {"Date": "2026-01-05", "Open": 150.0, "High": 150.5, "Low": 149.5, "Close": 150.2, "Volume": 0},
        {"Date": "2026-01-06", "Open": 150.2, "High": 151.0, "Low": 150.0, "Close": 150.8, "Volume": 0},
        {"Date": "2026-01-07", "Open": 150.8, "High": 151.0, "Low": 150.0, "Close": 150.5, "Volume": 0},
    ]
    n225_rows = [
        {"Date": "2026-01-05", "Open": 38000, "High": 38200, "Low": 37800, "Close": 38100, "Volume": 0},
        {"Date": "2026-01-06", "Open": 38100, "High": 38400, "Low": 38000, "Close": 38300, "Volume": 0},
        {"Date": "2026-01-07", "Open": 38300, "High": 38400, "Low": 38100, "Close": 38200, "Volume": 0},
    ]

    return {
        "7203": _make_ohlcv(ticker_rows),
        "^VIX": _make_ohlcv(vix_rows),
        "USDJPY=X": _make_ohlcv(usdjpy_rows),
        "^N225": _make_ohlcv(n225_rows),
    }


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------

class TestBacktestResult:
    def test_default_values(self):
        r = BacktestResult()
        assert r.initial_capital == 0.0
        assert r.total_trades == 0
        assert r.trades == []

    def test_summary_prints(self):
        r = BacktestResult(
            initial_capital=100000,
            final_equity=102000,
            total_return_pct=2.0,
            total_pnl=2000,
            total_trades=10,
            winning_trades=6,
            losing_trades=4,
            win_rate=60.0,
            profit_factor=1.5,
            sharpe_ratio=1.2,
            sortino_ratio=1.5,
            max_drawdown_pct=3.0,
            avg_win=500,
            avg_loss=-300,
            trading_days=20,
        )
        text = r.summary()
        assert "バックテスト結果" in text
        assert "102,000" in text
        assert "60.0%" in text

    def test_summary_with_strategies(self):
        r = BacktestResult(
            per_strategy={
                "intraday_momentum": {"trades": 5, "win_rate": 60.0, "pnl": 1500},
            }
        )
        text = r.summary()
        assert "intraday_momentum" in text


class TestBacktestEngine:
    def test_init_defaults(self):
        eng = BacktestEngine()
        assert eng.initial_capital == 100_000
        assert eng.slippage_bps == 5.0

    def test_apply_cost_buy(self):
        eng = BacktestEngine(slippage_bps=10.0, spread_bps=0.0)
        fill = eng._apply_cost(1000.0, "buy")
        assert fill > 1000.0

    def test_apply_cost_sell(self):
        eng = BacktestEngine(slippage_bps=10.0, spread_bps=0.0)
        fill = eng._apply_cost(1000.0, "sell")
        assert fill < 1000.0

    def test_run_with_mock_data(self, sample_data):
        eng = BacktestEngine(initial_capital=1_000_000)

        with patch.object(eng, "_fetch_data", return_value=sample_data):
            result = eng.run(
                tickers=["7203"],
                start_date="2026-01-05",
                end_date="2026-01-07",
            )

        assert isinstance(result, BacktestResult)
        assert result.initial_capital == 1_000_000
        assert result.trading_days > 0
        # Equity curve should have entries
        assert len(result.equity_curve) > 0

    def test_run_empty_data(self):
        eng = BacktestEngine()
        with patch.object(eng, "_fetch_data", return_value={}):
            result = eng.run(
                tickers=["9999"],
                start_date="2026-01-01",
                end_date="2026-01-31",
            )
        assert result.total_trades == 0

    def test_build_result_no_trades(self):
        eng = BacktestEngine(initial_capital=100000)
        result = eng._build_result([], [])
        assert result.final_equity == 100000
        assert result.total_trades == 0

    def test_build_result_with_trades(self):
        eng = BacktestEngine(initial_capital=100000)
        trades = [
            {"pnl": 500, "strategy": "s1"},
            {"pnl": -200, "strategy": "s1"},
            {"pnl": 300, "strategy": "s2"},
        ]
        curve = [
            {"date": "2026-01-05", "equity": 100500, "daily_pnl": 500},
            {"date": "2026-01-06", "equity": 100300, "daily_pnl": -200},
            {"date": "2026-01-07", "equity": 100600, "daily_pnl": 300},
        ]
        result = eng._build_result(trades, curve)
        assert result.total_trades == 3
        assert result.winning_trades == 2
        assert result.losing_trades == 1
        assert result.total_pnl == 600
        assert result.final_equity == 100600
        assert "s1" in result.per_strategy
        assert "s2" in result.per_strategy

    def test_safe_row_missing_key(self, sample_data):
        row = BacktestEngine._safe_row(sample_data, "MISSING", pd.Timestamp("2026-01-05"))
        assert row is None

    def test_safe_prev_row(self, sample_data):
        row = BacktestEngine._safe_prev_row(
            sample_data, "^VIX", pd.Timestamp("2026-01-06")
        )
        assert row is not None
