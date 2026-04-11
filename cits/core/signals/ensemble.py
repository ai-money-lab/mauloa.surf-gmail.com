"""Ensemble Signal — Multi-Confirmation Scoring System.

Only trade when MANY independent indicators agree.
Philosophy: high win-rate through consensus of diverse signals.

Each sub-signal votes +1 (buy), -1 (sell), or 0 (no opinion).
A trade is triggered only when enough signals confirm the same direction.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class EnsembleSignal:
    """Result of multi-confirmation ensemble analysis."""

    direction: int  # +1=buy, -1=sell, 0=no trade
    score: float  # 0.0-1.0, composite confidence
    confirmations: int  # how many signals agree on the chosen direction
    total_signals: int
    signals_detail: dict[str, int]  # each signal's vote
    detail: str


def _compute_rsi(closes: list[float], period: int = 14) -> float:
    """Compute RSI from closing prices."""
    if len(closes) < period + 1:
        return 50.0  # neutral
    gains, losses = [], []
    for i in range(-period, 0):
        change = closes[i] - closes[i - 1]
        gains.append(max(change, 0))
        losses.append(max(-change, 0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def compute_ensemble(
    closes: list[float],
    volumes: list[float],
    open_price: float,
    prev_close: float,
    vix_level: float = 20.0,
    min_confirmations: int = 5,
    min_score: float = 0.7,
) -> EnsembleSignal:
    """Compute multi-confirmation ensemble signal.

    Combines 8 independent sub-signals and requires a minimum number
    of agreements before issuing a trade direction.

    Args:
        closes: Historical closing prices (oldest first, at least 20 bars).
        volumes: Historical volumes matching closes (oldest first).
        open_price: Today's opening price.
        prev_close: Previous day's closing price.
        vix_level: Current VIX (or 日経VI) level.
        min_confirmations: Minimum agreeing signals to trigger a trade.
        min_score: Minimum score threshold (not used for direction but
                   stored for downstream filtering).

    Returns:
        EnsembleSignal with direction, score, and per-signal detail.
    """
    votes: dict[str, int] = {}

    # --- (a) Mean Reversion (Bollinger z-score) ---
    if len(closes) >= 20:
        window = closes[-20:]
        sma20 = sum(window) / 20
        std_dev = (sum((x - sma20) ** 2 for x in window) / 20) ** 0.5
        if std_dev > 0:
            z_score = (closes[-1] - sma20) / std_dev
            if z_score <= -2.0:
                votes["mean_reversion"] = 1
            elif z_score >= 2.0:
                votes["mean_reversion"] = -1
            else:
                votes["mean_reversion"] = 0
        else:
            votes["mean_reversion"] = 0
    else:
        votes["mean_reversion"] = 0

    # --- (b) RSI ---
    rsi = _compute_rsi(closes)
    if rsi < 30:
        votes["rsi"] = 1
    elif rsi > 70:
        votes["rsi"] = -1
    else:
        votes["rsi"] = 0

    # --- (c) Price vs SMA20 (oversold/overbought band) ---
    if len(closes) >= 20:
        sma20 = sum(closes[-20:]) / 20
        price = closes[-1]
        if price < sma20 * 0.97:
            votes["price_vs_sma20"] = 1
        elif price > sma20 * 1.03:
            votes["price_vs_sma20"] = -1
        else:
            votes["price_vs_sma20"] = 0
    else:
        votes["price_vs_sma20"] = 0

    # --- (d) Price vs SMA5 (short-term momentum shift) ---
    if len(closes) >= 5:
        sma5 = sum(closes[-5:]) / 5
        price = closes[-1]
        if price < sma5:
            votes["price_vs_sma5"] = 1
        elif price > sma5:
            votes["price_vs_sma5"] = -1
        else:
            votes["price_vs_sma5"] = 0
    else:
        votes["price_vs_sma5"] = 0

    # --- (e) Volume Spike ---
    if len(volumes) >= 20 and len(closes) >= 2:
        avg_vol = sum(volumes[-20:]) / 20
        current_vol = volumes[-1]
        price_change = closes[-1] - closes[-2]
        if avg_vol > 0 and current_vol > 1.5 * avg_vol:
            if price_change < 0:
                votes["volume_spike"] = 1  # capitulation buy
            elif price_change > 0:
                votes["volume_spike"] = -1  # euphoria sell
            else:
                votes["volume_spike"] = 0
        else:
            votes["volume_spike"] = 0
    else:
        votes["volume_spike"] = 0

    # --- (f) Consecutive Down Days ---
    if len(closes) >= 4:
        down_count = 0
        for i in range(-1, -4, -1):
            if closes[i] < closes[i - 1]:
                down_count += 1
            else:
                break
        if down_count >= 3:
            votes["consecutive_down"] = 1
        else:
            # Check consecutive up days for sell
            up_count = 0
            for i in range(-1, -4, -1):
                if closes[i] > closes[i - 1]:
                    up_count += 1
                else:
                    break
            if up_count >= 3:
                votes["consecutive_down"] = -1
            else:
                votes["consecutive_down"] = 0
    else:
        votes["consecutive_down"] = 0

    # --- (g) Price Range Position (20-day range) ---
    if len(closes) >= 20:
        high_20 = max(closes[-20:])
        low_20 = min(closes[-20:])
        range_20 = high_20 - low_20
        if range_20 > 0:
            position = (closes[-1] - low_20) / range_20
            if position <= 0.2:
                votes["range_position"] = 1
            elif position >= 0.8:
                votes["range_position"] = -1
            else:
                votes["range_position"] = 0
        else:
            votes["range_position"] = 0
    else:
        votes["range_position"] = 0

    # --- (h) Momentum Reversal (3-day return) ---
    if len(closes) >= 4:
        ret_3d = (closes[-1] - closes[-4]) / closes[-4] * 100
        if ret_3d < -3.0:
            votes["momentum_reversal"] = 1
        elif ret_3d > 3.0:
            votes["momentum_reversal"] = -1
        else:
            votes["momentum_reversal"] = 0
    else:
        votes["momentum_reversal"] = 0

    # --- Aggregate ---
    total_signals = len(votes)
    buy_votes = sum(1 for v in votes.values() if v == 1)
    sell_votes = sum(1 for v in votes.values() if v == -1)

    if buy_votes >= min_confirmations:
        direction = 1
        confirmations = buy_votes
        score = buy_votes / total_signals
    elif sell_votes >= min_confirmations:
        direction = -1
        confirmations = sell_votes
        score = sell_votes / total_signals
    else:
        direction = 0
        confirmations = max(buy_votes, sell_votes)
        score = confirmations / total_signals if total_signals > 0 else 0.0

    direction_label = {1: "BUY", -1: "SELL", 0: "NO_TRADE"}[direction]
    detail = (
        f"{direction_label}: {confirmations}/{total_signals} confirmations "
        f"(buy={buy_votes} sell={sell_votes}) score={score:.2f} "
        f"| votes={votes}"
    )

    logger.info(
        "Ensemble: dir=%+d score=%.2f confirms=%d/%d buy=%d sell=%d",
        direction,
        score,
        confirmations,
        total_signals,
        buy_votes,
        sell_votes,
    )

    return EnsembleSignal(
        direction=direction,
        score=round(score, 4),
        confirmations=confirmations,
        total_signals=total_signals,
        signals_detail=votes,
        detail=detail,
    )
