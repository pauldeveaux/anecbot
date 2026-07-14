from datetime import date, datetime, time

import pytest

from anecbot.utils.time import (
    next_active_day,
    next_publication_datetime,
    next_reveal_datetime,
    parse_days_off,
    parse_time,
)

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


# --- parse_time ---


def test_parse_time_normal():
    """Parse HH:MM into time object."""
    assert parse_time("15:00") == time(15, 0)


def test_parse_time_midnight():
    """Parse midnight."""
    assert parse_time("00:00") == time(0, 0)


def test_parse_time_end_of_day():
    """Parse 23:59."""
    assert parse_time("23:59") == time(23, 59)


# --- next_publication_datetime ---


def test_first_pub_before_publish_time():
    """First pub, current time before publish_time on active day → today."""
    now = datetime(2026, 7, 13, 10, 0)  # Monday 10:00
    result = next_publication_datetime(None, 3, "15:00", WEEKEND, now)
    assert result == datetime(2026, 7, 13, 15, 0)  # Monday 15:00


def test_first_pub_after_publish_time():
    """First pub, current time after publish_time → next active day."""
    now = datetime(2026, 7, 13, 16, 0)  # Monday 16:00
    result = next_publication_datetime(None, 3, "15:00", WEEKEND, now)
    assert result == datetime(2026, 7, 14, 15, 0)  # Tuesday 15:00


def test_first_pub_on_day_off():
    """First pub, today is a day off → next active day."""
    now = datetime(2026, 7, 18, 10, 0)  # Saturday 10:00
    result = next_publication_datetime(None, 3, "15:00", WEEKEND, now)
    assert result == datetime(2026, 7, 20, 15, 0)  # Monday 15:00


def test_pub_normal_no_days_off():
    """Normal interval, no days off."""
    last = datetime(2026, 7, 13, 15, 0)  # Monday 15:00
    now = datetime(2026, 7, 13, 16, 0)
    result = next_publication_datetime(last, 3, "15:00", set(), now)
    assert result == datetime(2026, 7, 16, 15, 0)  # Thursday 15:00


def test_pub_normal_weekend_off_active():
    """Normal interval, weekend off, landing on active day."""
    last = datetime(2026, 7, 13, 15, 0)  # Monday 15:00
    now = datetime(2026, 7, 13, 16, 0)
    result = next_publication_datetime(last, 3, "15:00", WEEKEND, now)
    assert result == datetime(2026, 7, 16, 15, 0)  # Thursday 15:00


def test_pub_normal_weekend_off_skip():
    """Normal interval, weekend off, would land on day off → skip."""
    last = datetime(2026, 7, 15, 15, 0)  # Wednesday 15:00
    now = datetime(2026, 7, 15, 16, 0)
    result = next_publication_datetime(last, 3, "15:00", WEEKEND, now)
    # Wed + 3 active = Thu(1), Fri(2), Mon(3)
    assert result == datetime(2026, 7, 20, 15, 0)  # Monday 15:00


def test_pub_bot_offline_catchup():
    """Bot offline: last_published far in past → reschedule from now."""
    last = datetime(2026, 7, 6, 15, 0)  # Monday a week ago
    now = datetime(2026, 7, 14, 10, 0)  # Tuesday 10:00
    # next_active_day(July 6, 3, weekend) = July 9 (Thursday)
    # July 9 15:00 < July 14 10:00 → in the past
    # Reschedule: today Tuesday is active, 10:00 < 15:00 → today
    result = next_publication_datetime(last, 3, "15:00", WEEKEND, now)
    assert result == datetime(2026, 7, 14, 15, 0)  # Tuesday 15:00 today


def test_pub_bot_offline_catchup_after_time():
    """Bot offline, catch-up but publish_time already passed today."""
    last = datetime(2026, 7, 6, 15, 0)  # Monday a week ago
    now = datetime(2026, 7, 14, 16, 0)  # Tuesday 16:00
    # Computed date in past, today active but 16:00 > 15:00 → next active day
    result = next_publication_datetime(last, 3, "15:00", WEEKEND, now)
    assert result == datetime(2026, 7, 15, 15, 0)  # Wednesday 15:00


