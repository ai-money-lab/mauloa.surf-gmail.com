"""Support & Resistance Level Detection.

Identifies key price levels where buying/selling pressure has historically
concentrated, then scores each level by touch count and recency.

Logic:
    - Find local minima (support) and maxima (resistance) using ±2 neighbors
    - Cluster nearby levels within tolerance_pct%
    - Score by touches × recency decay
    - Signal: buy near strong support, sell near strong resistance,
      breakout above resistance, breakdown below support
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PriceLevel:
    """A detected support or resistance price level."""

    price: float
    level_type: str  # "support" or "resistance"
    touches: int  # how many times price touched this level
    strength: float  # 0.0-1.0, based on touches and recency
    last_touch_idx: int  # index of last touch
    detail: str = ""


@dataclass
class SRAnalysis:
    """Result of support/resistance analysis."""

    supports: list[PriceLevel] = field(default_factory=list)
    resistances: list[PriceLevel] = field(default_factory=list)
    nearest_support: PriceLevel | None = None
    nearest_resistance: PriceLevel | None = None
    position: str = "mid_range"
    signal_direction: int = 0  # +1=buy, -1=sell, 0=neutral
    signal_strength: float = 0.0
    detail: str = ""


def _find_local_extrema(
    data: list[float],
    start: int,
    end: int,
) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    """Return (minima, maxima) as lists of (index, value)."""
    minima: list[tuple[int, float]] = []
    maxima: list[tuple[int, float]] = []
    for i in range(max(start, 2), min(end, len(data) - 2)):
        val = data[i]
        if val <= data[i - 1] and val <= data[i - 2] and val <= data[i + 1] and val <= data[i + 2]:
            minima.append((i, val))
        if val >= data[i - 1] and val >= data[i - 2] and val >= data[i + 1] and val >= data[i + 2]:
            maxima.append((i, val))
    return minima, maxima


def _cluster_levels(
    points: list[tuple[int, float]],
    tolerance_pct: float,
) -> list[tuple[float, list[int]]]:
    """Cluster nearby price points. Returns list of (avg_price, [indices])."""
    if not points:
        return []
    sorted_pts = sorted(points, key=lambda p: p[1])
    clusters: list[tuple[float, list[int]]] = []
    current_prices: list[float] = [sorted_pts[0][1]]
    current_idxs: list[int] = [sorted_pts[0][0]]

    for idx, price in sorted_pts[1:]:
        avg = sum(current_prices) / len(current_prices)
        if abs(price - avg) / avg * 100 <= tolerance_pct:
            current_prices.append(price)
            current_idxs.append(idx)
        else:
            clusters.append((sum(current_prices) / len(current_prices), current_idxs))
            current_prices = [price]
            current_idxs = [idx]
    clusters.append((sum(current_prices) / len(current_prices), current_idxs))
    return clusters


def _count_touches(
    closes: list[float],
    highs: list[float],
    lows: list[float],
    level: float,
    tolerance_pct: float,
    start: int,
    end: int,
) -> tuple[int, int]:
    """Count how many bars touch the level. Returns (count, last_touch_idx)."""
    tol = level * tolerance_pct / 100
    count = 0
    last_idx = start
    for i in range(start, min(end, len(closes))):
        if lows[i] - tol <= level <= highs[i] + tol:
            count += 1
            last_idx = i
    return count, last_idx


def analyze_support_resistance(
    closes: list[float],
    highs: list[float],
    lows: list[float],
    lookback: int = 50,
    tolerance_pct: float = 1.0,
) -> SRAnalysis:
    """Detect support and resistance levels from price data.

    Parameters
    ----------
    closes:
        List of closing prices.
    highs:
        List of high prices.
    lows:
        List of low prices.
    lookback:
        Number of bars to look back for level detection.
    tolerance_pct:
        Percentage tolerance for clustering and touch detection.

    Returns
    -------
    SRAnalysis with detected levels, position, and signal.
    """
    n = len(closes)
    if n < 5:
        return SRAnalysis(detail="insufficient data (need >= 5 bars)")

    start = max(0, n - lookback)
    current_price = closes[-1]

    # Step a: find local extrema
    minima, maxima = _find_local_extrema(lows, start, n)
    # Also use closes for extrema on highs
    min_h, max_h = _find_local_extrema(highs, start, n)
    maxima = maxima + max_h
    # Deduplicate by index
    seen: set[int] = set()
    unique_maxima: list[tuple[int, float]] = []
    for idx, val in maxima:
        if idx not in seen:
            seen.add(idx)
            unique_maxima.append((idx, val))
    maxima = unique_maxima

    # Step b: cluster nearby levels
    support_clusters = _cluster_levels(minima, tolerance_pct)
    resistance_clusters = _cluster_levels(maxima, tolerance_pct)

    # Step c: build PriceLevels with touch counts and scoring
    max_touches = 1  # avoid div by zero

    supports: list[PriceLevel] = []
    resistances: list[PriceLevel] = []

    for avg_price, _idxs in support_clusters:
        touches, last_touch = _count_touches(
            closes, highs, lows, avg_price, tolerance_pct, start, n,
        )
        max_touches = max(max_touches, touches)
        supports.append(PriceLevel(
            price=round(avg_price, 4),
            level_type="support",
            touches=touches,
            strength=0.0,  # filled below
            last_touch_idx=last_touch,
        ))

    for avg_price, _idxs in resistance_clusters:
        touches, last_touch = _count_touches(
            closes, highs, lows, avg_price, tolerance_pct, start, n,
        )
        max_touches = max(max_touches, touches)
        resistances.append(PriceLevel(
            price=round(avg_price, 4),
            level_type="resistance",
            touches=touches,
            strength=0.0,
            last_touch_idx=last_touch,
        ))

    # Score strength with recency decay
    for level in supports + resistances:
        recency = 1.0 - (n - 1 - level.last_touch_idx) / max(n, 1)
        recency = max(0.1, recency)
        level.strength = round(min(1.0, (level.touches / max_touches) * recency), 4)
        level.detail = (
            f"{level.level_type} at {level.price}, "
            f"{level.touches} touches, strength={level.strength}"
        )

    # Sort: strongest first
    supports.sort(key=lambda lv: lv.strength, reverse=True)
    resistances.sort(key=lambda lv: lv.strength, reverse=True)

    # Step d: nearest support/resistance
    nearest_support: PriceLevel | None = None
    nearest_resistance: PriceLevel | None = None
    for s in supports:
        if s.price <= current_price:
            if nearest_support is None or s.price > nearest_support.price:
                nearest_support = s
    for r in resistances:
        if r.price >= current_price:
            if nearest_resistance is None or r.price < nearest_resistance.price:
                nearest_resistance = r

    # Step e: determine position
    near_tol = 1.0  # percent
    position = "mid_range"
    if nearest_support and abs(current_price - nearest_support.price) / current_price * 100 <= near_tol:
        position = "near_support"
    elif nearest_resistance and abs(current_price - nearest_resistance.price) / current_price * 100 <= near_tol:
        position = "near_resistance"
    elif not nearest_support and nearest_resistance:
        # below all supports
        if supports:
            position = "below_support"
        else:
            position = "mid_range"
    elif not nearest_resistance and nearest_support:
        if resistances:
            position = "above_resistance"
        else:
            position = "mid_range"
    elif not nearest_support and not nearest_resistance:
        # No levels detected
        if supports and current_price < min(s.price for s in supports):
            position = "below_support"
        elif resistances and current_price > max(r.price for r in resistances):
            position = "above_resistance"

    # Step f: signal
    direction = 0
    strength = 0.0
    if position == "near_support" and nearest_support and nearest_support.touches >= 3:
        direction = 1
        strength = nearest_support.strength
    elif position == "near_resistance" and nearest_resistance and nearest_resistance.touches >= 3:
        direction = -1
        strength = nearest_resistance.strength
    elif position == "below_support":
        direction = -1
        strength = 0.5
    elif position == "above_resistance":
        direction = 1
        strength = 0.5

    detail_parts = [
        f"price={current_price}, position={position}",
        f"supports={len(supports)}, resistances={len(resistances)}",
    ]
    if nearest_support:
        detail_parts.append(f"nearest_support={nearest_support.price}")
    if nearest_resistance:
        detail_parts.append(f"nearest_resistance={nearest_resistance.price}")

    return SRAnalysis(
        supports=supports,
        resistances=resistances,
        nearest_support=nearest_support,
        nearest_resistance=nearest_resistance,
        position=position,
        signal_direction=direction,
        signal_strength=round(strength, 4),
        detail="; ".join(detail_parts),
    )
