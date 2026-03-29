"""Chart Formations — Detect geometric chart patterns from price data.

Identifies classic chart patterns (double bottom/top, head & shoulders,
triangles, cup-and-handle, support/resistance) using local peak/trough
detection.  Reliability figures sourced from Bulkowski's research.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ChartFormation:
    """A single detected chart formation."""

    name: str
    name_jp: str
    direction: int  # +1 bullish, -1 bearish, 0 neutral
    reliability: float  # Bulkowski's measured reliability
    target_pct: float  # expected move % based on pattern measurement
    detail: str


@dataclass
class FormationAnalysis:
    """Aggregated result of chart formation detection."""

    formations: list[ChartFormation] = field(default_factory=list)
    signal_direction: int = 0
    signal_strength: float = 0.0
    detail: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_peaks_troughs(
    prices: list[float],
    order: int = 3,
) -> tuple[list[int], list[int]]:
    """Find local maxima (peaks) and minima (troughs).

    *order*: number of points on each side to compare.
    """
    peaks: list[int] = []
    troughs: list[int] = []
    for i in range(order, len(prices) - order):
        if all(prices[i] >= prices[i - j] for j in range(1, order + 1)) and all(
            prices[i] >= prices[i + j] for j in range(1, order + 1)
        ):
            peaks.append(i)
        if all(prices[i] <= prices[i - j] for j in range(1, order + 1)) and all(
            prices[i] <= prices[i + j] for j in range(1, order + 1)
        ):
            troughs.append(i)
    return peaks, troughs


def _find_support_resistance(
    closes: list[float],
    lows: list[float],
    highs: list[float],
    lookback: int = 20,
) -> tuple[list[float], list[float]]:
    """Find support and resistance levels from recent price action.

    Support: cluster of lows within 1.5% of each other.
    Resistance: cluster of highs within 1.5% of each other.
    """
    recent_lows = lows[-lookback:]
    recent_highs = highs[-lookback:]
    tolerance = 0.015

    supports: list[float] = _cluster_levels(recent_lows, tolerance)
    resistances: list[float] = _cluster_levels(recent_highs, tolerance)
    return supports, resistances


def _cluster_levels(values: list[float], tolerance: float) -> list[float]:
    """Group nearby price levels and return those with 2+ touches."""
    if not values:
        return []
    sorted_vals = sorted(values)
    clusters: list[list[float]] = [[sorted_vals[0]]]
    for v in sorted_vals[1:]:
        if abs(v - clusters[-1][0]) / clusters[-1][0] <= tolerance:
            clusters[-1].append(v)
        else:
            clusters.append([v])
    return [sum(c) / len(c) for c in clusters if len(c) >= 2]


def _pct_diff(a: float, b: float) -> float:
    """Absolute percentage difference between two values."""
    if a == 0:
        return 0.0
    return abs(a - b) / abs(a)


# ---------------------------------------------------------------------------
# Individual pattern detectors
# ---------------------------------------------------------------------------

def _detect_double_bottom(
    closes: list[float],
    highs: list[float],
    lows: list[float],
    troughs: list[int],
    peaks: list[int],
) -> ChartFormation | None:
    """Double Bottom: two lows ~same level, peak between, price near neckline."""
    # Need at least 2 troughs
    if len(troughs) < 2:
        return None

    for i in range(len(troughs) - 1):
        t1, t2 = troughs[i], troughs[i + 1]
        if t2 - t1 < 5:
            continue
        low1, low2 = lows[t1], lows[t2]
        if _pct_diff(low1, low2) > 0.03:
            continue
        # Find highest peak between the two troughs
        between_peaks = [p for p in peaks if t1 < p < t2]
        if not between_peaks:
            continue
        neckline_idx = max(between_peaks, key=lambda p: highs[p])
        neckline = highs[neckline_idx]
        bottom = min(low1, low2)
        target_pct = (neckline - bottom) / bottom * 100
        current = closes[-1]
        # Current price should be near or above neckline
        if current >= neckline * 0.97:
            return ChartFormation(
                name="Double Bottom",
                name_jp="ダブルボトム",
                direction=1,
                reliability=0.78,
                target_pct=round(target_pct, 2),
                detail=(
                    f"Lows at idx {t1}({low1:.2f}) & {t2}({low2:.2f}), "
                    f"neckline {neckline:.2f}, target +{target_pct:.1f}%"
                ),
            )
    return None


def _detect_double_top(
    closes: list[float],
    highs: list[float],
    lows: list[float],
    peaks: list[int],
    troughs: list[int],
) -> ChartFormation | None:
    """Double Top: two highs ~same level, trough between, price near neckline."""
    if len(peaks) < 2:
        return None

    for i in range(len(peaks) - 1):
        p1, p2 = peaks[i], peaks[i + 1]
        if p2 - p1 < 5:
            continue
        high1, high2 = highs[p1], highs[p2]
        if _pct_diff(high1, high2) > 0.03:
            continue
        between_troughs = [t for t in troughs if p1 < t < p2]
        if not between_troughs:
            continue
        neckline_idx = min(between_troughs, key=lambda t: lows[t])
        neckline = lows[neckline_idx]
        top = max(high1, high2)
        target_pct = (top - neckline) / top * 100
        current = closes[-1]
        if current <= neckline * 1.03:
            return ChartFormation(
                name="Double Top",
                name_jp="ダブルトップ",
                direction=-1,
                reliability=0.75,
                target_pct=round(target_pct, 2),
                detail=(
                    f"Highs at idx {p1}({high1:.2f}) & {p2}({high2:.2f}), "
                    f"neckline {neckline:.2f}, target -{target_pct:.1f}%"
                ),
            )
    return None


def _detect_ascending_triangle(
    closes: list[float],
    highs: list[float],
    lows: list[float],
    peaks: list[int],
    troughs: list[int],
) -> ChartFormation | None:
    """Ascending Triangle: flat resistance, rising support."""
    if len(peaks) < 3 or len(troughs) < 2:
        return None

    # Check flat resistance: last 3+ peaks within 2%
    recent_peaks = peaks[-4:]
    peak_highs = [highs[p] for p in recent_peaks]
    avg_resistance = sum(peak_highs) / len(peak_highs)
    flat = all(_pct_diff(avg_resistance, h) <= 0.02 for h in peak_highs)
    if not flat:
        return None

    # Check rising support
    recent_troughs = troughs[-3:]
    if len(recent_troughs) < 2:
        return None
    trough_lows = [lows[t] for t in recent_troughs]
    rising = all(trough_lows[j] >= trough_lows[j - 1] * 0.99 for j in range(1, len(trough_lows)))
    if not rising or trough_lows[-1] <= trough_lows[0]:
        return None

    height = avg_resistance - trough_lows[0]
    target_pct = height / trough_lows[0] * 100

    return ChartFormation(
        name="Ascending Triangle",
        name_jp="上昇三角形",
        direction=1,
        reliability=0.75,
        target_pct=round(target_pct, 2),
        detail=(
            f"Flat resistance ~{avg_resistance:.2f} ({len(recent_peaks)} touches), "
            f"rising support, target +{target_pct:.1f}%"
        ),
    )


def _detect_descending_triangle(
    closes: list[float],
    highs: list[float],
    lows: list[float],
    peaks: list[int],
    troughs: list[int],
) -> ChartFormation | None:
    """Descending Triangle: flat support, falling resistance."""
    if len(troughs) < 3 or len(peaks) < 2:
        return None

    recent_troughs = troughs[-4:]
    trough_lows = [lows[t] for t in recent_troughs]
    avg_support = sum(trough_lows) / len(trough_lows)
    flat = all(_pct_diff(avg_support, lo) <= 0.02 for lo in trough_lows)
    if not flat:
        return None

    recent_peaks = peaks[-3:]
    if len(recent_peaks) < 2:
        return None
    peak_highs = [highs[p] for p in recent_peaks]
    falling = all(peak_highs[j] <= peak_highs[j - 1] * 1.01 for j in range(1, len(peak_highs)))
    if not falling or peak_highs[-1] >= peak_highs[0]:
        return None

    height = peak_highs[0] - avg_support
    target_pct = height / peak_highs[0] * 100

    return ChartFormation(
        name="Descending Triangle",
        name_jp="下降三角形",
        direction=-1,
        reliability=0.72,
        target_pct=round(target_pct, 2),
        detail=(
            f"Flat support ~{avg_support:.2f} ({len(recent_troughs)} touches), "
            f"falling resistance, target -{target_pct:.1f}%"
        ),
    )


def _detect_head_and_shoulders(
    closes: list[float],
    highs: list[float],
    lows: list[float],
    peaks: list[int],
    troughs: list[int],
) -> ChartFormation | None:
    """Head and Shoulders: left shoulder, higher head, right shoulder ~= left."""
    if len(peaks) < 3 or len(troughs) < 2:
        return None

    for i in range(len(peaks) - 2):
        ls, head, rs = peaks[i], peaks[i + 1], peaks[i + 2]
        h_ls, h_head, h_rs = highs[ls], highs[head], highs[rs]

        # Head must be higher than both shoulders
        if h_head <= h_ls or h_head <= h_rs:
            continue
        # Shoulders roughly equal (within 5%)
        if _pct_diff(h_ls, h_rs) > 0.05:
            continue

        # Find troughs between shoulders and head
        t_between_1 = [t for t in troughs if ls < t < head]
        t_between_2 = [t for t in troughs if head < t < rs]
        if not t_between_1 or not t_between_2:
            continue

        nl1 = lows[min(t_between_1, key=lambda t: lows[t])]
        nl2 = lows[min(t_between_2, key=lambda t: lows[t])]
        neckline = (nl1 + nl2) / 2
        target_pct = (h_head - neckline) / h_head * 100

        current = closes[-1]
        if current <= neckline * 1.03:
            return ChartFormation(
                name="Head and Shoulders",
                name_jp="三尊天井",
                direction=-1,
                reliability=0.83,
                target_pct=round(target_pct, 2),
                detail=(
                    f"LS({h_ls:.2f}) Head({h_head:.2f}) RS({h_rs:.2f}), "
                    f"neckline {neckline:.2f}, target -{target_pct:.1f}%"
                ),
            )
    return None


def _detect_inverse_head_and_shoulders(
    closes: list[float],
    highs: list[float],
    lows: list[float],
    peaks: list[int],
    troughs: list[int],
) -> ChartFormation | None:
    """Inverse Head and Shoulders: bullish reversal."""
    if len(troughs) < 3 or len(peaks) < 2:
        return None

    for i in range(len(troughs) - 2):
        ls, head, rs = troughs[i], troughs[i + 1], troughs[i + 2]
        l_ls, l_head, l_rs = lows[ls], lows[head], lows[rs]

        # Head must be lower than both shoulders
        if l_head >= l_ls or l_head >= l_rs:
            continue
        # Shoulders roughly equal
        if _pct_diff(l_ls, l_rs) > 0.05:
            continue

        # Peaks between troughs form neckline
        p_between_1 = [p for p in peaks if ls < p < head]
        p_between_2 = [p for p in peaks if head < p < rs]
        if not p_between_1 or not p_between_2:
            continue

        nl1 = highs[max(p_between_1, key=lambda p: highs[p])]
        nl2 = highs[max(p_between_2, key=lambda p: highs[p])]
        neckline = (nl1 + nl2) / 2
        target_pct = (neckline - l_head) / l_head * 100

        current = closes[-1]
        if current >= neckline * 0.97:
            return ChartFormation(
                name="Inverse Head and Shoulders",
                name_jp="逆三尊",
                direction=1,
                reliability=0.83,
                target_pct=round(target_pct, 2),
                detail=(
                    f"LS({l_ls:.2f}) Head({l_head:.2f}) RS({l_rs:.2f}), "
                    f"neckline {neckline:.2f}, target +{target_pct:.1f}%"
                ),
            )
    return None


def _detect_cup_and_handle(
    closes: list[float],
    highs: list[float],
    lows: list[float],
    peaks: list[int],
    troughs: list[int],
) -> ChartFormation | None:
    """Cup and Handle: U-shaped recovery + small pullback."""
    if len(peaks) < 2 or len(troughs) < 2:
        return None

    n = len(closes)
    # Look for a U-shape: left rim peak, bottom trough, right rim peak
    for i in range(len(peaks) - 1):
        left_rim = peaks[i]
        right_rim = peaks[i + 1]
        if right_rim - left_rim < 8:
            continue

        # Find lowest trough between rims (cup bottom)
        cup_troughs = [t for t in troughs if left_rim < t < right_rim]
        if not cup_troughs:
            continue
        cup_bottom_idx = min(cup_troughs, key=lambda t: lows[t])
        cup_bottom = lows[cup_bottom_idx]

        left_h = highs[left_rim]
        right_h = highs[right_rim]

        # Rims should be roughly same height (within 5%)
        if _pct_diff(left_h, right_h) > 0.05:
            continue

        # Cup should have meaningful depth (at least 5%)
        rim_avg = (left_h + right_h) / 2
        depth_pct = (rim_avg - cup_bottom) / rim_avg
        if depth_pct < 0.05:
            continue

        # U-shape check: bottom should be roughly centered
        center = (left_rim + right_rim) / 2
        if abs(cup_bottom_idx - center) > (right_rim - left_rim) * 0.35:
            continue

        # Handle: small pullback after right rim
        if right_rim >= n - 2:
            continue
        handle_slice = closes[right_rim:n]
        handle_low = min(handle_slice)
        handle_pullback = (right_h - handle_low) / right_h
        # Handle should be shallow (< 50% of cup depth)
        if handle_pullback > depth_pct * 0.5:
            continue

        target_pct = depth_pct * 100

        return ChartFormation(
            name="Cup and Handle",
            name_jp="カップウィズハンドル",
            direction=1,
            reliability=0.68,
            target_pct=round(target_pct, 2),
            detail=(
                f"Cup depth {depth_pct * 100:.1f}%, "
                f"rim ~{rim_avg:.2f}, handle pullback {handle_pullback * 100:.1f}%"
            ),
        )
    return None


def _detect_support_bounce(
    closes: list[float],
    highs: list[float],
    lows: list[float],
    lookback: int,
) -> ChartFormation | None:
    """Support Bounce: price touching support that held 2+ times, bouncing up."""
    supports, _ = _find_support_resistance(closes, lows, highs, lookback)
    if not supports:
        return None

    current = closes[-1]
    recent_low = min(lows[-3:])

    for level in supports:
        # Current price near support (within 2%)
        if _pct_diff(level, recent_low) <= 0.02:
            # Price bouncing (current close above recent low)
            if current > recent_low * 1.005:
                bounce_pct = (current - recent_low) / recent_low * 100
                return ChartFormation(
                    name="Support Bounce",
                    name_jp="サポートバウンス",
                    direction=1,
                    reliability=0.65,
                    target_pct=round(bounce_pct * 2, 2),  # target = 2x bounce
                    detail=(
                        f"Support at {level:.2f}, recent low {recent_low:.2f}, "
                        f"bouncing +{bounce_pct:.2f}%"
                    ),
                )
    return None


def _detect_resistance_break(
    closes: list[float],
    highs: list[float],
    lows: list[float],
    lookback: int,
) -> ChartFormation | None:
    """Resistance Break: price breaking above prior resistance."""
    _, resistances = _find_support_resistance(closes, lows, highs, lookback)
    if not resistances:
        return None

    current = closes[-1]
    prev_close = closes[-2] if len(closes) >= 2 else current

    for level in resistances:
        # Breaking above resistance: was below, now above
        if prev_close <= level and current > level:
            break_pct = (current - level) / level * 100
            return ChartFormation(
                name="Resistance Break",
                name_jp="レジスタンスブレイク",
                direction=1,
                reliability=0.70,
                target_pct=round(break_pct + 2.0, 2),  # measured move
                detail=(
                    f"Resistance at {level:.2f} broken, "
                    f"current {current:.2f} (+{break_pct:.2f}%)"
                ),
            )
    return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def analyze_formations(
    closes: list[float],
    highs: list[float],
    lows: list[float],
    lookback: int = 20,
) -> FormationAnalysis:
    """Analyze price data for chart formations.

    Parameters
    ----------
    closes : list[float]
        Closing prices.
    highs : list[float]
        High prices.
    lows : list[float]
        Low prices.
    lookback : int
        Minimum data points required / lookback window.

    Returns
    -------
    FormationAnalysis
        All detected formations with aggregate signal.
    """
    n = len(closes)
    if n < lookback or len(highs) != n or len(lows) != n:
        return FormationAnalysis(
            detail=f"Insufficient data: {n} bars (need {lookback})",
        )

    # Use data within lookback window
    c = closes[-lookback:]
    h = highs[-lookback:]
    lo = lows[-lookback:]

    order = max(2, min(5, lookback // 6))
    peaks, troughs = _find_peaks_troughs(c, order=order)

    formations: list[ChartFormation] = []

    detectors = [
        lambda: _detect_double_bottom(c, h, lo, troughs, peaks),
        lambda: _detect_double_top(c, h, lo, peaks, troughs),
        lambda: _detect_ascending_triangle(c, h, lo, peaks, troughs),
        lambda: _detect_descending_triangle(c, h, lo, peaks, troughs),
        lambda: _detect_head_and_shoulders(c, h, lo, peaks, troughs),
        lambda: _detect_inverse_head_and_shoulders(c, h, lo, peaks, troughs),
        lambda: _detect_cup_and_handle(c, h, lo, peaks, troughs),
        lambda: _detect_support_bounce(c, h, lo, lookback),
        lambda: _detect_resistance_break(c, h, lo, lookback),
    ]

    for detect in detectors:
        try:
            result = detect()
            if result is not None:
                formations.append(result)
        except Exception:
            logger.debug("Pattern detector error", exc_info=True)

    # Aggregate signal
    if not formations:
        return FormationAnalysis(detail="No chart formations detected")

    weighted_dir = sum(f.direction * f.reliability for f in formations)
    total_weight = sum(f.reliability for f in formations)
    avg_dir = weighted_dir / total_weight if total_weight else 0.0

    if avg_dir > 0.2:
        signal_direction = 1
    elif avg_dir < -0.2:
        signal_direction = -1
    else:
        signal_direction = 0

    signal_strength = min(1.0, abs(avg_dir) * len(formations) / 2)
    names = [f"{f.name_jp}({f.name})" for f in formations]

    return FormationAnalysis(
        formations=formations,
        signal_direction=signal_direction,
        signal_strength=round(signal_strength, 3),
        detail=f"Detected: {', '.join(names)} → direction={signal_direction}",
    )