def test_pub_config_reduce_interval():
    """Config change: reduce interval (7→2), computed date in past → reschedule."""
    last = datetime(2026, 7, 13, 15, 0)  # Monday 15:00
    now = datetime(2026, 7, 14, 10, 0)  # Tuesday 10:00, next day

    # With old interval=7: next would be next Wednesday (7 active days)
    result_old = next_publication_datetime(last, 7, "15:00", WEEKEND, now)
    assert result_old == datetime(2026, 7, 22, 15, 0)  # Wednesday next week

    # Config changed to interval=2: Mon + 2 active = Wed
    result_new = next_publication_datetime(last, 2, "15:00", WEEKEND, now)
    assert result_new == datetime(2026, 7, 15, 15, 0)  # Wednesday this week

    # After that pub happens (Wed 15:00), next with interval=2:
    result_after = next_publication_datetime(
        result_new, 2, "15:00", WEEKEND, now=datetime(2026, 7, 15, 16, 0)
    )
    assert result_after == datetime(2026, 7, 17, 15, 0)  # Friday


def test_pub_config_increase_interval():
    """Config change: increase interval (2→7), computed date in future → keep."""
    last = datetime(2026, 7, 13, 15, 0)  # Monday 15:00
    now = datetime(2026, 7, 14, 10, 0)  # Tuesday 10:00

    # With old interval=2: Mon + 2 active = Wed
    result_old = next_publication_datetime(last, 2, "15:00", WEEKEND, now)
    assert result_old == datetime(2026, 7, 15, 15, 0)  # Wednesday

    # Config changed to interval=7: Mon + 7 active = Wed next week
    result_new = next_publication_datetime(last, 7, "15:00", WEEKEND, now)
    assert result_new == datetime(2026, 7, 22, 15, 0)  # Wednesday next week
    assert result_new > result_old  # Further out


def test_pub_config_change_days_off():
    """Config change: days off changed between publications."""
    last = datetime(2026, 7, 13, 15, 0)  # Monday 15:00
    now = datetime(2026, 7, 13, 16, 0)

    # Weekend off: Mon + 3 active = Thu
    result1 = next_publication_datetime(last, 3, "15:00", WEEKEND, now)
    assert result1 == datetime(2026, 7, 16, 15, 0)  # Thursday

    # After pub Thu, days off changes: Fri also off {4, 5, 6}
    now2 = datetime(2026, 7, 16, 16, 0)
    result2 = next_publication_datetime(result1, 3, "15:00", {4, 5, 6}, now2)
    # Thu + 3 active (skip Fri/Sat/Sun): Mon(1), Tue(2), Wed(3)
    assert result2 == datetime(2026, 7, 22, 15, 0)  # Wednesday


# --- next_reveal_datetime ---


def test_reveal_interval_one_no_days_off():
    """Reveal interval=1, no days off → next day at reveal_time."""
    published = datetime(2026, 7, 13, 15, 0)  # Monday
    result = next_reveal_datetime(published, 1, "13:30", set())
    assert result == datetime(2026, 7, 14, 13, 30)  # Tuesday 13:30


def test_reveal_interval_zero():
    """Reveal interval=0 → same day at reveal_time."""
    published = datetime(2026, 7, 13, 15, 0)  # Monday
    result = next_reveal_datetime(published, 0, "13:30", set())
    assert result == datetime(2026, 7, 13, 13, 30)  # Monday 13:30


def test_reveal_day_off_skip():
    """Reveal day is a day off → skip to next active."""
    published = datetime(2026, 7, 17, 15, 0)  # Friday
    result = next_reveal_datetime(published, 1, "13:30", WEEKEND)
    # Fri + 1 active: skip Sat/Sun, Mon(1)
    assert result == datetime(2026, 7, 20, 13, 30)  # Monday 13:30


def test_reveal_weekend_off_publish_friday():
    """Weekend off, publish Friday, reveal interval=2 → Tuesday."""
    published = datetime(2026, 7, 17, 15, 0)  # Friday
    result = next_reveal_datetime(published, 2, "13:30", WEEKEND)
    # Fri + 2 active: skip Sat/Sun, Mon(1), Tue(2)
    assert result == datetime(2026, 7, 21, 13, 30)  # Tuesday 13:30
