"""Intraday Momentum Signal — first 30min predicts last 30min.

Based on: Gao, Han, Li, Zhou (Journal of Financial Economics, 2018)
"Market Intraday Momentum"

Key findings:
    - First 30-min return from prior close predicts last 30-min return
    - Sharpe ~1.08 annualized (6.67% return, 6.19% std dev)
    - R² = 1.6% normal, 3.3% on high-vol days
    - Stronger on high-volume, high-volatility, and macro news days
    - Does NOT exist in currencies or commodities (equity-specific)

Signal appears: 9:30 AM (after first 30 minutes)
Signal resolves: 15:00 (market close)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class IntradayMomentumSignal:
    """Result of intraday momentum analysis."""
    direction: int          # +1=bullish (long last HH), -1=bearish
    confidence: float       # 0.0-1.0
    first_30min_return: float  # % return of first 30 minutes
    is_high_vol: bool       # whether today is a high-volatility day
    detail: str


def compute_intraday_momentum(
    prev_close: float,
    price_at_930: float,
    avg_volume_ratio: float = 1.0,
    nikkei_vi: float | None = None,
    is_macro_news_day: bool = False,
) -> IntradayMomentumSignal:
    """Compute the intraday momentum signal from first 30-min return.

    The strategy: go long (short) the last 30 minutes if the first
    30-min return is positive (negative).

    Args:
        prev_close: Previous day's closing price
        price_at_930: Price at 9:30 AM (30 min after open)
        avg_volume_ratio: Today's first-30min volume / average first-30min volume
        nikkei_vi: Current 日経VI level (for volatility regime)
        is_macro_news_day: Whether today has major macro releases

    Returns:
        IntradayMomentumSignal
    """
    if prev_close <= 0:
        return IntradayMomentumSignal(
            direction=0, confidence=0, first_30min_return=0,
            is_high_vol=False, detail="Invalid prev_close",
        )

    first_30min_return = (price_at_930 - prev_close) / prev_close * 100
    direction = +1 if first_30min_return > 0 else (-1 if first_30min_return < 0 else 0)

    # Base confidence from magnitude of the move
    magnitude = abs(first_30min_return)
    base_confidence = min(magnitude / 1.0, 0.6)  # up to 0.6 for 1%+ move

    # Boost conditions (from the paper)
    is_high_vol = False
    boosts: list[str] = []

    if avg_volume_ratio > 1.5:
        base_confidence += 0.1
        boosts.append(f"高出来高({avg_volume_ratio:.1f}x)")
        is_high_vol = True

    if nikkei_vi is not None and nikkei_vi > 25:
        base_confidence += 0.1
        boosts.append(f"高ボラ(日経VI={nikkei_vi:.1f})")
        is_high_vol = True

    if is_macro_news_day:
        base_confidence += 0.1
        boosts.append("マクロニュース日")

    confidence = min(base_confidence, 0.9)

    # Very small moves have no signal
    if magnitude < 0.05:
        direction = 0
        confidence = 0
        detail = f"最初30分リターン {first_30min_return:+.3f}% — 変動小、シグナルなし"
    else:
        boost_str = f" ({', '.join(boosts)})" if boosts else ""
        detail = (
            f"最初30分リターン {first_30min_return:+.2f}% → "
            f"{'ロング' if direction > 0 else 'ショート'}バイアス{boost_str}"
        )

    signal = IntradayMomentumSignal(
        direction=direction,
        confidence=round(confidence, 3),
        first_30min_return=round(first_30min_return, 4),
        is_high_vol=is_high_vol,
        detail=detail,
    )

    logger.info(
        "IntradayMomentum: direction=%+d confidence=%.2f return=%.2f%% [%s]",
        direction, confidence, first_30min_return, detail,
    )
    return signal
