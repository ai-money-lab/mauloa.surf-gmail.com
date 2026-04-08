"""Volume Confirmation Filter — validate trades with volume support.

Trades are only valid when volume supports the move direction:
    - Long entries: require above-average volume AND up-day volume > down-day volume
    - Short entries: require above-average volume AND down-day volume > up-day volume
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from statistics import mean

logger = logging.getLogger(__name__)


@dataclass
class VolumeConfirmation:
    """Result of volume confirmation check."""

    confirmed: bool
    volume_ratio: float
    trend_volume_ratio: float
    detail: str


def compute_volume_confirmation(
    closes: list[float],
    volumes: list[float],
    direction: int,
    min_ratio: float = 1.0,
    lookback: int = 20,
) -> VolumeConfirmation:
    """Check whether volume confirms the intended trade direction.

    Args:
        closes: Historical closing prices (oldest first).
        volumes: Historical volumes matching *closes* (oldest first).
        direction: +1 for long, -1 for short, 0 for flat/neutral.
        min_ratio: Minimum current-volume / avg-volume ratio required.
        lookback: Number of past days used for averages.

    Returns:
        VolumeConfirmation with confirmation flag and diagnostics.
    """
    required = lookback + 1

    if len(closes) < required or len(volumes) < required:
        detail = (
            f"Insufficient data: need {required} bars, "
            f"got closes={len(closes)} volumes={len(volumes)}"
        )
        logger.warning("Volume confirm: %s", detail)
        return VolumeConfirmation(
            confirmed=False, volume_ratio=0.0, trend_volume_ratio=0.0, detail=detail,
        )

    current_volume = volumes[-1]
    avg_volume = mean(volumes[-lookback - 1 : -1])
    volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0.0

    # Classify each day in the lookback window as up or down
    up_volumes: list[float] = []
    down_volumes: list[float] = []
    for i in range(-lookback, 0):
        if closes[i] > closes[i - 1]:
            up_volumes.append(volumes[i])
        elif closes[i] < closes[i - 1]:
            down_volumes.append(volumes[i])

    avg_up_volume = mean(up_volumes) if up_volumes else 1.0
    avg_down_volume = mean(down_volumes) if down_volumes else 1.0
    trend_volume_ratio = avg_up_volume / avg_down_volume

    # Confirmation rules
    if direction == 1:
        confirmed = (volume_ratio >= min_ratio) and (trend_volume_ratio >= 1.0)
    elif direction == -1:
        confirmed = (volume_ratio >= min_ratio) and (trend_volume_ratio <= 1.0)
    else:
        confirmed = False

    detail = (
        f"dir={direction:+d} vol_ratio={volume_ratio:.2f} "
        f"trend_vol_ratio={trend_volume_ratio:.2f} "
        f"min_ratio={min_ratio:.2f} → {'confirmed' if confirmed else 'rejected'}"
    )

    logger.info("Volume confirm: %s", detail)
    return VolumeConfirmation(
        confirmed=confirmed,
        volume_ratio=volume_ratio,
        trend_volume_ratio=trend_volume_ratio,
        detail=detail,
    )
