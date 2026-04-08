"""Chart-based exit scoring for swing trades.

Evaluates whether a position should be closed based on chart analysis,
not just fixed days or stop/target levels.

Exit Score (0-100):
  0-30  = hold
  30-50 = watch closely
  50-70 = consider exit
  70+   = exit recommended

Components:
  1. Bearish candlestick patterns (evening star, bearish engulfing, etc.)
  2. Momentum decay (MA breakdown, volume drop, RSI divergence)
  3. Trailing stop (ATR-adaptive, profit-tier based)
  4. Stage analysis (Minervini: exit when stock leaves Stage 2)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ExitScore:
    """Result of chart-based exit evaluation."""
    total: float          # 0-100 weighted score
    bearish_pattern: float
    momentum_decay: float
    trailing_hit: bool
    stage_breakdown: bool
    recommendation: str   # "HOLD" / "WATCH" / "EXIT" / "EXIT_NOW"


def compute_exit_score(
    opens: list[float],
    highs: list[float],
    lows: list[float],
    closes: list[float],
    volumes: list[float],
    entry_price: float,
    current_high: float,
    hold_days: int,
    strategy: str = "CIS",
) -> ExitScore:
    if len(closes) < 5:
        return ExitScore(0, 0, 0, False, False, "HOLD")

    current_price = closes[-1]
    profit_pct = (current_price - entry_price) / entry_price * 100

    if strategy == "KEI":
        w_pattern, w_momentum, w_trail, w_stage = 0.25, 0.20, 0.25, 0.30
    else:
        w_pattern, w_momentum, w_trail, w_stage = 0.15, 0.30, 0.30, 0.25

    pattern_score = _score_bearish_patterns(opens, highs, lows, closes)
    momentum_score = _score_momentum_decay(closes, volumes)

    trail_hit = False
    trail_score = 0.0
    if len(highs) >= 15 and len(lows) >= 15:
        atr = _compute_atr(highs, lows, closes, 14)
        if atr > 0 and current_high > 0:
            if profit_pct >= 10:
                trail_pct = 3.0
            elif profit_pct >= 5:
                trail_pct = 2.0
            elif profit_pct >= 3:
                trail_pct = 0.0
            else:
                trail_pct = (2.0 * atr / current_high) * 100

            trail_level = current_high * (1 - trail_pct / 100)
            if current_price <= trail_level:
                trail_hit = True
                trail_score = 100.0
            else:
                dist_to_trail = (current_price - trail_level) / current_price * 100
                trail_score = max(0, 50 - dist_to_trail * 20)

    stage_breakdown = False
    stage_score = 0.0
    min_ma_period = 20
    if len(closes) >= min_ma_period:
        sma20 = sum(closes[-20:]) / 20
        if len(closes) >= 50:
            sma50 = sum(closes[-50:]) / 50
        else:
            sma50 = sma20

        if current_price < sma50:
            stage_breakdown = True
            stage_score = 80.0
        elif current_price < sma20:
            stage_score = 40.0
        elif len(closes) >= 50 and sma20 < sma50:
            stage_score = 60.0
            stage_breakdown = True

    total = (
        pattern_score * w_pattern
        + momentum_score * w_momentum
        + trail_score * w_trail
        + stage_score * w_stage
    )

    if trail_hit:
        total = max(total, 75.0)
    if stage_breakdown:
        total = max(total, 60.0)

    if total >= 70 or trail_hit:
        rec = "EXIT_NOW"
    elif total >= 50:
        rec = "EXIT"
    elif total >= 30:
        rec = "WATCH"
    else:
        rec = "HOLD"

    return ExitScore(
        total=round(total, 1),
        bearish_pattern=round(pattern_score, 1),
        momentum_decay=round(momentum_score, 1),
        trailing_hit=trail_hit,
        stage_breakdown=stage_breakdown,
        recommendation=rec,
    )


def _score_bearish_patterns(
    opens: list[float], highs: list[float],
    lows: list[float], closes: list[float],
) -> float:
    if len(closes) < 3:
        return 0.0
    score = 0.0
    n = min(len(closes), 5)
    for i in range(-n + 1, 0):
        o, h, low, c = opens[i], highs[i], lows[i], closes[i]
        prev_o, prev_c = opens[i - 1], closes[i - 1]
        body = c - o
        prev_body = prev_c - prev_o
        if prev_body > 0 and body < 0:
            if c < prev_o and o > prev_c:
                score += 35
        if h > 0 and (h - low) > 0:
            upper_shadow = h - max(o, c)
            lower_shadow = min(o, c) - low
            real_body = abs(body)
            if upper_shadow > 2 * real_body and lower_shadow < real_body * 0.3:
                score += 25
        if prev_body > 0 and body < 0 and o > prev_c:
            mid_prev = (prev_o + prev_c) / 2
            if c < mid_prev:
                score += 30
    if n >= 3 and all(closes[i] < opens[i] for i in range(-3, 0)):
        score += 20
    return min(score, 100.0)


def _score_momentum_decay(closes: list[float], volumes: list[float]) -> float:
    if len(closes) < 10:
        return 0.0
    score = 0.0
    current = closes[-1]
    ma5 = sum(closes[-5:]) / 5
    if current < ma5:
        pct_below = (ma5 - current) / ma5 * 100
        score += min(pct_below * 15, 40)
    if len(closes) >= 10:
        ma10 = sum(closes[-10:]) / 10
        if current < ma10:
            pct_below = (ma10 - current) / ma10 * 100
            score += min(pct_below * 10, 30)
    if len(volumes) >= 10:
        recent_vol = sum(volumes[-3:]) / 3
        prior_vol = sum(volumes[-10:-3]) / 7 if sum(volumes[-10:-3]) > 0 else 1
        if prior_vol > 0:
            vol_ratio = recent_vol / prior_vol
            if vol_ratio < 0.5:
                score += min((1 - vol_ratio) * 40, 30)
    if len(closes) >= 5:
        recent_highs = closes[-5:]
        if recent_highs[-1] < max(recent_highs[:-1]):
            score += 10
    rsi = _compute_rsi_simple(closes)
    if rsi is not None and rsi > 70:
        score += min((rsi - 70) * 2, 20)
    return min(score, 100.0)


def _compute_atr(
    highs: list[float], lows: list[float],
    closes: list[float], period: int = 14,
) -> float:
    n = min(period, len(closes) - 1)
    if n <= 0:
        return 0.0
    tr_values: list[float] = []
    for i in range(-n, 0):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        tr_values.append(tr)
    return sum(tr_values) / len(tr_values)


def _compute_rsi_simple(closes: list[float], period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    gains = []
    losses = []
    for i in range(-period, 0):
        change = closes[i] - closes[i - 1]
        if change > 0:
            gains.append(change)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(abs(change))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))
