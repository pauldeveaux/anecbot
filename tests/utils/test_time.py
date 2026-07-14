from datetime import date

import pytest

from anecbot.utils.time import next_active_day, parse_days_off

WEEKEND = {5, 6}  # Saturday, Sunday


# --- parse_days_off ---


def test_parse_empty_string():
    """Empty string returns empty set."""
    assert parse_days_off("") == set()


def test_parse_single_day():
    """Single day number."""
    assert parse_days_off("5") == {5}


def test_parse_multiple_days():
    """Comma-separated day numbers."""
    assert parse_days_off("5,6") == {5, 6}


def test_parse_whitespace():
    """Whitespace around values is stripped."""
    assert parse_days_off(" 5 , 6 ") == {5, 6}


# --- next_active_day — basic ---


def test_no_days_off():
    """No days off: from_date + interval."""
    # Monday 2026-07-13 + 3 = Thursday 2026-07-16
    result = next_active_day(date(2026, 7, 13), 3, set())
    assert result == date(2026, 7, 16)


def test_weekend_off_from_monday():
    """Weekend off, from Monday interval=3: Tue(1), Wed(2), Thu(3)."""
    # Monday 2026-07-13
    result = next_active_day(date(2026, 7, 13), 3, WEEKEND)
    assert result == date(2026, 7, 16)  # Thursday


def test_weekend_off_from_wednesday():
    """Weekend off, from Wednesday interval=3: Thu(1), Fri(2), skip Sat/Sun, Mon(3)."""
    # Wednesday 2026-07-15
    result = next_active_day(date(2026, 7, 15), 3, WEEKEND)
    assert result == date(2026, 7, 20)  # Monday


def test_weekend_off_from_thursday():
    """Weekend off, from Thursday interval=3: Fri(1), skip Sat/Sun, Mon(2), Tue(3)."""
    # Thursday 2026-07-16
    result = next_active_day(date(2026, 7, 16), 3, WEEKEND)
    assert result == date(2026, 7, 21)  # Tuesday


def test_weekend_off_from_friday():
    """Weekend off, from Friday interval=3: skip Sat/Sun, Mon(1), Tue(2), Wed(3)."""
    # Friday 2026-07-17
    result = next_active_day(date(2026, 7, 17), 3, WEEKEND)
    assert result == date(2026, 7, 22)  # Wednesday


# --- next_active_day — no collapsing ---


def test_no_collapsing_weekend_off():
    """Different start days must produce different results with same interval."""
    wed = next_active_day(date(2026, 7, 15), 3, WEEKEND)  # Wednesday
    thu = next_active_day(date(2026, 7, 16), 3, WEEKEND)  # Thursday
    fri = next_active_day(date(2026, 7, 17), 3, WEEKEND)  # Friday

    assert wed == date(2026, 7, 20)  # Monday
    assert thu == date(2026, 7, 21)  # Tuesday
    assert fri == date(2026, 7, 22)  # Wednesday
    assert len({wed, thu, fri}) == 3  # All different


# --- next_active_day — interval=0 ---


def test_interval_zero_active_day():
    """Interval 0 on active day returns same day."""
    # Monday
    result = next_active_day(date(2026, 7, 13), 0, WEEKEND)
    assert result == date(2026, 7, 13)


def test_interval_zero_day_off():
    """Interval 0 on day off returns next active day."""
    # Saturday 2026-07-18
    result = next_active_day(date(2026, 7, 18), 0, WEEKEND)
    assert result == date(2026, 7, 20)  # Monday


def test_interval_zero_sunday():
    """Interval 0 on Sunday returns Monday."""
    # Sunday 2026-07-19
    result = next_active_day(date(2026, 7, 19), 0, WEEKEND)
    assert result == date(2026, 7, 20)  # Monday


# --- next_active_day — extreme ---


def test_six_days_off_interval_one():
    """Only Monday active (days_off=Tue-Sun), interval=1 → next Monday."""
    only_monday = {1, 2, 3, 4, 5, 6}  # Tue through Sun off
    # Monday 2026-07-13
    result = next_active_day(date(2026, 7, 13), 1, only_monday)
    assert result == date(2026, 7, 20)  # Next Monday


def test_six_days_off_interval_two():
    """Only Monday active, interval=2 → Monday after next."""
    only_monday = {1, 2, 3, 4, 5, 6}
    # Monday 2026-07-13
    result = next_active_day(date(2026, 7, 13), 2, only_monday)
    assert result == date(2026, 7, 27)  # Two Mondays later


def test_all_days_off_raises():
    """All 7 days off raises ValueError."""
    all_off = {0, 1, 2, 3, 4, 5, 6}
    with pytest.raises(ValueError, match="no active days"):
        next_active_day(date(2026, 7, 13), 1, all_off)


# --- next_active_day — config change ---


def test_config_change_add_day_off():
    """Config change: add Friday to days off between two computations."""
    # First: weekend off, from Monday interval=3 → Thursday
    first = next_active_day(date(2026, 7, 13), 3, WEEKEND)
    assert first == date(2026, 7, 16)  # Thursday

    # Config changes: Friday also off now {4, 5, 6}
    extended_off = {4, 5, 6}
    second = next_active_day(first, 3, extended_off)
    # From Thursday: skip Fri/Sat/Sun, Mon(1), Tue(2), Wed(3)
    assert second == date(2026, 7, 22)  # Wednesday


def test_config_change_remove_day_off():
    """Config change: remove days off between two computations."""
    # First: weekend off, from Monday interval=3 → Thursday
    first = next_active_day(date(2026, 7, 13), 3, WEEKEND)
    assert first == date(2026, 7, 16)  # Thursday

    # Config changes: no days off anymore
    second = next_active_day(first, 3, set())
    # From Thursday: Fri(1), Sat(2), Sun(3)
    assert second == date(2026, 7, 19)  # Sunday


def test_config_change_swap_days_off():
    """Config change: swap which days are off."""
    # First: Mon/Tue off, from Wednesday interval=2
    first = next_active_day(date(2026, 7, 15), 2, {0, 1})
    # Wed→Thu(1), Fri(2)
    assert first == date(2026, 7, 17)  # Friday

    # Config changes: Thu/Fri off now
    second = next_active_day(first, 2, {3, 4})
    # Fri→skip Sat/Sun are active now, Sat(1), Sun(2)
    assert second == date(2026, 7, 19)  # Sunday
