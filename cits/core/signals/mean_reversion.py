"""Mean Reversion Signal — Bollinger Bands z-score strategy.

When price deviates significantly from its moving average,
bet on reversion to the mean.

Logic:
    - Compute SMA and standard deviation over a lookback period
    - z_score = (price - SMA) / std_dev
    - z <= -entry_z  → oversold  → buy  (+1)
    - z >=  entry_z  → overbought → sell (-1)
    - |z| <= exit_z  → near mean  → neutral (0)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MeanReversionSignal:
    """Result of mean-reversion / Bollinger Band analysis."""

    direction: int  # +1=buy oversold, -1=sell overbought, 0=neutral
    confidence: float  # 0.0-1.0
    z_score: float  # how many std devs from mean
    upper_band: float
    lower_band: float
    middle_band: float  # SMA
    detail: str


def compute_mean_reversion(
    closes: list[float],
    period: int = 20,
    entry_z: float = 2.0,
    exit_z: float = 0.5,
) -> MeanReversionSignal:
    """Compute mean-reversion signal from closing prices.

    Args:
        closes: List of closing prices (oldest first).
        period: Lookback period for SMA / std dev.
        entry_z: Z-score threshold to trigger entry signal.
        exit_z: Z-score threshold below which signal is neutral.

    Returns:
        MeanReversionSignal with direction, confidence, bands, etc.
    """
    neutral = MeanReversionSignal(
        direction=0,
        confidence=0.0,
        z_score=0.0,
        upper_band=0.0,
        lower_band=0.0,
        middle_band=0.0,
        detail="insufficient data",
    )

    if len(closes) < period:
        logger.debug(
            "mean_reversion: not enough data (%d < %d)", len(closes), period
        )
        return neutral

    window = closes[-period:]
    sma = sum(window) / period
    variance = sum((x - sma) ** 2 for x in window) / period
    std_dev = variance**0.5

    if std_dev == 0.0:
        logger.debug("mean_reversion: std_dev is zero, returning neutral")
        return MeanReversionSignal(
            direction=0,
            confidence=0.0,
            z_score=0.0,
            upper_band=sma,
            lower_band=sma,
            middle_band=sma,
            detail="zero volatility",
        )

    current_price = closes[-1]
    z_score = (current_price - sma) / std_dev

    upper_band = sma + entry_z * std_dev
    lower_band = sma - entry_z * std_dev

    # Determine direction
    if z_score <= -entry_z:
        direction = 1
        detail = f"oversold: z={z_score:.2f} below -{entry_z}"
    elif z_score >= entry_z:
        direction = -1
        detail = f"overbought: z={z_score:.2f} above +{entry_z}"
    elif abs(z_score) <= exit_z:
        direction = 0
        detail = f"near mean: z={z_score:.2f} within ±{exit_z}"
    else:
        direction = 0
        detail = f"no signal: z={z_score:.2f} between exit and entry"

    confidence = min(abs(z_score) / 3.0, 0.9)

    logger.info(
        "mean_reversion: price=%.2f sma=%.2f z=%.2f dir=%d conf=%.2f",
        current_price,
        sma,
        z_score,
        direction,
        confidence,
    )

    return MeanReversionSignal(
        direction=direction,
        confidence=confidence,
        z_score=z_score,
        upper_band=upper_band,
        lower_band=lower_band,
        middle_band=sma,
        detail=detail,
    )
