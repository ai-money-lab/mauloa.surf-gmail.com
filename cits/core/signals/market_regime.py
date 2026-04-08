"""Market Regime Detector — BNF-inspired regime switching.

BNF's core insight: adapt strategy to market conditions.
- Uptrend:   trend-following (buy dips, ride momentum)
- Downtrend: mean-reversion (buy oversold bounces)
- Range:     mean-reversion (buy support, sell resistance)
- Volatile:  stay out (SQ week, crash, black swan)

Uses moving averages, ATR, and slope to classify the current regime
and recommend an appropriate strategy.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MarketRegime:
    """Current market regime classification."""

    regime: str          # "uptrend" / "downtrend" / "range" / "volatile"
    strategy: str        # "trend_follow" / "mean_reversion" / "stay_out"
    strength: float      # 0.0-1.0, how clear the regime is
    ma20: float
    ma50: float
    atr_pct: float       # average true range as % of price
    detail: str


def _simple_ma(values: list[float], period: int) -> float:
    """Return simple moving average of the last *period* values."""
    segment = values[-period:]
    return sum(segment) / len(segment)


def _atr(
    closes: list[float],
    highs: list[float],
    lows: list[float],
    period: int = 14,
) -> float:
    """Return Average True Range over *period* bars."""
    n = min(period, len(closes) - 1)
    if n <= 0:
        return 0.0
    tr_values: list[float] = []
    for i in range(-n, 0):
        high = highs[i]
        low = lows[i]
        prev_close = closes[i - 1]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_values.append(tr)
    return sum(tr_values) / len(tr_values)


def _slope(values: list[float], period: int = 10) -> float:
    """Return normalised slope (least-squares) over last *period* values.

    Result is daily change as a fraction of the mean price.
    """
    segment = values[-period:]
    n = len(segment)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2.0
    y_mean = sum(segment) / n
    if y_mean == 0:
        return 0.0
    numer = 0.0
    denom = 0.0
    for i, y in enumerate(segment):
        dx = i - x_mean
        numer += dx * (y - y_mean)
        denom += dx * dx
    if denom == 0:
        return 0.0
    raw_slope = numer / denom  # price change per day
    return raw_slope / y_mean  # normalise by mean price


def detect_regime(
    closes: list[float],
    highs: list[float],
    lows: list[float],
    lookback_short: int = 20,
    lookback_long: int = 50,
) -> MarketRegime:
    """Detect the current market regime from price data.

    Args:
        closes: List of closing prices (oldest first).
        highs: List of high prices.
        lows: List of low prices.
        lookback_short: Short MA period (default 20).
        lookback_long: Long MA period (default 50).

    Returns:
        MarketRegime with regime classification and recommended strategy.

    Raises:
        ValueError: If not enough data for the long lookback.
    """
    min_required = lookback_long + 1
    if len(closes) < min_required:
        msg = f"Need at least {min_required} bars, got {len(closes)}"
        raise ValueError(msg)

    price = closes[-1]
    ma_short = _simple_ma(closes, lookback_short)
    ma_long = _simple_ma(closes, lookback_long)
    atr_val = _atr(closes, highs, lows, period=14)
    atr_pct = (atr_val / price) * 100.0 if price else 0.0
    trend_slope = _slope(closes, period=10)

    # MA separation as percentage
    ma_sep_pct = abs(ma_short - ma_long) / ma_long * 100.0 if ma_long else 0.0

    # --- Regime detection (order matters: volatile first) ---
    if atr_pct > 3.0:
        regime = "volatile"
        strategy = "stay_out"
        # Strength: how far above 3% threshold
        strength = min((atr_pct - 3.0) / 3.0, 1.0)
        detail = (
            f"ATR={atr_pct:.2f}% > 3% → 高ボラティリティ, "
            f"MA20={ma_short:.1f}, MA50={ma_long:.1f}"
        )
    elif (
        ma_short > ma_long
        and price > ma_short
        and trend_slope > 0
    ):
        regime = "uptrend"
        strategy = "trend_follow"
        # Strength: combination of MA separation and slope consistency
        sep_score = min(ma_sep_pct / 5.0, 1.0)
        slope_score = min(abs(trend_slope) * 100, 1.0)
        strength = 0.6 * sep_score + 0.4 * slope_score
        detail = (
            f"MA20({ma_short:.1f}) > MA50({ma_long:.1f}), "
            f"price={price:.1f} > MA20, slope={trend_slope:+.4f} → 上昇トレンド"
        )
    elif (
        ma_short < ma_long
        and price < ma_short
        and trend_slope < 0
    ):
        regime = "downtrend"
        strategy = "mean_reversion"
        sep_score = min(ma_sep_pct / 5.0, 1.0)
        slope_score = min(abs(trend_slope) * 100, 1.0)
        strength = 0.6 * sep_score + 0.4 * slope_score
        detail = (
            f"MA20({ma_short:.1f}) < MA50({ma_long:.1f}), "
            f"price={price:.1f} < MA20, slope={trend_slope:+.4f} → 下降トレンド"
        )
    elif ma_sep_pct < 2.0 and atr_pct < 2.0:
        regime = "range"
        strategy = "mean_reversion"
        # Strength: how tight the range is (tighter = clearer range)
        tightness = 1.0 - (ma_sep_pct / 2.0)
        low_vol = 1.0 - (atr_pct / 2.0)
        strength = 0.5 * tightness + 0.5 * low_vol
        detail = (
            f"MA20≈MA50 (差{ma_sep_pct:.2f}%), ATR={atr_pct:.2f}% → レンジ相場"
        )
    else:
        # Ambiguous — default to range with low confidence
        regime = "range"
        strategy = "mean_reversion"
        strength = 0.2
        detail = (
            f"レジーム不明確: MA20={ma_short:.1f}, MA50={ma_long:.1f}, "
            f"ATR={atr_pct:.2f}%, slope={trend_slope:+.4f}"
        )

    strength = round(max(0.0, min(1.0, strength)), 3)

    return MarketRegime(
        regime=regime,
        strategy=strategy,
        strength=strength,
        ma20=round(ma_short, 2),
        ma50=round(ma_long, 2),
        atr_pct=round(atr_pct, 4),
        detail=detail,
    )
