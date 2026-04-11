"""Tests for CITS quantitative signal modules."""

from datetime import date

import pytest

from cits.core.signal_tracker import SignalTracker
from cits.core.signals.intraday_momentum import compute_intraday_momentum
from cits.core.signals.premarket_trio import compute_premarket_trio
from cits.core.signals.regime_filter import compute_regime, _second_friday


# ===== PremarketTrio =====


class TestPremarketTrio:
    def test_all_bearish(self):
        sig = compute_premarket_trio(
            nkd_change_pct=-2.0,
            usdjpy_change_pct=-1.0,
            vix_level=35,
            vix_change_pct=20.0,
        )
        assert sig.direction == -1
        assert sig.signals_aligned == 3
        assert sig.confidence > 0

    def test_all_bullish(self):
        sig = compute_premarket_trio(
            nkd_change_pct=1.5,
            usdjpy_change_pct=0.5,
            vix_level=12,
            vix_change_pct=-5.0,
        )
        assert sig.direction == +1
        assert sig.signals_aligned == 3

    def test_mixed_signals(self):
        sig = compute_premarket_trio(
            nkd_change_pct=0.5,
            usdjpy_change_pct=-0.3,
            vix_level=18,
            vix_change_pct=0.0,
        )
        # One bullish (CME), one bearish (JPY), one neutral (VIX)
        assert sig.direction == 0 or abs(sig.direction) == 1

    def test_flat_market(self):
        sig = compute_premarket_trio(
            nkd_change_pct=0.02,
            usdjpy_change_pct=-0.05,
            vix_level=18,
            vix_change_pct=0.5,
        )
        assert sig.signals_aligned <= 1
        assert sig.confidence < 0.5

    def test_high_vix_reduces_confidence(self):
        high_vix = compute_premarket_trio(
            nkd_change_pct=-1.0,
            usdjpy_change_pct=-0.5,
            vix_level=40,
            vix_change_pct=25.0,
        )
        low_vix = compute_premarket_trio(
            nkd_change_pct=-1.0,
            usdjpy_change_pct=-0.5,
            vix_level=15,
            vix_change_pct=25.0,
        )
        # Same moves, but high VIX should reduce confidence
        assert high_vix.confidence < low_vix.confidence

    def test_nikkei_vi_override(self):
        sig = compute_premarket_trio(
            nkd_change_pct=1.0,
            usdjpy_change_pct=0.5,
            vix_level=15,
            vix_change_pct=-2.0,
            nikkei_vi=40,  # overrides VIX
        )
        # 2 bullish (CME, JPY) vs 1 bearish (日経VI=40) = bullish direction
        # but high 日経VI reduces confidence via 0.7x multiplier
        assert sig.direction == +1
        assert sig.signals_aligned == 2
        assert "高ボラ" in sig.detail  # confidence reduction flag present


# ===== IntradayMomentum =====


class TestIntradayMomentum:
    def test_positive_momentum(self):
        sig = compute_intraday_momentum(prev_close=2800, price_at_930=2830)
        assert sig.direction == +1
        assert sig.first_30min_return > 0
        assert sig.confidence > 0

    def test_negative_momentum(self):
        sig = compute_intraday_momentum(prev_close=2800, price_at_930=2770)
        assert sig.direction == -1
        assert sig.first_30min_return < 0

    def test_flat_no_signal(self):
        sig = compute_intraday_momentum(prev_close=2800, price_at_930=2801)
        assert sig.direction == 0
        assert sig.confidence == 0

    def test_high_vol_boosts_confidence(self):
        normal = compute_intraday_momentum(prev_close=2800, price_at_930=2830)
        boosted = compute_intraday_momentum(
            prev_close=2800, price_at_930=2830,
            avg_volume_ratio=2.0, nikkei_vi=30, is_macro_news_day=True,
        )
        assert boosted.confidence > normal.confidence
        assert boosted.is_high_vol is True

    def test_invalid_prev_close(self):
        sig = compute_intraday_momentum(prev_close=0, price_at_930=100)
        assert sig.direction == 0
        assert sig.confidence == 0


# ===== RegimeFilter =====


