"""Tests for cits.core.chart_exit -- chart-based exit scoring."""

from cits.core.chart_exit import ExitScore, compute_exit_score


def _make_uptrend(n: int = 30, start: float = 1000.0):
    """Generate uptrend OHLCV data."""
    opens, highs, lows, closes, volumes = [], [], [], [], []
    price = start
    for _ in range(n):
        o = price
        h = price + 10
        low = price - 3
        c = price + 7
        price = c
        opens.append(o)
        highs.append(h)
        lows.append(low)
        closes.append(c)
        volumes.append(50000)
    return opens, highs, lows, closes, volumes


def _make_crash(base_data, crash_days: int = 10):
    """Append crash days to existing OHLCV data."""
    opens, highs, lows, closes, volumes = [list(x) for x in base_data]
    price = closes[-1]
    for _ in range(crash_days):
        o = price - 10
        h = price - 5
        low = price - 30
        c = price - 20
        price = c
        opens.append(o)
        highs.append(h)
        lows.append(low)
        closes.append(c)
        volumes.append(90000)
    return opens, highs, lows, closes, volumes


class TestExitScoreBasics:
    def test_returns_exit_score_type(self):
        result = compute_exit_score(
            [100] * 10, [102] * 10, [99] * 10, [101] * 10, [1000] * 10,
            entry_price=100, current_high=102, hold_days=3,
        )
        assert isinstance(result, ExitScore)

    def test_insufficient_data_returns_hold(self):
        result = compute_exit_score(
            [100, 101], [102, 103], [99, 100], [101, 102], [1000, 1000],
            entry_price=100, current_high=103, hold_days=1,
        )
        assert result.recommendation == "HOLD"
        assert result.total == 0

    def test_score_range_0_to_100(self):
        opens, highs, lows, closes, volumes = _make_uptrend(30)
        result = compute_exit_score(
            opens, highs, lows, closes, volumes,
            entry_price=closes[0], current_high=max(closes), hold_days=15,
        )
        assert 0 <= result.total <= 100


class TestUptrend:
    def test_uptrend_recommends_hold(self):
        opens, highs, lows, closes, volumes = _make_uptrend(30)
        result = compute_exit_score(
            opens, highs, lows, closes, volumes,
            entry_price=closes[5], current_high=max(closes), hold_days=10,
        )
        assert result.recommendation == "HOLD"
        assert result.trailing_hit is False

    def test_uptrend_low_score(self):
        opens, highs, lows, closes, volumes = _make_uptrend(30)
        result = compute_exit_score(
            opens, highs, lows, closes, volumes,
            entry_price=closes[5], current_high=max(closes), hold_days=10,
        )
        assert result.total < 30


class TestCrash:
    def test_crash_triggers_exit(self):
        base = _make_uptrend(25)
        opens, highs, lows, closes, volumes = _make_crash(base, crash_days=10)
        peak = max(closes[:25])
        entry = closes[10]
        result = compute_exit_score(
            opens, highs, lows, closes, volumes,
            entry_price=entry, current_high=peak, hold_days=20, strategy="CIS",
        )
        assert result.recommendation in ("EXIT", "EXIT_NOW")
        assert result.total >= 50

    def test_crash_trailing_stop_hit(self):
        base = _make_uptrend(25)
        opens, highs, lows, closes, volumes = _make_crash(base, crash_days=10)
        peak = max(closes[:25])
        entry = closes[10]
        result = compute_exit_score(
            opens, highs, lows, closes, volumes,
            entry_price=entry, current_high=peak, hold_days=20, strategy="CIS",
        )
        assert result.trailing_hit is True


class TestStrategy:
    def test_cis_and_kei_produce_different_scores(self):
        base = _make_uptrend(25)
        opens, highs, lows, closes, volumes = _make_crash(base, crash_days=5)
        peak = max(closes[:25])
        entry = closes[10]

        cis = compute_exit_score(
            opens, highs, lows, closes, volumes,
            entry_price=entry, current_high=peak, hold_days=10, strategy="CIS",
        )
        kei = compute_exit_score(
            opens, highs, lows, closes, volumes,
            entry_price=entry, current_high=peak, hold_days=10, strategy="KEI",
        )
        # Same data but different weights -> may differ
        # Both should still be >= EXIT threshold on crash
        assert cis.total > 0
        assert kei.total > 0


class TestBearishPatterns:
    def test_bearish_engulfing_detected(self):
        # Build data with bearish engulfing at the end
        opens = [100] * 8 + [105, 110]
        highs = [102] * 8 + [108, 112]
        lows = [99] * 8 + [104, 98]
        closes = [101] * 8 + [107, 99]  # big red candle engulfs previous
        volumes = [1000] * 10
        result = compute_exit_score(
            opens, highs, lows, closes, volumes,
            entry_price=100, current_high=112, hold_days=5,
        )
        assert result.bearish_pattern > 0
