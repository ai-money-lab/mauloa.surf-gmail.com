"""Trend Filter — Moving average based trend direction filter.

Uses short-term and long-term moving averages to determine the dominant
trend direction.  Only trades aligned with the trend should be taken:
    - Uptrend:   short MA > long MA AND price > short MA  → +1
    - Downtrend: short MA < long MA AND price < short MA  → -1
    - Unclear:   otherwise                                → 0
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TrendFilterSignal:
    """Result of the trend filter computation."""

    direction: int  # +1 bullish, -1 bearish, 0 neutral
    strength: float  # 0.0-1.0
    ma_short: float  # short-term MA value
    ma_long: float  # long-term MA value
    price_vs_ma: float  # % distance from long MA
    detail: str


def compute_trend_filter(
    closes: list[float],
    short_period: int = 5,
    long_period: int = 20,
) -> TrendFilterSignal:
    """Compute trend direction from moving averages.

    Args:
        closes: List of closing prices (oldest first).
        short_period: Window for short-term MA (default 5).
        long_period: Window for long-term MA (default 20).

    Returns:
        TrendFilterSignal with direction, strength, and detail.
    """
    if len(closes) < long_period:
        logger.debug(
            "Not enough data for trend filter: %d < %d", len(closes), long_period
        )
        return TrendFilterSignal(
            direction=0,
            strength=0.0,
            ma_short=0.0,
            ma_long=0.0,
            price_vs_ma=0.0,
            detail=f"データ不足({len(closes)}/{long_period})",
        )

    current_price = closes[-1]
    ma_short = sum(closes[-short_period:]) / short_period
    ma_long = sum(closes[-long_period:]) / long_period

    # Direction
    if ma_short > ma_long and current_price > ma_short:
        direction = 1
    elif ma_short < ma_long and current_price < ma_short:
        direction = -1
    else:
        direction = 0

    # Strength: MA separation normalized by price level
    strength = 0.0
    if ma_long > 0:
        strength = min(abs(ma_short - ma_long) / ma_long * 100, 1.0)

    # Price vs long MA
    price_vs_ma = 0.0
    if ma_long > 0:
        price_vs_ma = (current_price - ma_long) / ma_long * 100

    direction_label = {1: "上昇", -1: "下降", 0: "中立"}[direction]
    detail = (
        f"トレンド={direction_label} "
        f"MA{short_period}={ma_short:.2f} MA{long_period}={ma_long:.2f} "
        f"乖離={price_vs_ma:+.2f}% 強度={strength:.2f}"
    )

    signal = TrendFilterSignal(
        direction=direction,
        strength=strength,
        ma_short=ma_short,
        ma_long=ma_long,
        price_vs_ma=price_vs_ma,
        detail=detail,
    )

    logger.info(
        "TrendFilter: direction=%+d strength=%.2f price_vs_ma=%.2f%%",
        direction,
        strength,
        price_vs_ma,
    )
    return signal
