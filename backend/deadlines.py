"""Deterministic cancellation-deadline (vypoved) math. Pure Python — never the LLM."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional


def _make(year: int, month: int, day: int) -> date:
    """Build a date, clamping an invalid day (e.g. Feb 29 in a non-leap year) to 28."""
    try:
        return date(year, month, day)
    except ValueError:
        return date(year, month, 28)


def _next_occurrence(month: int, day: int, today: date) -> date:
    """Next occurrence of month/day on or after `today`."""
    this_year = _make(today.year, month, day)
    if this_year >= today:
        return this_year
    return _make(today.year + 1, month, day)


def compute_cancellation_deadline(
    anniversary: Optional[date],
    notice_period_days: Optional[int],
    today: Optional[date] = None,
) -> Optional[date]:
    """Last date a cancellation notice can be delivered before the next renewal.

    Returns None if either input is missing.
    """
    if anniversary is None or notice_period_days is None:
        return None
    today = today or date.today()
    renewal = _next_occurrence(anniversary.month, anniversary.day, today)
    return renewal - timedelta(days=notice_period_days)
