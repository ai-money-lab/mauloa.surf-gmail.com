"""
CITS Risk Management Layer
リスク管理モジュール

- CircuitBreaker: auto-halt trading on adverse conditions
- CrashDetector: detect sudden market movements
- WinRateEngine: track and validate strategy performance
- PositionSizer: calculate appropriate position sizes
"""

from cits.risk.circuit_breaker import CircuitBreaker
from cits.risk.crash_detector import CrashDetector
from cits.risk.position_sizer import PositionSizer
from cits.risk.win_rate_engine import WinRateEngine

__all__ = [
    "CircuitBreaker",
    "CrashDetector",
    "PositionSizer",
    "WinRateEngine",
]
