"""Tests for risk management modules: circuit_breaker, crash_detector, position_sizer, win_rate_engine."""

from cits.risk.circuit_breaker import CircuitBreaker, _second_friday
from cits.risk.crash_detector import CrashDetector
from cits.risk.position_sizer import PositionSizer
from cits.risk.win_rate_engine import WinRateEngine


# ===== CircuitBreaker =====

def test_cb_no_trigger_normal():
    """CircuitBreaker returns continue when all metrics are within limits."""
    cb = CircuitBreaker()
    result = cb.check(
        portfolio={"daily_pnl": -10000, "consecutive_losses": 1, "daily_trade_count": 3},
        market_data={"volatility": 1.5, "date": "2026-03-22"},
    )
    assert result["is_triggered"] is False
    assert result["action"] == "continue"


def test_cb_daily_loss_halt():
    """CircuitBreaker halts when daily loss exceeds max."""
    cb = CircuitBreaker(max_daily_loss=50000)
    result = cb.check(
        portfolio={"daily_pnl": -60000},
        market_data={},
    )
    assert result["is_triggered"] is True
    assert result["action"] == "halt"
    assert "Daily loss" in result["reason"]


def test_cb_consecutive_losses_halt():
    """CircuitBreaker halts on consecutive losses."""
    cb = CircuitBreaker(max_consecutive_losses=3)
    result = cb.check(
        portfolio={"daily_pnl": 0, "consecutive_losses": 4},
        market_data={},
    )
    assert result["is_triggered"] is True
    assert result["action"] == "halt"


def test_cb_max_trades_halt():
    """CircuitBreaker halts when daily trade count exceeds max."""
    cb = CircuitBreaker(max_daily_trades=10)
    result = cb.check(
        portfolio={"daily_pnl": 0, "consecutive_losses": 0, "daily_trade_count": 10},
        market_data={},
    )
    assert result["is_triggered"] is True
    assert result["action"] == "halt"


def test_cb_volatility_reduce():
    """CircuitBreaker triggers reduce on high volatility."""
    cb = CircuitBreaker(volatility_threshold=3.0)
    result = cb.check(
        portfolio={"daily_pnl": 0, "consecutive_losses": 0, "daily_trade_count": 0},
        market_data={"volatility": 4.0},
    )
    assert result["is_triggered"] is True
    assert result["action"] == "reduce"


def test_cb_sq_date_reduce():
    """CircuitBreaker triggers reduce near SQ date (2nd Friday)."""
    cb = CircuitBreaker()
    # 2026-03-13 is 2nd Friday of March 2026
    sq = _second_friday(2026, 3)
    # day before SQ
    day_before = sq.isoformat()
    result = cb.check(
        portfolio={"daily_pnl": 0, "consecutive_losses": 0, "daily_trade_count": 0},
        market_data={"volatility": 0.5, "date": day_before},
    )
    # Should reduce since it is 0 days to SQ
    assert result["is_triggered"] is True
    assert result["action"] == "reduce"


def test_cb_reset_daily():
    """reset_daily zeroes out daily counters."""
    cb = CircuitBreaker()
    cb.daily_pnl = -99999
    cb.consecutive_losses = 10
    cb.daily_trade_count = 50
    cb.reset_daily()
    assert cb.daily_pnl == 0.0
    assert cb.consecutive_losses == 0
    assert cb.daily_trade_count == 0


def test_second_friday_march_2026():
    """_second_friday returns correct date for March 2026."""
    result = _second_friday(2026, 3)
    assert result.weekday() == 4  # Friday
    assert 8 <= result.day <= 14


# ===== CrashDetector =====

def test_cd_normal_market():
    """CrashDetector returns normal severity for calm market."""
    cd = CrashDetector()
    result = cd.check_market({
        "price_change_pct": -0.5,
        "volume_ratio": 1.2,
        "vix": 15,
    })
    assert result["is_crash"] is False
    assert result["severity"] == "normal"


