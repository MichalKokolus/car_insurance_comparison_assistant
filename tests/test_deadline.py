from datetime import date

from backend.deadlines import compute_cancellation_deadline


def test_deadline_this_year():
    # Anniversary later this year: renewal 2026-09-01, minus 42 days.
    result = compute_cancellation_deadline(date(2020, 9, 1), 42, today=date(2026, 7, 16))
    assert result == date(2026, 7, 21)


def test_deadline_rolls_to_next_year():
    # Anniversary already passed this year -> next renewal is next year.
    result = compute_cancellation_deadline(date(2020, 3, 1), 30, today=date(2026, 7, 16))
    assert result == date(2027, 1, 30)


def test_deadline_on_anniversary_day_counts_as_upcoming():
    result = compute_cancellation_deadline(date(2020, 7, 16), 0, today=date(2026, 7, 16))
    assert result == date(2026, 7, 16)


def test_leap_day_anniversary_clamps():
    # Feb 29 anniversary in a non-leap renewal year clamps to Feb 28.
    result = compute_cancellation_deadline(date(2020, 2, 29), 0, today=date(2026, 1, 1))
    assert result == date(2026, 2, 28)


def test_missing_inputs_return_none():
    assert compute_cancellation_deadline(None, 42) is None
    assert compute_cancellation_deadline(date(2020, 9, 1), None) is None
