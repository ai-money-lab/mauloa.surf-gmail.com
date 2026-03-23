"""Regime Filter — VIX/日経VI based strategy selector.

Uses volatility index as a master switch for all other signals:
    - Low vol (< 20):   Trend-following strategies favored
    - Normal (20-25):   Standard signals apply
    - High vol (> 25):  Mean-reversion strategies favored, reduce size
    - Extreme (> 35):   Reduce all positions, tighten stops

Also includes calendar-based regime awareness:
    - SQ week (2nd Friday of month): elevated volatility
    - 魔の水曜日: SQ week Wednesday bearish bias
    - BOJ meeting days: no new positions
    - Quarter-end rebalancing: last 3 business days
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta

logger = logging.getLogger(__name__)


def _second_friday(year: int, month: int) -> date:
    """Return the date of the 2nd Friday of the given month."""
    first_day = date(year, month, 1)
    days_until_friday = (4 - first_day.weekday()) % 7
    first_friday = first_day + timedelta(days=days_until_friday)
    return first_friday + timedelta(weeks=1)


@dataclass
class RegimeState:
    """Current market regime assessment."""
    volatility_regime: str     # "low" / "normal" / "high" / "extreme"
    vi_level: float
    position_size_multiplier: float  # 0.0-1.0
    preferred_strategy: str    # "trend" / "standard" / "mean_reversion" / "defensive"
    calendar_flags: list[str] = field(default_factory=list)
    detail: str = ""


# Major SQ months where futures + options settle
_MAJOR_SQ_MONTHS = {3, 6, 9, 12}

# BOJ meeting dates for 2026 (announced annually; update as needed)
_BOJ_MEETING_DATES_2026 = [
    date(2026, 1, 23), date(2026, 1, 24),
    date(2026, 3, 13), date(2026, 3, 14),
    date(2026, 4, 30), date(2026, 5, 1),
    date(2026, 6, 12), date(2026, 6, 13),
    date(2026, 7, 30), date(2026, 7, 31),
    date(2026, 9, 17), date(2026, 9, 18),
    date(2026, 10, 29), date(2026, 10, 30),
    date(2026, 12, 17), date(2026, 12, 18),
]


def compute_regime(
    vi_level: float,
    today: date | str | None = None,
) -> RegimeState:
    """Compute the current regime state from volatility and calendar.

    Args:
        vi_level: Current 日経VI (or VIX if JP data unavailable)
        today: Date to check calendar events (defaults to today)

    Returns:
        RegimeState with regime, size multiplier, and calendar flags.
    """
    if isinstance(today, str):
        today = date.fromisoformat(today)
    today = today or date.today()

    # Volatility regime
    if vi_level < 20:
        regime = "low"
        size_mult = 1.0
        strategy = "trend"
    elif vi_level < 25:
        regime = "normal"
        size_mult = 1.0
        strategy = "standard"
    elif vi_level < 35:
        regime = "high"
        size_mult = 0.5
        strategy = "mean_reversion"
    else:
        regime = "extreme"
        size_mult = 0.25
        strategy = "defensive"

    # Calendar events
    flags: list[str] = []

    # SQ week check
    sq_date = _second_friday(today.year, today.month)
    sq_week_start = sq_date - timedelta(days=sq_date.weekday())  # Monday of SQ week
    if sq_week_start <= today <= sq_date:
        is_major = today.month in _MAJOR_SQ_MONTHS
        sq_type = "メジャーSQ" if is_major else "マイナーSQ"
        flags.append(f"SQ週({sq_type}, SQ日={sq_date.isoformat()})")
        size_mult *= 0.7  # reduce 30% during SQ week

        # 魔の水曜日
        if today.weekday() == 2:  # Wednesday
            flags.append("魔の水曜日 — 弱気バイアス")

        # SQ day itself
        if today == sq_date:
            flags.append("SQ当日 — 寄付参加注意")
            size_mult *= 0.5

    # BOJ meeting day
    if today in _BOJ_MEETING_DATES_2026:
        flags.append("BOJ金融政策決定会合日 — 新規ポジション非推奨")
        size_mult *= 0.5

    # Quarter-end rebalancing (last 3 business days of quarter)
    quarter_end_months = {3, 6, 9, 12}
    if today.month in quarter_end_months:
        # Check if we're in the last 5 calendar days (approximates last 3 biz days)
        next_month = today.month + 1 if today.month < 12 else 1
        next_year = today.year if today.month < 12 else today.year + 1
        quarter_end = date(next_year, next_month, 1) - timedelta(days=1)
        days_to_end = (quarter_end - today).days
        if 0 <= days_to_end <= 4:
            flags.append(f"四半期末リバランス期間(残{days_to_end}日)")

    # Month-end (last 3 calendar days)
    next_month = today.month + 1 if today.month < 12 else 1
    next_year = today.year if today.month < 12 else today.year + 1
    month_end = date(next_year, next_month, 1) - timedelta(days=1)
    days_to_month_end = (month_end - today).days
    if 0 <= days_to_month_end <= 2:
        flags.append(f"月末リバランス期間(残{days_to_month_end}日)")

    size_mult = max(round(size_mult, 2), 0.1)

    detail_parts = [f"日経VI={vi_level:.1f} → {regime}レジーム, サイズ{size_mult:.0%}"]
    if flags:
        detail_parts.extend(flags)
    detail = " | ".join(detail_parts)

    state = RegimeState(
        volatility_regime=regime,
        vi_level=vi_level,
        position_size_multiplier=size_mult,
        preferred_strategy=strategy,
        calendar_flags=flags,
        detail=detail,
    )

    logger.info("Regime: %s size=%.0f%% flags=%s", regime, size_mult * 100, flags)
    return state