def test_cd_price_drop_warning():
    """CrashDetector detects a price drop correction."""
    cd = CrashDetector(drop_threshold=-3.0)
    result = cd.check_market({"price_change_pct": -4.0})
    assert result["is_crash"] is True
    assert result["severity"] in ("warning", "severe")
    assert result["type"] == "correction"


def test_cd_flash_crash():
    """CrashDetector detects a flash crash (intraday drop + volume spike)."""
    cd = CrashDetector(drop_threshold=-3.0, spike_threshold=5.0)
    result = cd.check_market({
        "price_change_pct": -5.0,
        "intraday_low_pct": -6.0,
        "volume_ratio": 8.0,
        "vix": 35,
    })
    assert result["is_crash"] is True
    assert result["type"] == "flash_crash"


def test_cd_black_swan():
    """CrashDetector detects extreme conditions with appropriate severity."""
    cd = CrashDetector(drop_threshold=-3.0, spike_threshold=5.0)
    result = cd.check_market({
        "price_change_pct": -10.0,
        "intraday_low_pct": -12.0,
        "volume_ratio": 10.0,
        "vix": 50,
        "vix_change_pct": 40.0,
        "bid_ask_spread": 50,
        "avg_bid_ask_spread": 5,
    })
    assert result["is_crash"] is True
    assert result["severity"] == "extreme"
    # flash_crash takes priority when intraday_low + volume_ratio both trigger
    assert result["type"] in ("flash_crash", "black_swan")
    assert "Flatten" in result["recommended_action"]


def test_cd_tse_circuit_breaker_limit_down():
    """check_circuit_breaker_triggered detects limit-down."""
    cd = CrashDetector()
    assert cd.check_circuit_breaker_triggered({"price_change_pct": -31.0}) is True


def test_cd_tse_circuit_breaker_no_trigger():
    """check_circuit_breaker_triggered returns False for normal moves."""
    cd = CrashDetector()
    assert cd.check_circuit_breaker_triggered({"price_change_pct": -5.0}) is False


# ===== PositionSizer =====

def test_ps_basic_sizing():
    """PositionSizer returns correct size for a simple case."""
    ps = PositionSizer(account_size=1_000_000, max_risk_per_trade=0.02, max_position_ratio=0.5)
    result = ps.calculate_size(entry_price=1000, stop_loss=950)
    # risk_amount = 1_000_000 * 0.02 = 20_000; risk_per_unit = 50
    # size = 20_000 / 50 = 400; max_notional = 500_000 => max 500 shares, no cap
    assert result["position_size"] == 400
    assert result["risk_amount"] == 20_000.0


def test_ps_capped_by_max_position():
    """PositionSizer caps size when notional would exceed max_position_ratio."""
    ps = PositionSizer(account_size=100_000, max_risk_per_trade=0.10, max_position_ratio=0.05)
    # risk_amount = 10_000; risk_per_unit = 10 => raw size = 1000
    # max_notional = 100_000 * 0.05 = 5000; max_size = 5000/100 = 50
    result = ps.calculate_size(entry_price=100, stop_loss=90)
    assert result["position_size"] == 50


def test_ps_zero_entry_price():
    """PositionSizer returns 0 for invalid entry price."""
    ps = PositionSizer()
    result = ps.calculate_size(entry_price=0, stop_loss=100)
    assert result["position_size"] == 0


def test_ps_equal_entry_stop():
    """PositionSizer returns 0 when entry equals stop loss."""
    ps = PositionSizer()
    result = ps.calculate_size(entry_price=1000, stop_loss=1000)
    assert result["position_size"] == 0


def test_ps_kelly_positive_edge():
    """adjust_for_kelly returns a positive fraction for a winning strategy."""
    ps = PositionSizer(max_risk_per_trade=0.05)
    result = ps.adjust_for_kelly(win_rate=0.6, avg_win=200, avg_loss=100)
    # kelly = 0.6 - 0.4/2 = 0.4; half-kelly = 0.2; capped at 0.05
    assert result == 0.05


