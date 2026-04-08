"""Pre-Market Trio Signal — CME夜間先物 + USD/JPY + VIX の3点セット.

The strongest pre-open signal complex: when all three align,
same-day directional prediction accuracy is significantly higher.

Signal appears: overnight (US session)
Signal resolves: first 1-2 hours of Tokyo session

Data sources:
    - CME Nikkei 225 futures (NKD=F via yfinance, or kabuStation)
    - USD/JPY (USDJPY=X via yfinance, or Twelve Data)
    - VIX (^VIX via yfinance, or FRED API)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PremarketSignal:
    """Result of pre-market trio analysis."""
    direction: int          # +1=bullish, -1=bearish, 0=neutral
    confidence: float       # 0.0-1.0
    nkd_change_pct: float   # CME Nikkei 225 futures % change
    usdjpy_change_pct: float  # USD/JPY % change (positive = yen weakness = bullish)
    vix_level: float        # VIX absolute level
    vix_change_pct: float   # VIX % change (negative = risk-on = bullish)
    signals_aligned: int    # how many of 3 agree (0-3)
    detail: str


def compute_premarket_trio(
    nkd_change_pct: float,
    usdjpy_change_pct: float,
    vix_level: float,
    vix_change_pct: float,
    nikkei_vi: float | None = None,
) -> PremarketSignal:
    """Compute the pre-market trio directional signal.

    Args:
        nkd_change_pct: CME Nikkei 225 futures overnight change %
        usdjpy_change_pct: USD/JPY overnight change % (positive = yen weaker)
        vix_level: VIX closing level
        vix_change_pct: VIX overnight change %
        nikkei_vi: Optional 日経VI level (replaces VIX for JP-specific assessment)

    Returns:
        PremarketSignal with direction, confidence, and detail.
    """
    votes: list[int] = []
    reasons: list[str] = []

    # Signal 1: CME Nikkei futures direction
    if nkd_change_pct > 0.1:
        votes.append(+1)
        reasons.append(f"CME先物+{nkd_change_pct:.2f}%")
    elif nkd_change_pct < -0.1:
        votes.append(-1)
        reasons.append(f"CME先物{nkd_change_pct:.2f}%")
    else:
        votes.append(0)
        reasons.append(f"CME先物横ばい({nkd_change_pct:+.2f}%)")

    # Signal 2: USD/JPY direction (yen weak = bullish for exporters/Nikkei)
    if usdjpy_change_pct > 0.1:
        votes.append(+1)
        reasons.append(f"円安+{usdjpy_change_pct:.2f}%")
    elif usdjpy_change_pct < -0.1:
        votes.append(-1)
        reasons.append(f"円高{usdjpy_change_pct:.2f}%")
    else:
        votes.append(0)
        reasons.append(f"ドル円横ばい({usdjpy_change_pct:+.2f}%)")

    # Signal 3: VIX level and direction (low/falling = bullish)
    vi_level = nikkei_vi if nikkei_vi is not None else vix_level
    vi_name = "日経VI" if nikkei_vi is not None else "VIX"

    if vix_change_pct < -3.0 or vi_level < 15:
        votes.append(+1)
        reasons.append(f"{vi_name}={vi_level:.1f}(変動{vix_change_pct:+.1f}%) リスクオン")
    elif vix_change_pct > 5.0 or vi_level > 30:
        votes.append(-1)
        reasons.append(f"{vi_name}={vi_level:.1f}(変動{vix_change_pct:+.1f}%) リスクオフ")
    else:
        votes.append(0)
        reasons.append(f"{vi_name}={vi_level:.1f}(変動{vix_change_pct:+.1f}%) 中立")

    # Aggregate
    bullish = sum(1 for v in votes if v > 0)
    bearish = sum(1 for v in votes if v < 0)
    aligned = max(bullish, bearish)

    if bullish >= 2:
        direction = +1
    elif bearish >= 2:
        direction = -1
    else:
        direction = 0

    # Confidence based on alignment and magnitude
    base_confidence = aligned / 3.0
    magnitude_boost = min(abs(nkd_change_pct) / 2.0, 0.2)  # up to +0.2 for large moves
    confidence = min(base_confidence + magnitude_boost, 1.0)

    # High VIX regime reduces confidence (more noise)
    if vi_level > 30:
        confidence *= 0.7
        reasons.append(f"⚠ 高ボラ({vi_name}>{30})で信頼度低下")

    detail = " | ".join(reasons)

    signal = PremarketSignal(
        direction=direction,
        confidence=round(confidence, 3),
        nkd_change_pct=nkd_change_pct,
        usdjpy_change_pct=usdjpy_change_pct,
        vix_level=vix_level,
        vix_change_pct=vix_change_pct,
        signals_aligned=aligned,
        detail=detail,
    )

    logger.info(
        "PremarketTrio: direction=%+d confidence=%.2f aligned=%d/3 [%s]",
        direction, confidence, aligned, detail,
    )
    return signal
