"""CITS Position Monitor v2 -- Intelligent Exit Strategy.

Runs every 30 minutes via Task Scheduler during market hours.
Evaluates ALL open positions with a multi-factor exit scoring system.

Exit Score (0-100):
  0  = hold confidently
  50 = watch closely
  70+= exit recommended
  90+= exit immediately

Score Components:
  1. Chart Pattern Score   -- bearish reversal candlestick patterns
  2. Momentum Score        -- MA position, volume trend, RSI
  3. Market Regime Score   -- Nikkei drop, VIX spike, S&P overnight
  4. Trailing Stop Score   -- ATR-based adaptive trailing stop
  5. Time Score            -- approaching max hold period

Strategy-specific weights:
  CIS (short-term, 1-5 days):  heavier on momentum + trailing stop
  KEI (medium-term, 1-30 days): heavier on chart patterns + trend

Usage:
    python -m cits.scripts.position_monitor --dry-run
    python -m cits.scripts.position_monitor
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import yfinance as yf

# .env auto-load (handle Japanese Windows cp932 encoding)
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        try:
            load_dotenv(env_path, override=True)
        except UnicodeDecodeError:
            load_dotenv(env_path, override=True, encoding="cp932")
except ImportError:
    pass

LOG_DIR = Path(__file__).resolve().parent.parent / "logs" / "position_monitor"
LOG_DIR.mkdir(parents=True, exist_ok=True)
POSITION_DB = Path(__file__).resolve().parent.parent / "data" / "positions.json"

# Configure logging
_log_handler_file = logging.FileHandler(
    LOG_DIR / "monitor.log", encoding="utf-8"
)
_log_handler_stdout = logging.StreamHandler(sys.stdout)
_log_fmt = logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s")
_log_handler_file.setFormatter(_log_fmt)
_log_handler_stdout.setFormatter(_log_fmt)

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
if not root_logger.handlers:
    root_logger.addHandler(_log_handler_file)
    root_logger.addHandler(_log_handler_stdout)

logger = logging.getLogger("cits.position_monitor")


# ---------------------------------------------------------------------------
# Data classes for exit analysis
# ---------------------------------------------------------------------------

@dataclass
class ExitSignal:
    """A single exit signal with score contribution."""
    name: str
    score: float       # 0-100 contribution
    weight: float      # how much this matters (0-1)
    reason: str


@dataclass
class ExitAnalysis:
    """Complete exit analysis for a position."""
    ticker: str
    strategy: str
    total_score: float         # weighted 0-100
    signals: list[ExitSignal] = field(default_factory=list)
    recommendation: str = ""   # "HOLD" / "WATCH" / "EXIT" / "EXIT_NOW"
    detail: str = ""


# ---------------------------------------------------------------------------
# Strategy weight profiles
# ---------------------------------------------------------------------------

# CIS: short-term momentum. Trailing stop and momentum matter most.
CIS_WEIGHTS = {
    "chart_pattern": 0.10,
    "momentum": 0.25,
    "market_regime": 0.15,
    "trailing_stop": 0.20,
    "time": 0.10,
    "stage_analysis": 0.20,  # Minervini: exit when stock leaves Stage 2
}

# KEI: medium-term new-high riding. Chart patterns and trend matter most.
KEI_WEIGHTS = {
    "chart_pattern": 0.20,
    "momentum": 0.15,
    "market_regime": 0.10,
    "trailing_stop": 0.20,
    "time": 0.10,
    "stage_analysis": 0.25,  # Minervini: stage breakdown is critical for KEI
}

# Trailing stop tiers: as profit grows, tighten the stop
# Format: (min_profit_pct, trail_pct_from_high)
TRAILING_STOP_TIERS = [
    (10.0, 3.0),   # profit 10%+: trail at -3% from high
    (5.0, 2.0),    # profit 5-10%: trail at -2% from high
    (3.0, 0.0),    # profit 3-5%: move SL to breakeven (0% trail = entry)
    (0.0, None),    # profit 0-3%: keep original SL
]

# CIS: max 5 days, KEI: max 30 days
MAX_HOLD_DAYS = {"CIS": 5, "KEI": 30}


# ---------------------------------------------------------------------------
# Position DB operations
# ---------------------------------------------------------------------------

def load_positions() -> list[dict]:
    """Load position database from JSON."""
    if POSITION_DB.exists():
        with open(POSITION_DB, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_positions(positions: list[dict]) -> None:
    """Save position database to JSON."""
    POSITION_DB.parent.mkdir(parents=True, exist_ok=True)
    with open(POSITION_DB, "w", encoding="utf-8") as f:
        json.dump(positions, f, ensure_ascii=False, indent=2, default=str)
    logger.info("Position DB saved: %d positions", len(positions))


def register_position(ticker: str, strategy: str, entry_price: float,
                       size: int, stop_loss: float, sl_order_id: str = "",
                       exit_deadline: str = "") -> None:
    """Register a new position in the DB.

    Args:
        exit_deadline: Optional date string (YYYY-MM-DD) for forced exit.
                       Use for earnings dates, etc. Position will be closed
                       on or before this date regardless of other signals.
    """
    positions = load_positions()
    positions.append({
        "ticker": ticker,
        "strategy": strategy,
        "entry_date": str(date.today()),
        "entry_price": entry_price,
        "size": size,
        "stop_loss": stop_loss,
        "sl_order_id": sl_order_id,
        "status": "open",
        "high_since_entry": entry_price,
        "new_high_days": 0,
        "hold_days": 0,
        "exit_deadline": exit_deadline,  # forced exit date (e.g. pre-earnings)
    })
    save_positions(positions)
    logger.info("Position registered: %s %s x%d @ %.1f deadline=%s",
                strategy, ticker, size, entry_price, exit_deadline or "none")


# ---------------------------------------------------------------------------
# Chart data fetcher (yfinance -- free, no API key)
# ---------------------------------------------------------------------------

def _ensure_tse_suffix(ticker: str) -> str:
    """Append .T for TSE stocks if not already suffixed."""
    if ticker.startswith("^"):
        return ticker
    if "." not in ticker:
        return f"{ticker}.T"
    return ticker


def fetch_chart_data(ticker: str, period: str = "3mo") -> pd.DataFrame:
    """Fetch OHLCV data from yfinance. Returns empty DF on failure."""
    symbol = _ensure_tse_suffix(ticker)
    try:
        df = yf.download(symbol, period=period, progress=False)
        if df.empty:
            logger.warning("No chart data for %s", symbol)
            return pd.DataFrame()
        # Flatten MultiIndex columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception as e:
        logger.error("Chart data fetch failed for %s: %s", symbol, e)
        return pd.DataFrame()


def fetch_nikkei_data(period: str = "1mo") -> pd.DataFrame:
    """Fetch Nikkei 225 index data."""
    try:
        df = yf.download("^N225", period=period, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception as e:
        logger.error("Nikkei data fetch failed: %s", e)
        return pd.DataFrame()


def fetch_sp500_data(period: str = "5d") -> pd.DataFrame:
    """Fetch S&P 500 data for overnight risk check."""
    try:
        df = yf.download("^GSPC", period=period, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception as e:
        logger.error("S&P 500 data fetch failed: %s", e)
        return pd.DataFrame()


def fetch_vix_data(period: str = "5d") -> pd.DataFrame:
    """Fetch VIX data."""
    try:
        df = yf.download("^VIX", period=period, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception as e:
        logger.error("VIX data fetch failed: %s", e)
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# Score component calculators
# ---------------------------------------------------------------------------

def _compute_atr(highs: list[float], lows: list[float],
                 closes: list[float], period: int = 14) -> float:
    """Compute ATR (Average True Range) from price lists."""
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


def _compute_rsi(closes: list[float], period: int = 14) -> float | None:
    """Compute RSI from close prices."""
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


def _simple_ma(values: list[float], period: int) -> float | None:
    """Simple moving average of the last N values."""
    if len(values) < period:
        return None
    segment = values[-period:]
    return sum(segment) / len(segment)


def score_chart_patterns(df: pd.DataFrame) -> ExitSignal:
    """Score bearish chart patterns using the existing candlestick engine.

    Returns score 0-100 where higher = more bearish patterns detected.
    """
    if df.empty or len(df) < 10:
        return ExitSignal(
            name="chart_pattern", score=0, weight=1.0,
            reason="Insufficient data for pattern analysis",
        )

    try:
        from cits.core.signals.candlestick_patterns import analyze_candlesticks
    except ImportError:
        return ExitSignal(
            name="chart_pattern", score=0, weight=1.0,
            reason="candlestick_patterns module not available",
        )

    opens = df["Open"].tolist()
    highs = df["High"].tolist()
    lows = df["Low"].tolist()
    closes = df["Close"].tolist()

    analysis = analyze_candlesticks(opens, highs, lows, closes)

    # Extract bearish signal strength
    score = 0.0
    bearish_patterns = [p for p in analysis.patterns if p.direction == -1]

    if bearish_patterns:
        # Each bearish pattern contributes based on its reliability
        for p in bearish_patterns:
            score += p.reliability * 40  # e.g. 0.79 reliability -> 31.6 points

        # Cap individual component at 100
        score = min(score, 100.0)

    pattern_names = [p.name for p in bearish_patterns]
    reason = (
        f"Bearish patterns: {pattern_names}" if bearish_patterns
        else "No bearish reversal patterns detected"
    )

    return ExitSignal(
        name="chart_pattern", score=round(score, 1), weight=1.0,
        reason=reason,
    )


def score_momentum(df: pd.DataFrame, entry_price: float) -> ExitSignal:
    """Score momentum health: MA position, volume trend, RSI.

    Higher score = momentum dying / bearish momentum building.
    """
    if df.empty or len(df) < 20:
        return ExitSignal(
            name="momentum", score=0, weight=1.0,
            reason="Insufficient data for momentum analysis",
        )

    closes = df["Close"].tolist()
    volumes = df["Volume"].tolist()
    current_price = closes[-1]

    sub_scores: list[float] = []
    reasons: list[str] = []

    # 1. Price vs 5-day MA (short-term trend)
    ma5 = _simple_ma(closes, 5)
    if ma5 is not None:
        if current_price < ma5:
            # Below 5MA = bearish momentum
            pct_below = (ma5 - current_price) / ma5 * 100
            sub_scores.append(min(pct_below * 15, 100))  # 2% below -> 30 pts
            reasons.append(f"Below MA5 by {pct_below:.1f}%")
        else:
            sub_scores.append(0)

    # 2. Price vs 10-day MA (medium-term)
    ma10 = _simple_ma(closes, 10)
    if ma10 is not None:
        if current_price < ma10:
            pct_below = (ma10 - current_price) / ma10 * 100
            sub_scores.append(min(pct_below * 10, 100))
            reasons.append(f"Below MA10 by {pct_below:.1f}%")
        else:
            sub_scores.append(0)

    # 3. Volume drop-off (momentum exhaustion)
    if len(volumes) >= 10:
        recent_vol = sum(volumes[-3:]) / 3
        prev_vol = sum(volumes[-10:-3]) / 7
        if prev_vol > 0:
            vol_ratio = recent_vol / prev_vol
            if vol_ratio < 0.5:
                # Volume dropped more than 50% -> momentum dying
                sub_scores.append(min((1 - vol_ratio) * 80, 100))
                reasons.append(f"Volume drop-off: {vol_ratio:.2f}x recent/prior")
            else:
                sub_scores.append(0)

    # 4. Lower high formation (last 5 bars)
    if len(df) >= 5:
        highs_5 = df["High"].tolist()[-5:]
        max_first_half = max(highs_5[:3])
        max_second_half = max(highs_5[3:])
        if max_second_half < max_first_half:
            sub_scores.append(25)
            reasons.append("Lower high forming in last 5 bars")
        else:
            sub_scores.append(0)

    # 5. RSI overbought -> turning down
    rsi = _compute_rsi(closes)
    if rsi is not None:
        if rsi > 70:
            sub_scores.append(min((rsi - 70) * 3, 100))
            reasons.append(f"RSI overbought: {rsi:.1f}")
        elif rsi < 30:
            # RSI oversold is not necessarily a sell signal
            sub_scores.append(0)
        else:
            sub_scores.append(0)

    score = sum(sub_scores) / max(len(sub_scores), 1)
    reason = "; ".join(reasons) if reasons else "Momentum healthy"

    return ExitSignal(
        name="momentum", score=round(min(score, 100), 1), weight=1.0,
        reason=reason,
    )


def score_market_regime() -> ExitSignal:
    """Score overall market health: Nikkei, VIX, S&P overnight.

    Higher score = market environment hostile to holding positions.
    """
    sub_scores: list[float] = []
    reasons: list[str] = []

    # 1. Nikkei 225 daily change
    nk = fetch_nikkei_data(period="5d")
    if not nk.empty and len(nk) >= 2:
        nk_closes = nk["Close"].tolist()
        nk_change_pct = (nk_closes[-1] - nk_closes[-2]) / nk_closes[-2] * 100
        if nk_change_pct <= -2.0:
            # Nikkei dropped >2% today -> tighten all stops
            sub_scores.append(min(abs(nk_change_pct) * 20, 100))
            reasons.append(f"Nikkei225 {nk_change_pct:+.1f}% today")
        elif nk_change_pct <= -1.0:
            sub_scores.append(min(abs(nk_change_pct) * 10, 100))
            reasons.append(f"Nikkei225 weak: {nk_change_pct:+.1f}%")
        else:
            sub_scores.append(0)

    # 2. VIX level
    vix_df = fetch_vix_data(period="5d")
    if not vix_df.empty:
        vix_closes = vix_df["Close"].tolist()
        vix_current = vix_closes[-1]
        if vix_current >= 30:
            sub_scores.append(min((vix_current - 20) * 5, 100))
            reasons.append(f"VIX elevated: {vix_current:.1f}")
        elif vix_current >= 25:
            sub_scores.append(min((vix_current - 20) * 4, 100))
            reasons.append(f"VIX warning: {vix_current:.1f}")
        else:
            sub_scores.append(0)

    # 3. S&P 500 overnight drop (affects Japan open)
    sp = fetch_sp500_data(period="5d")
    if not sp.empty and len(sp) >= 2:
        sp_closes = sp["Close"].tolist()
        sp_change_pct = (sp_closes[-1] - sp_closes[-2]) / sp_closes[-2] * 100
        if sp_change_pct <= -1.5:
            sub_scores.append(min(abs(sp_change_pct) * 20, 100))
            reasons.append(f"S&P500 overnight {sp_change_pct:+.1f}%")
        elif sp_change_pct <= -1.0:
            sub_scores.append(min(abs(sp_change_pct) * 10, 100))
            reasons.append(f"S&P500 weak: {sp_change_pct:+.1f}%")
        else:
            sub_scores.append(0)

    score = sum(sub_scores) / max(len(sub_scores), 1)
    reason = "; ".join(reasons) if reasons else "Market regime normal"

    return ExitSignal(
        name="market_regime", score=round(min(score, 100), 1), weight=1.0,
        reason=reason,
    )


def score_trailing_stop(
    df: pd.DataFrame,
    entry_price: float,
    current_price: float,
    original_sl: float,
    high_since_entry: float = 0.0,
) -> ExitSignal:
    """Compute adaptive trailing stop score.

    Two methods combined:
    1. Percentage-based tiered trailing stop (locks in profits as they grow)
    2. ATR-based trailing stop (adapts to volatility)

    Higher score = price approaching or breaching trailing stop level.
    """
    if df.empty or len(df) < 15:
        return ExitSignal(
            name="trailing_stop", score=0, weight=1.0,
            reason="Insufficient data for trailing stop calculation",
        )

    highs = df["High"].tolist()
    lows = df["Low"].tolist()
    closes = df["Close"].tolist()

    # Use tracked high_since_entry from position DB (accurate to entry date)
    # Fall back to chart-based high only if not tracked
    highest_close = high_since_entry if high_since_entry > 0 else current_price

    profit_pct = (current_price - entry_price) / entry_price * 100
    drop_from_high_pct = (highest_close - current_price) / highest_close * 100

    reasons: list[str] = []

    # --- Method 1: Percentage trailing stop tiers ---
    pct_trail_level = original_sl  # default: original SL
    for min_profit, trail_pct in TRAILING_STOP_TIERS:
        if profit_pct >= min_profit:
            if trail_pct is None:
                pct_trail_level = original_sl
            elif trail_pct == 0.0:
                pct_trail_level = entry_price  # breakeven
            else:
                pct_trail_level = highest_close * (1 - trail_pct / 100)
            reasons.append(
                f"Tier trail: profit={profit_pct:.1f}%, "
                f"trail_level={pct_trail_level:.0f}"
            )
            break

    # --- Method 2: ATR-based trailing stop (2x ATR from highest close) ---
    atr = _compute_atr(highs, lows, closes, period=14)
    atr_multiplier = 2.0
    atr_trail_level = highest_close - (atr * atr_multiplier)
    reasons.append(f"ATR trail: ATR={atr:.0f}, level={atr_trail_level:.0f}")

    # Use the HIGHER of the two trailing stops (more conservative)
    effective_trail = max(pct_trail_level, atr_trail_level)
    reasons.append(f"Effective trail stop: {effective_trail:.0f}")

    # Score: how close is current price to the trailing stop?
    if current_price <= effective_trail:
        # Price has breached trailing stop -> max urgency
        score = 100.0
        reasons.append("TRAILING STOP BREACHED")
    elif effective_trail > 0:
        distance_pct = (current_price - effective_trail) / current_price * 100
        if distance_pct < 1.0:
            # Within 1% of trail stop
            score = 80.0
            reasons.append(f"Within 1% of trail stop ({distance_pct:.1f}%)")
        elif distance_pct < 2.0:
            score = 50.0
            reasons.append(f"Within 2% of trail stop ({distance_pct:.1f}%)")
        else:
            score = max(0, 30 - distance_pct * 5)
            reasons.append(f"Distance from trail: {distance_pct:.1f}%")
    else:
        score = 0
        reasons.append("Trail stop not computed")

    # Bonus: if price dropped significantly from high
    if drop_from_high_pct > 5:
        score = min(score + 20, 100)
        reasons.append(f"Dropped {drop_from_high_pct:.1f}% from high")

    return ExitSignal(
        name="trailing_stop", score=round(min(score, 100), 1), weight=1.0,
        reason="; ".join(reasons),
    )


def score_stage_analysis(df: pd.DataFrame) -> ExitSignal:
    """Minervini Stage Analysis: detect if stock is leaving Stage 2 uptrend.

    Stage 2 (Advancing) criteria -- ALL must be true:
      1. Price > 50-day SMA
      2. Price > 150-day SMA
      3. Price > 200-day SMA
      4. 150-day SMA > 200-day SMA
      5. 200-day SMA trending up (current > 1 month ago)
      6. Price within 25% of 52-week high
      7. Price at least 30% above 52-week low

    When criteria start failing -> stock entering Stage 3 (distribution)
    or Stage 4 (decline). EXIT.

    Score: number of failed criteria * weight.
    0 failed = 0 (strong Stage 2), 3+ failed = 70+ (exit).
    """
    if df.empty or len(df) < 200:
        # Not enough data for full stage analysis, use what we have
        if df.empty or len(df) < 50:
            return ExitSignal(
                name="stage_analysis", score=0, weight=1.0,
                reason="Insufficient data for stage analysis",
            )

    closes = [float(x) for x in df["Close"]]
    current_price = closes[-1]

    failures = []
    checks_done = 0

    # SMA calculations
    sma50 = _simple_ma(closes, 50)
    sma150 = _simple_ma(closes, 150) if len(closes) >= 150 else None
    sma200 = _simple_ma(closes, 200) if len(closes) >= 200 else None

    # 52-week high/low (use available data, max 252 trading days)
    lookback = min(len(closes), 252)
    high_52w = max(closes[-lookback:])
    low_52w = min(closes[-lookback:])

    # 1. Price > 50-day SMA
    if sma50 is not None:
        checks_done += 1
        if current_price < sma50:
            failures.append(f"Price {current_price:.0f} < SMA50 {sma50:.0f}")

    # 2. Price > 150-day SMA
    if sma150 is not None:
        checks_done += 1
        if current_price < sma150:
            failures.append(f"Price {current_price:.0f} < SMA150 {sma150:.0f}")

    # 3. Price > 200-day SMA
    if sma200 is not None:
        checks_done += 1
        if current_price < sma200:
            failures.append(f"Price {current_price:.0f} < SMA200 {sma200:.0f}")

    # 4. 150-day SMA > 200-day SMA
    if sma150 is not None and sma200 is not None:
        checks_done += 1
        if sma150 < sma200:
            failures.append(f"SMA150 {sma150:.0f} < SMA200 {sma200:.0f} (death cross)")

    # 5. 200-day SMA trending up (vs 20 days ago)
    if sma200 is not None and len(closes) >= 220:
        sma200_prev = _simple_ma(closes[:-20], 200)
        if sma200_prev is not None:
            checks_done += 1
            if sma200 < sma200_prev:
                failures.append(f"SMA200 declining: {sma200:.0f} < {sma200_prev:.0f}")

    # 6. Price within 25% of 52-week high
    if high_52w > 0:
        checks_done += 1
        pct_from_high = (high_52w - current_price) / high_52w * 100
        if pct_from_high > 25:
            failures.append(f"Price {pct_from_high:.0f}% below 52w high (>{25}%)")

    # 7. Price at least 30% above 52-week low
    if low_52w > 0:
        checks_done += 1
        pct_above_low = (current_price - low_52w) / low_52w * 100
        if pct_above_low < 30:
            failures.append(f"Only {pct_above_low:.0f}% above 52w low (<30%)")

    # Score: each failure = ~15 points, 5+ failures = 75+ (EXIT)
    if checks_done == 0:
        score = 0.0
        reason = "Stage analysis: no checks possible"
    else:
        fail_rate = len(failures) / checks_done
        score = min(fail_rate * 100, 100)

        if len(failures) == 0:
            reason = f"Stage 2 CONFIRMED ({checks_done}/{checks_done} criteria met)"
        elif len(failures) <= 2:
            reason = f"Stage 2 WARNING ({len(failures)} failed): " + "; ".join(failures)
        else:
            reason = f"Stage 2 BREAKDOWN ({len(failures)} failed): " + "; ".join(failures)

    return ExitSignal(
        name="stage_analysis", score=round(score, 1), weight=1.0,
        reason=reason,
    )


def score_time(hold_days: int, strategy: str, new_high_days: int = 0,
               exit_deadline: str = "") -> ExitSignal:
    """Score based on time held. Approaching max = higher urgency.

    For KEI strategy: new_high_days resets the clock (ride the winners).
    """
    max_days = MAX_HOLD_DAYS.get(strategy, 5)
    reasons: list[str] = []

    # EXIT DEADLINE: forced exit before earnings, events, etc.
    if exit_deadline:
        try:
            deadline = date.fromisoformat(exit_deadline)
            days_to_deadline = (deadline - date.today()).days
            if days_to_deadline <= 0:
                return ExitSignal(
                    name="time", score=95.0, weight=1.0,
                    reason=f"EXIT DEADLINE REACHED: {exit_deadline} (earnings/event). MUST EXIT TODAY.",
                )
            elif days_to_deadline == 1:
                return ExitSignal(
                    name="time", score=80.0, weight=1.0,
                    reason=f"EXIT DEADLINE TOMORROW: {exit_deadline}. Prepare to exit.",
                )
            elif days_to_deadline <= 3:
                reasons.append(f"Deadline in {days_to_deadline} days ({exit_deadline})")
        except ValueError:
            pass

    if strategy == "KEI" and new_high_days >= 7:
        # KEI new-high-7-day exit rule -- strong exit signal
        score = 85.0
        reasons.append(
            f"KEI new high 7 days reached: {new_high_days} consecutive new highs"
        )
    elif hold_days >= max_days:
        # Max hold reached -- this is a hard rule, score high
        score = 90.0
        reasons.append(f"MAX HOLD REACHED: {hold_days}/{max_days} days")
    elif hold_days >= max_days * 0.8:
        # 80% of max hold -> strong warning
        score = 60.0
        reasons.append(f"Approaching max hold: {hold_days}/{max_days} days")
    elif hold_days >= max_days * 0.6:
        score = 30.0
        reasons.append(f"Hold time: {hold_days}/{max_days} days")
    else:
        score = 0
        reasons.append(f"Hold time OK: {hold_days}/{max_days} days")

    return ExitSignal(
        name="time", score=round(score, 1), weight=1.0,
        reason="; ".join(reasons),
    )


# ---------------------------------------------------------------------------
# Main analysis: compute exit score for one position
# ---------------------------------------------------------------------------

def analyze_position(pos: dict, df: pd.DataFrame,
                     market_regime_signal: ExitSignal | None = None) -> ExitAnalysis:
    """Run all exit checks on a single position.

    Args:
        pos: Position dict from positions.json
        df: OHLCV DataFrame for the ticker
        market_regime_signal: Pre-computed market regime score (shared across positions)

    Returns:
        ExitAnalysis with total score and recommendation.
    """
    ticker = pos["ticker"]
    strategy = pos["strategy"]
    entry_price = pos["entry_price"]
    hold_days = pos.get("hold_days", 0)
    new_high_days = pos.get("new_high_days", 0)
    original_sl = pos.get("stop_loss", entry_price * 0.95)

    # Get current price from chart data
    if df.empty:
        return ExitAnalysis(
            ticker=ticker, strategy=strategy, total_score=0,
            recommendation="HOLD",
            detail="No chart data available -- cannot analyze",
        )

    current_price = float(df["Close"].iloc[-1])

    # Compute all signal scores
    signals: list[ExitSignal] = []

    # 1-2. Chart pattern + Momentum via shared chart_exit module
    try:
        from cits.core.chart_exit import compute_exit_score as _chart_exit
        opens = [float(x) for x in df["Open"]]
        highs_list = [float(x) for x in df["High"]]
        lows_list = [float(x) for x in df["Low"]]
        closes_list = [float(x) for x in df["Close"]]
        vols_list = [float(x) for x in df["Volume"]]
        high_since = pos.get("high_since_entry", current_price)

        exit_eval = _chart_exit(
            opens, highs_list, lows_list, closes_list, vols_list,
            entry_price=entry_price, current_high=high_since,
            hold_days=hold_days, strategy=strategy,
        )
        chart_sig = ExitSignal(
            name="chart_pattern", score=exit_eval.bearish_pattern, weight=1.0,
            reason=f"chart_exit bearish={exit_eval.bearish_pattern:.0f}",
        )
        momentum_sig = ExitSignal(
            name="momentum", score=exit_eval.momentum_decay, weight=1.0,
            reason=f"chart_exit momentum_decay={exit_eval.momentum_decay:.0f}",
        )
    except Exception:
        # Fallback to local scoring if chart_exit unavailable
        chart_sig = score_chart_patterns(df)
        momentum_sig = score_momentum(df, entry_price)

    signals.append(chart_sig)
    signals.append(momentum_sig)

    # 3. Market regime (shared, computed once for all positions)
    if market_regime_signal is not None:
        signals.append(market_regime_signal)
    else:
        regime_sig = score_market_regime()
        signals.append(regime_sig)

    # 4. Trailing stop (use chart_exit result if available, else local)
    high_since = pos.get("high_since_entry", current_price)
    try:
        if exit_eval.trailing_hit:
            trail_sig = ExitSignal(
                name="trailing_stop", score=100.0, weight=1.0,
                reason="chart_exit: TRAILING STOP BREACHED",
            )
        else:
            trail_sig = score_trailing_stop(
                df, entry_price, current_price, original_sl,
                high_since_entry=high_since,
            )
    except NameError:
        trail_sig = score_trailing_stop(
            df, entry_price, current_price, original_sl,
            high_since_entry=high_since,
        )
    signals.append(trail_sig)

    # 5. Time
    exit_deadline = pos.get("exit_deadline", "")
    time_sig = score_time(hold_days, strategy, new_high_days, exit_deadline)
    signals.append(time_sig)

    # 6. Minervini Stage Analysis (exit if stock leaves Stage 2)
    stage_sig = score_stage_analysis(df)
    signals.append(stage_sig)

    # Select weight profile
    weights = CIS_WEIGHTS if strategy == "CIS" else KEI_WEIGHTS

    # Compute weighted total
    weighted_sum = 0.0
    total_weight = 0.0
    for sig in signals:
        w = weights.get(sig.name, 0.1)
        weighted_sum += sig.score * w
        total_weight += w

    total_score = weighted_sum / total_weight if total_weight > 0 else 0

    # Hard overrides: certain conditions force minimum scores
    # 1. Trailing stop breached -> minimum 90 (EXIT_NOW)
    trail_signals = [s for s in signals if s.name == "trailing_stop"]
    if trail_signals and trail_signals[0].score >= 100:
        total_score = max(total_score, 90)

    # 2. CIS max hold reached -> minimum 70 (EXIT)
    #    CIS philosophy: never hold more than 5 days, period.
    time_signals = [s for s in signals if s.name == "time"]
    if time_signals and time_signals[0].score >= 90 and strategy == "CIS":
        total_score = max(total_score, 70)

    # 3. KEI new-high-7 -> minimum 70 (EXIT)
    if time_signals and time_signals[0].score >= 85 and strategy == "KEI":
        total_score = max(total_score, 70)

    # 4. Minervini Stage 2 breakdown (5+ criteria failed) -> minimum 80 (EXIT)
    stage_signals = [s for s in signals if s.name == "stage_analysis"]
    if stage_signals and stage_signals[0].score >= 70:
        total_score = max(total_score, 80)

    # Recommendation
    if total_score >= 90:
        recommendation = "EXIT_NOW"
    elif total_score >= 70:
        recommendation = "EXIT"
    elif total_score >= 50:
        recommendation = "WATCH"
    else:
        recommendation = "HOLD"

    pnl_pct = (current_price - entry_price) / entry_price * 100

    detail_parts = [
        f"Score={total_score:.0f} -> {recommendation}",
        f"PnL={pnl_pct:+.1f}%",
        f"Price={current_price:.0f} Entry={entry_price:.0f}",
    ]
    for sig in signals:
        detail_parts.append(f"  [{sig.name}] {sig.score:.0f}pts: {sig.reason}")

    return ExitAnalysis(
        ticker=ticker,
        strategy=strategy,
        total_score=round(total_score, 1),
        signals=signals,
        recommendation=recommendation,
        detail="\n".join(detail_parts),
    )


# ---------------------------------------------------------------------------
# Main check loop
# ---------------------------------------------------------------------------

def check_positions(dry_run: bool = True) -> list[ExitAnalysis]:
    """Check all open positions with intelligent exit scoring.

    Returns list of ExitAnalysis for reporting.
    """
    positions = load_positions()
    open_positions = [p for p in positions if p["status"] == "open"]

    if not open_positions:
        logger.info("No open positions.")
        return []

    logger.info("Checking %d open positions...", len(open_positions))
    today = date.today()

    # Pre-compute market regime once (shared across all positions)
    logger.info("Computing market regime...")
    market_regime_signal = score_market_regime()
    logger.info(
        "Market regime: score=%s, reason=%s",
        market_regime_signal.score, market_regime_signal.reason,
    )

    results: list[ExitAnalysis] = []

    for pos in open_positions:
        ticker = pos["ticker"]
        strategy = pos["strategy"]
        entry_date = date.fromisoformat(pos["entry_date"])
        entry_price = pos["entry_price"]
        hold_days = (today - entry_date).days
        pos["hold_days"] = hold_days

        logger.info("--- Analyzing %s [%s] hold=%dd ---", ticker, strategy, hold_days)

        # Fetch chart data
        df = fetch_chart_data(ticker, period="3mo")
        if df.empty:
            logger.warning("  %s: no chart data, skipping", ticker)
            continue

        current_price = float(df["Close"].iloc[-1])
        pnl_pct = (current_price - entry_price) / entry_price * 100

        # Track new highs (kei-kun)
        if current_price > pos.get("high_since_entry", entry_price):
            pos["high_since_entry"] = current_price
            pos["new_high_days"] = pos.get("new_high_days", 0) + 1

        logger.info(
            "  price=%.1f entry=%.1f pnl=%+.1f%% high_days=%d",
            current_price, entry_price, pnl_pct, pos.get("new_high_days", 0),
        )

        # Run full analysis
        analysis = analyze_position(pos, df, market_regime_signal)
        results.append(analysis)

        # Log the full analysis
        logger.info("  EXIT SCORE: %.0f -> %s", analysis.total_score, analysis.recommendation)
        for sig in analysis.signals:
            logger.info("    [%s] %5.1f pts: %s", sig.name, sig.score, sig.reason)

        # Execute exit if score >= 70
        if analysis.recommendation in ("EXIT", "EXIT_NOW"):
            exit_reason = (
                f"Exit score {analysis.total_score:.0f} "
                f"({analysis.recommendation}): "
                + "; ".join(
                    f"{s.name}={s.score:.0f}"
                    for s in analysis.signals if s.score > 0
                )
            )
            logger.info("  EXIT SIGNAL: %s -> %s", ticker, exit_reason)

            if dry_run:
                logger.info(
                    "  [DRY RUN] Would sell %s x%d @ market (%.1f)",
                    ticker, pos["size"], current_price,
                )
            else:
                _execute_exit(pos, current_price, exit_reason, today)
        elif analysis.recommendation == "WATCH":
            logger.info("  WATCH: %s -- monitoring closely", ticker)
        else:
            logger.info("  HOLD: %s -- no exit signal", ticker)

    save_positions(positions)
    return results


def _execute_exit(pos: dict, current_price: float, exit_reason: str,
                  today: date) -> None:
    """Execute a sell order via the broker API."""
    ticker = pos["ticker"]

    # Safety: only execute from Task Scheduler
    scheduled = os.environ.get("CITS_SCHEDULED_RUN", "")
    if scheduled != "TASKSCHEDULER":
        logger.error("  BLOCKED: Not running from Task Scheduler")
        return

    try:
        from cits.japan.broker.kabu_api import KabuStationAPI
        broker = KabuStationAPI()
        broker._ensure_token()

        sell_resp = broker.place_order(
            symbol=ticker, side="sell", qty=pos["size"],
            order_type="market", exchange=9,
        )
        if "error" in sell_resp:
            logger.error("  Sell failed: %s", sell_resp["error"])
        else:
            order_id = sell_resp.get("OrderId", "?")
            logger.info(
                "  SOLD: %s x%d OrderId=%s reason=%s",
                ticker, pos["size"], order_id, exit_reason,
            )
            pnl_pct = (current_price - pos["entry_price"]) / pos["entry_price"] * 100
            pos["status"] = "closed"
            pos["exit_date"] = str(today)
            pos["exit_price"] = current_price
            pos["exit_reason"] = exit_reason
            pos["pnl_pct"] = round(pnl_pct, 2)

            # Cancel SL order if exists
            if pos.get("sl_order_id"):
                try:
                    broker.cancel_order(pos["sl_order_id"])
                    logger.info("  SL order cancelled: %s", pos["sl_order_id"])
                except Exception:
                    pass
    except Exception as e:
        logger.error("  Sell execution error: %s", e)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="CITS Position Monitor v2")
    parser.add_argument("--dry-run", action="store_true",
                        help="Simulate without placing orders")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("CITS Position Monitor v2 -- Intelligent Exit Strategy")
    logger.info("  Date: %s Time: %s", date.today(), datetime.now().strftime("%H:%M:%S"))
    logger.info("  Mode: %s", "DRY RUN" if args.dry_run else "LIVE")
    logger.info("=" * 60)

    # Market day check
    if date.today().weekday() >= 5:
        logger.info("Weekend. Skipping.")
        return

    results = check_positions(dry_run=args.dry_run)

    # Write status for remote monitoring
    _write_monitor_status(results)

    # Summary
    if results:
        logger.info("=" * 60)
        logger.info("SUMMARY")
        logger.info("=" * 60)
        for r in results:
            logger.info(
                "  %s [%s] Score=%.0f -> %s",
                r.ticker, r.strategy, r.total_score, r.recommendation,
            )


def _write_monitor_status(results: list[ExitAnalysis]) -> None:
    """Write monitor status to vps_status.json for remote monitoring."""
    status_path = Path(__file__).resolve().parent.parent / "data" / "vps_status.json"
    positions = load_positions()
    open_pos = [p for p in positions if p.get("status") == "open"]
    status = {
        "timestamp": datetime.now().isoformat(),
        "date": str(date.today()),
        "source": "position_monitor",
        "open_positions": len(open_pos),
        "positions": [
            {
                "ticker": p.get("ticker"),
                "strategy": p.get("strategy"),
                "entry_price": p.get("entry_price"),
                "size": p.get("size"),
                "hold_days": p.get("hold_days", 0),
                "status": p.get("status"),
            }
            for p in open_pos
        ],
        "exit_analyses": [
            {
                "ticker": r.ticker,
                "strategy": r.strategy,
                "score": r.total_score,
                "recommendation": r.recommendation,
            }
            for r in results
        ],
    }
    try:
        status_path.write_text(
            json.dumps(status, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
    except Exception:
        pass


if __name__ == "__main__":
    main()