def test_ps_kelly_no_edge():
    """adjust_for_kelly returns 0 when there is no edge."""
    ps = PositionSizer()
    result = ps.adjust_for_kelly(win_rate=0.3, avg_win=100, avg_loss=100)
    # kelly = 0.3 - 0.7/1 = -0.4 → 0
    assert result == 0.0


def test_ps_volatility_adjustment_high_vol():
    """adjust_for_volatility reduces size when current vol > avg vol."""
    ps = PositionSizer()
    result = ps.adjust_for_volatility(base_size=100, current_vol=2.0, avg_vol=1.0)
    assert result == 50  # 100 / 2.0


def test_ps_volatility_adjustment_low_vol():
    """adjust_for_volatility keeps base size when current vol < avg vol."""
    ps = PositionSizer()
    result = ps.adjust_for_volatility(base_size=100, current_vol=0.5, avg_vol=1.0)
    assert result == 100  # no increase


# ===== WinRateEngine =====

def test_wre_record_and_stats(tmp_path):
    """WinRateEngine records trades and computes stats."""
    db = tmp_path / "test_trades.db"
    wre = WinRateEngine(db_path=db, min_trades=2)
    wre.record_trade({"symbol": "7203", "side": "buy", "qty": 100,
                       "entry_price": 1000, "exit_price": 1100, "pnl": 10000})
    wre.record_trade({"symbol": "7203", "side": "buy", "qty": 100,
                       "entry_price": 1000, "exit_price": 900, "pnl": -10000})
    stats = wre.get_stats()
    assert stats["total_trades"] == 2
    assert stats["win_rate"] == 0.5
    assert stats["total_pnl"] == 0.0


def test_wre_empty_stats(tmp_path):
    """WinRateEngine returns zeroed stats when no trades recorded."""
    db = tmp_path / "empty.db"
    wre = WinRateEngine(db_path=db)
    stats = wre.get_stats()
    assert stats["total_trades"] == 0
    assert stats["win_rate"] == 0.0


def test_wre_is_strategy_valid_insufficient(tmp_path):
    """is_strategy_valid fails when there are not enough trades."""
    db = tmp_path / "few.db"
    wre = WinRateEngine(db_path=db, min_trades=20)
    wre.record_trade({"symbol": "7203", "side": "buy", "qty": 1,
                       "entry_price": 100, "exit_price": 110, "pnl": 10})
    result = wre.is_strategy_valid()
    assert result["is_valid"] is False
    assert any("Insufficient" in r for r in result["reasons"])


def test_wre_strategy_weights(tmp_path):
    """get_strategy_weights returns normalised weights."""
    db = tmp_path / "weights.db"
    wre = WinRateEngine(db_path=db)
    for i in range(5):
        wre.record_trade({
            "symbol": "7203", "side": "buy", "qty": 100,
            "entry_price": 1000, "exit_price": 1100, "pnl": 10000,
            "strategy": "alpha",
        })
    for i in range(5):
        wre.record_trade({
            "symbol": "9984", "side": "sell", "qty": 100,
            "entry_price": 1000, "exit_price": 900, "pnl": -10000,
            "strategy": "beta",
        })
    weights = wre.get_strategy_weights()
    assert "alpha" in weights
    assert "beta" in weights
    assert abs(sum(weights.values()) - 1.0) < 0.01


def test_wre_profit_factor(tmp_path):
    """Profit factor computed correctly: gross_profit / gross_loss."""
    db = tmp_path / "pf.db"
    wre = WinRateEngine(db_path=db)
    wre.record_trade({"symbol": "7203", "side": "buy", "qty": 1,
                       "entry_price": 100, "exit_price": 200, "pnl": 100})
    wre.record_trade({"symbol": "7203", "side": "buy", "qty": 1,
                       "entry_price": 200, "exit_price": 150, "pnl": -50})
    stats = wre.get_stats()
    assert stats["profit_factor"] == 2.0  # 100 / 50
