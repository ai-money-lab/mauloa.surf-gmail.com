"""NY-Nikkei Overnight Correlation Signal.

The STRONGEST statistical edge: NY Dow/S&P500 performance predicts
next-day Nikkei movement with ~0.898 correlation.

Logic:
    - Calculate rolling Pearson correlation between NY daily returns
      and next-day Nikkei returns over a lookback window.
    - Latest NY change > +0.3% and correlation > 0.5 → bullish (+1)
    - Latest NY change < -0.3% and correlation > 0.5 → bearish (-1)
    - Otherwise → neutral (0)
    - Confidence = abs(ny_change) * correlation, capped at 0.9
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class NYNikkeiSignal:
    """Result of NY-Nikkei overnight correlation analysis."""

    direction: int  # +1=bullish, -1=bearish, 0=neutral
    confidence: float  # 0.0-1.0
    ny_change_pct: float  # overnight US market change %
    correlation_strength: float
    detail: str


def _pearson_correlation(x: list[float], y: list[float]) -> float:
    """Calculate Pearson correlation coefficient between two sequences.

    Returns 0.0 if inputs are too short or have zero variance.
    """
    n = len(x)
    if n != len(y) or n < 2:
        return 0.0

    mean_x = sum(x) / n
    mean_y = sum(y) / n

    cov = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    var_x = sum((xi - mean_x) ** 2 for xi in x)
    var_y = sum((yi - mean_y) ** 2 for yi in y)

    denom = math.sqrt(var_x * var_y)
    if denom == 0.0:
        return 0.0

    return cov / denom


def compute_ny_nikkei_signal(
    ny_closes: list[float],
    nikkei_closes: list[float],
    lookback: int = 20,
) -> NYNikkeiSignal:
    """Compute signal based on NY-Nikkei overnight correlation.

    Parameters
    ----------
    ny_closes:
        Recent NY (Dow / S&P500) closing prices, oldest first.
    nikkei_closes:
        Recent Nikkei closing prices, oldest first.
        nikkei_closes[i] corresponds to the trading day **after** ny_closes[i].
    lookback:
        Number of return pairs to use for the rolling correlation.
    """
    # Need at least 2 closes to compute 1 return
    if len(ny_closes) < 2 or len(nikkei_closes) < 2:
        return NYNikkeiSignal(
            direction=0,
            confidence=0.0,
            ny_change_pct=0.0,
            correlation_strength=0.0,
            detail="Insufficient data for correlation calculation",
        )

    # Daily returns: ret[i] = (close[i+1] - close[i]) / close[i] * 100
    ny_returns = [
        (ny_closes[i + 1] - ny_closes[i]) / ny_closes[i] * 100
        for i in range(len(ny_closes) - 1)
    ]
    nikkei_returns = [
        (nikkei_closes[i + 1] - nikkei_closes[i]) / nikkei_closes[i] * 100
        for i in range(len(nikkei_closes) - 1)
    ]

    # Align: NY return[i] predicts next-day Nikkei return[i+1]
    # So pair ny_returns[:-1] with nikkei_returns[1:]
    if len(ny_returns) < 2 or len(nikkei_returns) < 2:
        return NYNikkeiSignal(
            direction=0,
            confidence=0.0,
            ny_change_pct=0.0,
            correlation_strength=0.0,
            detail="Insufficient return data for correlation",
        )

    ny_for_corr = ny_returns[:-1]
    nk_for_corr = nikkei_returns[1:]

    # Trim to common length then take last `lookback` pairs
    common_len = min(len(ny_for_corr), len(nk_for_corr))
    ny_for_corr = ny_for_corr[-min(common_len, lookback):]
    nk_for_corr = nk_for_corr[-min(common_len, lookback):]

    correlation = _pearson_correlation(ny_for_corr, nk_for_corr)

    # Latest NY overnight change
    ny_change_pct = (ny_closes[-1] - ny_closes[-2]) / ny_closes[-2] * 100

    # Decision logic
    direction = 0
    if correlation > 0.5:
        if ny_change_pct > 0.3:
            direction = 1
        elif ny_change_pct < -0.3:
            direction = -1

    # Confidence = |ny_change| * correlation, capped at 0.9
    confidence = min(abs(ny_change_pct) * abs(correlation), 0.9)

    label = {1: "BULLISH", -1: "BEARISH", 0: "NEUTRAL"}[direction]
    detail = (
        f"{label}: NY change={ny_change_pct:+.2f}%, "
        f"correlation={correlation:.3f} (lookback={len(ny_for_corr)}d)"
    )

    return NYNikkeiSignal(
        direction=direction,
        confidence=round(confidence, 4),
        ny_change_pct=round(ny_change_pct, 4),
        correlation_strength=round(correlation, 4),
        detail=detail,
    )
