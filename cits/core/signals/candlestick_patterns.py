"""Candlestick Pattern Recognition Engine.

Detects Japanese candlestick patterns from OHLCV data and returns
their statistical edge based on academic research (Thomas Bulkowski et al.).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class CandlePattern:
    """A single detected candlestick pattern."""

    name: str
    name_jp: str
    direction: int  # +1 bullish, -1 bearish, 0 neutral
    reliability: float  # 0.0-1.0
    detail: str


@dataclass
class CandlestickAnalysis:
    """Aggregated result of candlestick pattern analysis."""

    patterns: list[CandlePattern] = field(default_factory=list)
    signal_direction: int = 0  # +1 bullish, -1 bearish, 0 neutral
    signal_strength: float = 0.0  # 0.0-1.0
    detail: str = ""


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _body_size(o: float, c: float) -> float:
    return abs(c - o)


def _upper_shadow(o: float, h: float, c: float) -> float:
    return h - max(o, c)


def _lower_shadow(o: float, lo: float, c: float) -> float:
    return min(o, c) - lo


def _is_bullish(o: float, c: float) -> bool:
    return c > o


def _is_bearish(o: float, c: float) -> bool:
    return c < o


def _is_doji(o: float, h: float, lo: float, c: float) -> bool:
    if h == lo:
        return True
    return _body_size(o, c) <= (h - lo) * 0.05


def _day_range(h: float, lo: float) -> float:
    return h - lo


def _in_downtrend(closes: list[float], lookback: int = 3) -> bool:
    """Check for 3+ consecutive lower closes."""
    if len(closes) < lookback + 1:
        return False
    for i in range(len(closes) - lookback, len(closes)):
        if closes[i] >= closes[i - 1]:
            return False
    return True


def _in_uptrend(closes: list[float], lookback: int = 3) -> bool:
    """Check for 3+ consecutive higher closes."""
    if len(closes) < lookback + 1:
        return False
    for i in range(len(closes) - lookback, len(closes)):
        if closes[i] <= closes[i - 1]:
            return False
    return True


def _small_body(o: float, h: float, lo: float, c: float) -> bool:
    """Body is small relative to day range."""
    dr = _day_range(h, lo)
    if dr == 0:
        return True
    return _body_size(o, c) / dr < 0.3


# ---------------------------------------------------------------------------
# Pattern detection functions
# ---------------------------------------------------------------------------

def _detect_hammer(
    opens: list[float], highs: list[float],
    lows: list[float], closes: list[float],
) -> CandlePattern | None:
    """Hammer: small body, long lower shadow (>2x body), little upper shadow, in downtrend."""
    o, h, lo, c = opens[-1], highs[-1], lows[-1], closes[-1]
    body = _body_size(o, c)
    lower = _lower_shadow(o, lo, c)
    upper = _upper_shadow(o, h, c)

    if body == 0:
        body = 0.001  # avoid div-by-zero

    if lower >= 2 * body and upper <= body and _in_downtrend(closes[:-1]):
        return CandlePattern(
            name="Hammer", name_jp="カラカサ", direction=1,
            reliability=0.60,
            detail="Small body with long lower shadow after downtrend",
        )
    return None


def _detect_bullish_engulfing(
    opens: list[float], highs: list[float],
    lows: list[float], closes: list[float],
) -> CandlePattern | None:
    """Bullish Engulfing: bearish prior candle engulfed by current bullish candle."""
    if len(opens) < 2:
        return None
    o1, c1 = opens[-2], closes[-2]
    o2, c2 = opens[-1], closes[-1]

    if _is_bearish(o1, c1) and _is_bullish(o2, c2):
        if o2 <= c1 and c2 >= o1:
            return CandlePattern(
                name="Bullish Engulfing", name_jp="陽線包み足", direction=1,
                reliability=0.63,
                detail="Bullish candle body engulfs prior bearish body",
            )
    return None


def _detect_morning_star(
    opens: list[float], highs: list[float],
    lows: list[float], closes: list[float],
) -> CandlePattern | None:
    """Morning Star: bearish, small body (star), bullish."""
    if len(opens) < 3:
        return None
    o1, c1 = opens[-3], closes[-3]
    o2, h2, l2, c2 = opens[-2], highs[-2], lows[-2], closes[-2]
    o3, c3 = opens[-1], closes[-1]

    if (
        _is_bearish(o1, c1)
        and _small_body(o2, h2, l2, c2)
        and max(o2, c2) < c1  # star gaps down from first body
        and _is_bullish(o3, c3)
        and c3 > (o1 + c1) / 2  # third closes above midpoint of first
    ):
        return CandlePattern(
            name="Morning Star", name_jp="明けの明星", direction=1,
            reliability=0.78,
            detail="3-candle bullish reversal: bearish, star, bullish",
        )
    return None


def _detect_three_white_soldiers(
    opens: list[float], highs: list[float],
    lows: list[float], closes: list[float],
) -> CandlePattern | None:
    """Three White Soldiers: 3 consecutive bullish candles, each closing higher."""
    if len(opens) < 3:
        return None
    for i in range(-3, 0):
        o, c = opens[i], closes[i]
        if not _is_bullish(o, c):
            return None
    # Each closes higher than prior
    if closes[-2] <= closes[-3] or closes[-1] <= closes[-2]:
        return None
    # Each opens within prior body
    if not (min(opens[-3], closes[-3]) <= opens[-2] <= max(opens[-3], closes[-3])):
        return None
    if not (min(opens[-2], closes[-2]) <= opens[-1] <= max(opens[-2], closes[-2])):
        return None

    return CandlePattern(
        name="Three White Soldiers", name_jp="赤三兵", direction=1,
        reliability=0.82,
        detail="3 consecutive bullish candles closing progressively higher",
    )


def _detect_piercing_line(
    opens: list[float], highs: list[float],
    lows: list[float], closes: list[float],
) -> CandlePattern | None:
    """Piercing Line: bearish then bullish opening below prior low, closing above midpoint."""
    if len(opens) < 2:
        return None
    o1, c1, l1 = opens[-2], closes[-2], lows[-2]
    o2, c2 = opens[-1], closes[-1]

    midpoint = (o1 + c1) / 2
    if (
        _is_bearish(o1, c1)
        and _is_bullish(o2, c2)
        and o2 < l1
        and c2 > midpoint
        and c2 < o1  # doesn't fully engulf
    ):
        return CandlePattern(
            name="Piercing Line", name_jp="切り込み線", direction=1,
            reliability=0.64,
            detail="Bullish candle opens below prior low, closes above prior midpoint",
        )
    return None


def _detect_shooting_star(
    opens: list[float], highs: list[float],
    lows: list[float], closes: list[float],
) -> CandlePattern | None:
    """Shooting Star: small body, long upper shadow, little lower shadow, in uptrend."""
    o, h, lo, c = opens[-1], highs[-1], lows[-1], closes[-1]
    body = _body_size(o, c)
    upper = _upper_shadow(o, h, c)
    lower = _lower_shadow(o, lo, c)

    if body == 0:
        body = 0.001

    if upper >= 2 * body and lower <= body and _in_uptrend(closes[:-1]):
        return CandlePattern(
            name="Shooting Star", name_jp="流れ星", direction=-1,
            reliability=0.59,
            detail="Small body with long upper shadow after uptrend",
        )
    return None


def _detect_bearish_engulfing(
    opens: list[float], highs: list[float],
    lows: list[float], closes: list[float],
) -> CandlePattern | None:
    """Bearish Engulfing: bullish prior candle engulfed by current bearish candle."""
    if len(opens) < 2:
        return None
    o1, c1 = opens[-2], closes[-2]
    o2, c2 = opens[-1], closes[-1]

    if _is_bullish(o1, c1) and _is_bearish(o2, c2):
        if o2 >= c1 and c2 <= o1:
            return CandlePattern(
                name="Bearish Engulfing", name_jp="陰線包み足", direction=-1,
                reliability=0.79,
                detail="Bearish candle body engulfs prior bullish body",
            )
    return None


def _detect_evening_star(
    opens: list[float], highs: list[float],
    lows: list[float], closes: list[float],
) -> CandlePattern | None:
    """Evening Star: bullish, small body, bearish."""
    if len(opens) < 3:
        return None
    o1, c1 = opens[-3], closes[-3]
    o2, h2, l2, c2 = opens[-2], highs[-2], lows[-2], closes[-2]
    o3, c3 = opens[-1], closes[-1]

    if (
        _is_bullish(o1, c1)
        and _small_body(o2, h2, l2, c2)
        and min(o2, c2) > c1  # star gaps up from first body
        and _is_bearish(o3, c3)
        and c3 < (o1 + c1) / 2  # third closes below midpoint of first
    ):
        return CandlePattern(
            name="Evening Star", name_jp="宵の明星", direction=-1,
            reliability=0.72,
            detail="3-candle bearish reversal: bullish, star, bearish",
        )
    return None


def _detect_three_black_crows(
    opens: list[float], highs: list[float],
    lows: list[float], closes: list[float],
) -> CandlePattern | None:
    """Three Black Crows: 3 consecutive bearish candles, each closing lower."""
    if len(opens) < 3:
        return None
    for i in range(-3, 0):
        if not _is_bearish(opens[i], closes[i]):
            return None
    if closes[-2] >= closes[-3] or closes[-1] >= closes[-2]:
        return None

    return CandlePattern(
        name="Three Black Crows", name_jp="黒三兵", direction=-1,
        reliability=0.78,
        detail="3 consecutive bearish candles closing progressively lower",
    )


def _detect_dark_cloud_cover(
    opens: list[float], highs: list[float],
    lows: list[float], closes: list[float],
) -> CandlePattern | None:
    """Dark Cloud Cover: bullish, then bearish opens above prior high, closes below midpoint."""
    if len(opens) < 2:
        return None
    o1, h1, c1 = opens[-2], highs[-2], closes[-2]
    o2, c2 = opens[-1], closes[-1]

    midpoint = (o1 + c1) / 2
    if (
        _is_bullish(o1, c1)
        and _is_bearish(o2, c2)
        and o2 > h1
        and c2 < midpoint
        and c2 > o1  # doesn't fully engulf
    ):
        return CandlePattern(
            name="Dark Cloud Cover", name_jp="かぶせ線", direction=-1,
            reliability=0.60,
            detail="Bearish candle opens above prior high, closes below prior midpoint",
        )
    return None


def _detect_doji(
    opens: list[float], highs: list[float],
    lows: list[float], closes: list[float],
) -> CandlePattern | None:
    """Doji: open ≈ close (body < 5% of day range)."""
    o, h, lo, c = opens[-1], highs[-1], lows[-1], closes[-1]
    if _is_doji(o, h, lo, c):
        # Direction depends on trend context
        if _in_uptrend(closes[:-1]):
            direction = -1
        elif _in_downtrend(closes[:-1]):
            direction = 1
        else:
            direction = 0
        return CandlePattern(
            name="Doji", name_jp="十字線", direction=direction,
            reliability=0.50,
            detail="Open ≈ Close indicating indecision",
        )
    return None


def _detect_spinning_top(
    opens: list[float], highs: list[float],
    lows: list[float], closes: list[float],
) -> CandlePattern | None:
    """Spinning Top: small body with shadows on both sides."""
    o, h, lo, c = opens[-1], highs[-1], lows[-1], closes[-1]
    dr = _day_range(h, lo)
    if dr == 0:
        return None
    body = _body_size(o, c)
    upper = _upper_shadow(o, h, c)
    lower = _lower_shadow(o, lo, c)

    # Small body, not a doji, shadows on both sides
    if (
        not _is_doji(o, h, lo, c)
        and body / dr < 0.3
        and upper > body * 0.5
        and lower > body * 0.5
    ):
        return CandlePattern(
            name="Spinning Top", name_jp="コマ", direction=0,
            reliability=0.45,
            detail="Small body with shadows on both sides indicating indecision",
        )
    return None


def _detect_abandoned_baby(
    opens: list[float], highs: list[float],
    lows: list[float], closes: list[float],
) -> CandlePattern | None:
    """Abandoned Baby: like morning/evening star but star gaps completely."""
    if len(opens) < 3:
        return None
    o1, h1, l1, c1 = opens[-3], highs[-3], lows[-3], closes[-3]
    o2, h2, l2, c2 = opens[-2], highs[-2], lows[-2], closes[-2]
    o3, h3, l3, c3 = opens[-1], highs[-1], lows[-1], closes[-1]

    is_star = _is_doji(o2, h2, l2, c2) or _small_body(o2, h2, l2, c2)

    # Bullish abandoned baby
    if (
        _is_bearish(o1, c1)
        and is_star
        and h2 < l1  # complete gap down
        and _is_bullish(o3, c3)
        and l3 > h2  # complete gap up
    ):
        return CandlePattern(
            name="Abandoned Baby", name_jp="捨て子線", direction=1,
            reliability=0.70,
            detail="Bullish abandoned baby: star gaps completely from both candles",
        )

    # Bearish abandoned baby
    if (
        _is_bullish(o1, c1)
        and is_star
        and l2 > h1  # complete gap up
        and _is_bearish(o3, c3)
        and h3 < l2  # complete gap down
    ):
        return CandlePattern(
            name="Abandoned Baby", name_jp="捨て子線", direction=-1,
            reliability=0.70,
            detail="Bearish abandoned baby: star gaps completely from both candles",
        )
    return None


def _detect_three_inside_up(
    opens: list[float], highs: list[float],
    lows: list[float], closes: list[float],
) -> CandlePattern | None:
    """Three Inside Up: bearish, bullish harami, bullish continuation."""
    if len(opens) < 3:
        return None
    o1, c1 = opens[-3], closes[-3]
    o2, c2 = opens[-2], closes[-2]
    o3, c3 = opens[-1], closes[-1]

    if (
        _is_bearish(o1, c1)
        and _is_bullish(o2, c2)
        and o2 >= c1 and c2 <= o1  # harami: second inside first
        and _is_bullish(o3, c3)
        and c3 > o1  # closes above first candle's open
    ):
        return CandlePattern(
            name="Three Inside Up", name_jp="はらみ足上昇", direction=1,
            reliability=0.65,
            detail="Bearish candle, bullish harami, bullish continuation",
        )
    return None


def _detect_three_inside_down(
    opens: list[float], highs: list[float],
    lows: list[float], closes: list[float],
) -> CandlePattern | None:
    """Three Inside Down: bullish, bearish harami, bearish continuation."""
    if len(opens) < 3:
        return None
    o1, c1 = opens[-3], closes[-3]
    o2, c2 = opens[-2], closes[-2]
    o3, c3 = opens[-1], closes[-1]

    if (
        _is_bullish(o1, c1)
        and _is_bearish(o2, c2)
        and c2 >= o1 and o2 <= c1  # harami: second inside first
        and _is_bearish(o3, c3)
        and c3 < o1  # closes below first candle's open
    ):
        return CandlePattern(
            name="Three Inside Down", name_jp="はらみ足下降", direction=-1,
            reliability=0.65,
            detail="Bullish candle, bearish harami, bearish continuation",
        )
    return None


# ---------------------------------------------------------------------------
# Main analysis function
# ---------------------------------------------------------------------------

_ALL_DETECTORS = [
    _detect_hammer,
    _detect_bullish_engulfing,
    _detect_morning_star,
    _detect_three_white_soldiers,
    _detect_piercing_line,
    _detect_shooting_star,
    _detect_bearish_engulfing,
    _detect_evening_star,
    _detect_three_black_crows,
    _detect_dark_cloud_cover,
    _detect_doji,
    _detect_spinning_top,
    _detect_abandoned_baby,
    _detect_three_inside_up,
    _detect_three_inside_down,
]


def analyze_candlesticks(
    opens: list[float],
    highs: list[float],
    lows: list[float],
    closes: list[float],
    volumes: list[float] | None = None,
) -> CandlestickAnalysis:
    """Analyze OHLCV data for candlestick patterns.

    Requires at least 5 candles. Checks the last 3 candles with prior
    candles as context for trend detection.

    Parameters
    ----------
    opens, highs, lows, closes : list[float]
        OHLCV price data (same length).
    volumes : list[float] | None
        Optional volume data (reserved for future use).

    Returns
    -------
    CandlestickAnalysis
        Detected patterns with consensus direction and strength.
    """
    n = len(opens)
    if n < 5:
        logger.warning("Need at least 5 candles, got %d", n)
        return CandlestickAnalysis(
            detail=f"Insufficient data: {n} candles (need >=5)",
        )

    patterns: list[CandlePattern] = []

    for detector in _ALL_DETECTORS:
        try:
            result = detector(opens, highs, lows, closes)
            if result is not None:
                patterns.append(result)
                logger.debug("Detected: %s (%s)", result.name, result.name_jp)
        except Exception:
            logger.exception("Error in detector %s", detector.__name__)

    # Calculate consensus
    weighted_sum = sum(p.direction * p.reliability for p in patterns)
    total_possible = sum(p.reliability for p in patterns) if patterns else 1.0

    if weighted_sum > 0.1:
        signal_direction = 1
    elif weighted_sum < -0.1:
        signal_direction = -1
    else:
        signal_direction = 0

    signal_strength = min(abs(weighted_sum) / total_possible, 1.0) if total_possible > 0 else 0.0

    pattern_names = [p.name for p in patterns]
    detail = (
        f"Detected {len(patterns)} pattern(s): {pattern_names}; "
        f"weighted_sum={weighted_sum:+.3f}, strength={signal_strength:.3f}"
    )
    logger.info(detail)

    return CandlestickAnalysis(
        patterns=patterns,
        signal_direction=signal_direction,
        signal_strength=signal_strength,
        detail=detail,
    )
