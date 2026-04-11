"""Chart-based exit scoring for swing trades."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ExitScore:
    total: float
    bearish_pattern: float
    momentum_decay: float
    trailing_hit: bool
    stage_breakdown: bool
    recommendation: str


def compute_exit_score(
    opens: list[float], highs: list[float], lows: list[float],
    closes: list[float], volumes: list[float],
    entry_price: float, current_high: float, hold_days: int,
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
                dist = (current_price - trail_level) / current_price * 100
                trail_score = max(0, 50 - dist * 20)
    stage_breakdown = False
    stage_score = 0.0
    if len(closes) >= 20:
        sma20 = sum(closes[-20:]) / 20
        sma50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else sma20
        if current_price < sma50:
            stage_breakdown = True
            stage_score = 80.0
        elif current_price < sma20:
            stage_score = 40.0
        elif len(closes) >= 50 and sma20 < sma50:
            stage_score = 60.0
            stage_breakdown = True
    total = pattern_score * w_pattern + momentum_score * w_momentum + trail_score * w_trail + stage_score * w_stage
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
    return ExitScore(round(total, 1), round(pattern_score, 1), round(momentum_score, 1), trail_hit, stage_breakdown, rec)


def _score_bearish_patterns(opens, highs, lows, closes):
    if len(closes) < 3:
        return 0.0
    score = 0.0
    n = min(len(closes), 5)
    for i in range(-n + 1, 0):
        o, h, low, c = opens[i], highs[i], lows[i], closes[i]
        prev_o, prev_c = opens[i-1], closes[i-1]
        body, prev_body = c - o, prev_c - prev_o
        if prev_body > 0 and body < 0 and c < prev_o and o > prev_c:
            score += 35
        if h > 0 and (h - low) > 0:
            us = h - max(o, c)
            ls = min(o, c) - low
            rb = abs(body)
            if us > 2 * rb and ls < rb * 0.3:
                score += 25
        if prev_body > 0 and body < 0 and o > prev_c and c < (prev_o + prev_c) / 2:
            score += 30
    if n >= 3 and all(closes[i] < opens[i] for i in range(-3, 0)):
        score += 20
    return min(score, 100.0)


def _score_momentum_decay(closes, volumes):
    if len(closes) < 10:
        return 0.0
    score = 0.0
    current = closes[-1]
    ma5 = sum(closes[-5:]) / 5
    if current < ma5:
        score += min((ma5 - current) / ma5 * 100 * 15, 40)
    if len(closes) >= 10:
        ma10 = sum(closes[-10:]) / 10
        if current < ma10:
            score += min((ma10 - current) / ma10 * 100 * 10, 30)
    if len(volumes) >= 10:
        rv = sum(volumes[-3:]) / 3
        pv = sum(volumes[-10:-3]) / 7 if sum(volumes[-10:-3]) > 0 else 1
        if pv > 0 and rv / pv < 0.5:
            score += min((1 - rv / pv) * 40, 30)
    if len(closes) >= 5 and closes[-1] < max(closes[-5:-1]):
        score += 10
    rsi = _compute_rsi_simple(closes)
    if rsi is not None and rsi > 70:
        score += min((rsi - 70) * 2, 20)
    return min(score, 100.0)


def _compute_atr(highs, lows, closes, period=14):
    n = min(period, len(closes) - 1)
    if n <= 0:
        return 0.0
    return sum(max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1])) for i in range(-n, 0)) / n


def _compute_rsi_simple(closes, period=14):
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(-period, 0):
        ch = closes[i] - closes[i-1]
        gains.append(max(ch, 0))
        losses.append(max(-ch, 0))
    ag, al = sum(gains) / period, sum(losses) / period
    if al == 0:
        return 100.0
    return 100.0 - (100.0 / (1.0 + ag / al))
