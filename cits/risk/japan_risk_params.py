"""Japan-specific risk parameters and calendar data.

Centralizes all TSE/JPX-specific risk adjustments:
- 売買単位 (lot sizes)
- SQ dates
- BOJ meeting dates
- 権利付最終日 (ex-rights dates)
- 市場時間 (trading hours)
- 値幅制限 (price limit rules)
"""

from __future__ import annotations

import datetime as _dt
from typing import Any

# ---------------------------------------------------------------------------
# TSE trading hours  前場 / 後場
# ---------------------------------------------------------------------------
MORNING_OPEN = _dt.time(9, 0)
MORNING_CLOSE = _dt.time(11, 30)
AFTERNOON_OPEN = _dt.time(12, 30)
AFTERNOON_CLOSE = _dt.time(15, 0)

# ---------------------------------------------------------------------------
# 値幅制限 (price limit) table — (upper_bound, limit_range)
# upper_bound is *inclusive*; the last entry uses float("inf").
# ---------------------------------------------------------------------------
_PRICE_LIMIT_TABLE: list[tuple[float, int]] = [
    (100, 30),
    (200, 50),
    (500, 80),
    (700, 100),
    (1_000, 150),
    (1_500, 300),
    (2_000, 400),
    (3_000, 500),
    (5_000, 700),
    (7_000, 1_000),
    (10_000, 1_500),
    (15_000, 3_000),
    (20_000, 4_000),
    (30_000, 5_000),
    (50_000, 7_000),
    (70_000, 10_000),
    (100_000, 15_000),
    (float("inf"), 30_000),
]

# ---------------------------------------------------------------------------
# SQ dates for 2026 — 2nd Friday of each month
# ---------------------------------------------------------------------------


def _second_friday(year: int, month: int) -> _dt.date:
    """Return the second Friday of the given month."""
    first = _dt.date(year, month, 1)
    # weekday(): Monday=0 … Friday=4
    days_until_friday = (4 - first.weekday()) % 7
    first_friday = first + _dt.timedelta(days=days_until_friday)
    return first_friday + _dt.timedelta(weeks=1)


SQ_DATES_2026: list[_dt.date] = [_second_friday(2026, m) for m in range(1, 13)]

# Major SQ (メジャーSQ) months: March, June, September, December
MAJOR_SQ_DATES_2026: list[_dt.date] = [
    _second_friday(2026, m) for m in (3, 6, 9, 12)
]

# ---------------------------------------------------------------------------
# 権利付最終日 2026 (quarterly: 3月, 9月)
# Rights are determined 2 business days before month-end.
# These are pre-calculated for 2026.
# ---------------------------------------------------------------------------
EX_RIGHTS_DATES_2026: list[_dt.date] = [
    _dt.date(2026, 3, 27),  # 3月期末 権利付最終日
    _dt.date(2026, 9, 28),  # 9月中間 権利付最終日
]

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_price_limit(base_price: float) -> tuple[float, float]:
    """Return (lower_limit, upper_limit) for a given base price per TSE rules.

    >>> get_price_limit(1500)
    (1200.0, 1800.0)
    """
    for upper_bound, limit_range in _PRICE_LIMIT_TABLE:
        if base_price <= upper_bound:
            return (base_price - limit_range, base_price + limit_range)
    # Should never reach here because the last entry is inf
    limit_range = _PRICE_LIMIT_TABLE[-1][1]
    return (base_price - limit_range, base_price + limit_range)


def get_lot_size(ticker: str) -> int:  # noqa: ARG001
    """Return the trading lot size for a given ticker.

    As of 2024-10 all TSE-listed stocks trade in 100-share lots.
    This function exists as a central place to add exceptions if the
    exchange ever re-introduces non-standard lot sizes.
    """
    return 100


def is_trading_hours(dt: _dt.datetime) -> bool:
    """Return True if *dt* falls within TSE trading hours (JST assumed).

    Checks weekday (Mon-Fri) and session times:
    - 前場: 09:00 – 11:30
    - 後場: 12:30 – 15:00
    """
    if dt.weekday() >= 5:  # Saturday / Sunday
        return False
    t = dt.time()
    in_morning = MORNING_OPEN <= t < MORNING_CLOSE
    in_afternoon = AFTERNOON_OPEN <= t < AFTERNOON_CLOSE
    return in_morning or in_afternoon


def get_risk_adjustments(
    date: _dt.date,
    vi_level: float = 0.0,
) -> dict[str, Any]:
    """Return a dict of risk adjustments for the given date and VI level.

    Keys returned:
    - ``position_scale``: multiplier to apply to normal position size (0.0–1.0)
    - ``reason``: human-readable explanation of the adjustment
    - ``is_sq``: whether *date* is an SQ settlement day
    - ``is_major_sq``: whether *date* is a Major SQ day
    - ``is_ex_rights``: whether *date* is a 権利付最終日
    - ``near_ex_rights``: True if within 3 business days of ex-rights date
    """
    reasons: list[str] = []
    scale = 1.0

    # --- SQ check ---
    is_sq = date in SQ_DATES_2026
    is_major_sq = date in MAJOR_SQ_DATES_2026
    if is_major_sq:
        scale *= 0.5
        reasons.append("メジャーSQ日: ポジション50%縮小")
    elif is_sq:
        scale *= 0.7
        reasons.append("SQ日: ポジション30%縮小")

    # --- Ex-rights proximity ---
    is_ex_rights = date in EX_RIGHTS_DATES_2026
    near_ex_rights = any(
        0 <= (ex - date).days <= 3 for ex in EX_RIGHTS_DATES_2026
    )
    if is_ex_rights:
        scale *= 0.5
        reasons.append("権利付最終日: ポジション50%縮小")
    elif near_ex_rights:
        scale *= 0.7
        reasons.append("権利付最終日3営業日以内: ポジション30%縮小")

    # --- Volatility index ---
    if vi_level >= 30:
        scale *= 0.3
        reasons.append(f"VI={vi_level:.1f} ≥ 30: ポジション70%縮小")
    elif vi_level >= 25:
        scale *= 0.5
        reasons.append(f"VI={vi_level:.1f} ≥ 25: ポジション50%縮小")
    elif vi_level >= 20:
        scale *= 0.7
        reasons.append(f"VI={vi_level:.1f} ≥ 20: ポジション30%縮小")

    reason = "; ".join(reasons) if reasons else "通常リスク"

    return {
        "position_scale": round(scale, 4),
        "reason": reason,
        "is_sq": is_sq,
        "is_major_sq": is_major_sq,
        "is_ex_rights": is_ex_rights,
        "near_ex_rights": near_ex_rights,
    }