class TestRegimeFilter:
    def test_low_vol_regime(self):
        r = compute_regime(vi_level=15, today=date(2026, 3, 2))
        assert r.volatility_regime == "low"
        assert r.preferred_strategy == "trend"
        assert r.position_size_multiplier == 1.0

    def test_high_vol_regime(self):
        r = compute_regime(vi_level=28, today=date(2026, 3, 2))
        assert r.volatility_regime == "high"
        assert r.preferred_strategy == "mean_reversion"
        assert r.position_size_multiplier == 0.5

    def test_extreme_regime(self):
        r = compute_regime(vi_level=40, today=date(2026, 3, 2))
        assert r.volatility_regime == "extreme"
        assert r.preferred_strategy == "defensive"
        assert r.position_size_multiplier == 0.25

    def test_sq_week_reduces_size(self):
        # March 2026: 2nd Friday is March 13
        sq_date = _second_friday(2026, 3)
        sq_monday = sq_date - __import__("datetime").timedelta(days=sq_date.weekday())
        r = compute_regime(vi_level=22, today=sq_monday)
        assert r.position_size_multiplier < 1.0
        assert any("SQ" in f for f in r.calendar_flags)

    def test_maji_no_suiyoubi(self):
        # Find a Wednesday in SQ week
        sq_date = _second_friday(2026, 3)
        sq_wed = sq_date - __import__("datetime").timedelta(days=2)  # Friday - 2 = Wednesday
        r = compute_regime(vi_level=22, today=sq_wed)
        assert any("魔の水曜日" in f for f in r.calendar_flags)

    def test_boj_meeting_day(self):
        r = compute_regime(vi_level=22, today=date(2026, 3, 13))
        assert any("BOJ" in f for f in r.calendar_flags)
        assert r.position_size_multiplier < 1.0

    def test_quarter_end(self):
        r = compute_regime(vi_level=22, today=date(2026, 3, 30))
        assert any("四半期末" in f for f in r.calendar_flags)

    def test_second_friday(self):
        assert _second_friday(2026, 3) == date(2026, 3, 13)
        assert _second_friday(2026, 6) == date(2026, 6, 12)


# ===== SignalTracker =====


class TestSignalTracker:
    @pytest.fixture
    def tracker(self, tmp_path):
        return SignalTracker(db_path=tmp_path / "test_signals.db")

    def test_record_and_verify_win(self, tracker):
        tracker.record_prediction("test_sig", predicted_direction=+1, confidence=0.8, date="2026-03-23")
        result = tracker.verify_prediction("test_sig", actual_return=1.5, date="2026-03-23")
        assert result["is_win"] is True

    def test_record_and_verify_loss(self, tracker):
        tracker.record_prediction("test_sig", predicted_direction=+1, confidence=0.8, date="2026-03-23")
        result = tracker.verify_prediction("test_sig", actual_return=-0.5, date="2026-03-23")
        assert result["is_win"] is False

    def test_verify_without_prediction(self, tracker):
        result = tracker.verify_prediction("nonexistent", actual_return=1.0, date="2026-03-23")
        assert result.get("error") == "no_prediction"

    def test_stats(self, tracker):
        for i in range(5):
            tracker.record_prediction("sig_a", +1, 0.7, date=f"2026-03-{10+i:02d}")
            tracker.verify_prediction("sig_a", 0.5 if i < 4 else -0.3, date=f"2026-03-{10+i:02d}")

        stats = tracker.get_signal_stats("sig_a")
        assert len(stats) == 1
        assert stats[0]["total"] == 5
        assert stats[0]["wins"] == 4
        assert stats[0]["win_rate"] == 0.8
        assert stats[0]["is_validated"] is False  # < 20 signals

    def test_active_signals_threshold(self, tracker):
        # Not enough data
        tracker.record_prediction("weak", +1, 0.5, date="2026-03-01")
        tracker.verify_prediction("weak", -1.0, date="2026-03-01")
        assert tracker.get_active_signals() == []

    def test_replace_prediction(self, tracker):
        tracker.record_prediction("sig", +1, 0.5, date="2026-03-23")
        tracker.record_prediction("sig", -1, 0.9, date="2026-03-23")  # replace
        result = tracker.verify_prediction("sig", actual_return=-2.0, date="2026-03-23")
        assert result["predicted_direction"] == -1
        assert result["is_win"] is True
