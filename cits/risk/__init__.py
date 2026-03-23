"""
CITS Risk Management Layer
リスク管理モジュール

- CircuitBreaker: auto-halt trading on adverse conditions
- CrashDetector: detect sudden market movements
- WinRateEngine: track and validate strategy performance
- PositionSizer: calculate appropriate position sizes
- japan_risk_params: TSE/JPX-specific risk parameters and calendar data
"""

from cits.risk.circuit_breaker import CircuitBreaker
from cits.risk.crash_detector import CrashDetector
from cits.risk.japan_risk_params import (
    get_lot_size,
    get_price_limit,
    get_risk_adjustments,
    is_trading_hours,
)
from cits.risk.position_sizer import PositionSizer
from cits.risk.win_rate_engine import WinRateEngine

__all__ = [
    "CircuitBreaker",
    "CrashDetector",
    "PositionSizer",
    "WinRateEngine",
    "get_lot_size",
    "get_price_limit",
    "get_risk_adjustments",
    "is_trading_hours",
]
