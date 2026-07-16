from datetime import date, datetime, time, timezone

import pytest

from anecbot.models.enums import LeaderboardResetMode
from anecbot.utils.time import (
    discord_timestamp,
    discord_timestamp_full_relative,
    next_active_day,
    next_leaderboard_reset_datetime,
    next_publication_datetime,
    next_reveal_datetime,
    parse_days_off,
    parse_time,
)

WEEKEND = {5, 6}  # Saturday, Sunday


# --- discord_timestamp / discord_timestamp_full_relative ---


def test_discord_timestamp_full_relative_treats_naive_datetime_as_utc():
    """The Unix timestamp is computed as if dt were UTC, regardless of the system's local tz.

    Regression test: naive datetime.timestamp() interprets the value as local system time,
    not UTC. Since every naive datetime in this codebase is UTC (via utcnow()), computing
    .timestamp() directly silently shifted every rendered Discord timestamp by the host
    machine's UTC offset — a genuinely future UTC time could render as already past.
    """
    dt = datetime(2026, 7, 16, 13, 47)
    expected_unix = int(dt.replace(tzinfo=timezone.utc).timestamp())

    result = discord_timestamp_full_relative(dt)

    assert f"<t:{expected_unix}:f>" in result
    assert f"<t:{expected_unix}:R>" in result


def test_discord_timestamp_treats_naive_datetime_as_utc():
    """Same UTC-interpretation fix, for the single-timestamp variant."""
    iso = "2026-07-16T13:47:00"
    expected_unix = int(
        datetime.fromisoformat(iso).replace(tzinfo=timezone.utc).timestamp()
    )

    result = discord_timestamp(iso)

    assert result == f"<t:{expected_unix}:f>"


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


# --- next_leaderboard_reset_datetime — DAILY ---


def test_leaderboard_daily_first_reset_is_now():
    """DAILY, never reset before → due immediately (now)."""
    now = datetime(2026, 7, 13, 10, 0)
    result = next_leaderboard_reset_datetime(
        None, LeaderboardResetMode.DAILY, 1, None, now
    )
    assert result == now


def test_leaderboard_daily_subsequent():
    """DAILY, subsequent reset → last_reset + interval days."""
    last = datetime(2026, 7, 10, 0, 0)
    now = datetime(2026, 7, 13, 10, 0)
    result = next_leaderboard_reset_datetime(
        last, LeaderboardResetMode.DAILY, 3, None, now
    )
    assert result == datetime(2026, 7, 13, 0, 0)


# --- next_leaderboard_reset_datetime — WEEKLY (anchor = weekday, 0=Mon) ---


def test_leaderboard_weekly_first_reset_today_matches_anchor():
    """WEEKLY, never reset, today is the anchor weekday → due today at midnight."""
    now = datetime(2026, 7, 13, 10, 0)  # Monday
    result = next_leaderboard_reset_datetime(
        None, LeaderboardResetMode.WEEKLY, 1, 0, now
    )
    assert result == datetime(2026, 7, 13, 0, 0)


def test_leaderboard_weekly_first_reset_future_anchor():
    """WEEKLY, never reset, anchor weekday is later this week."""
    now = datetime(2026, 7, 13, 10, 0)  # Monday
    result = next_leaderboard_reset_datetime(
        None, LeaderboardResetMode.WEEKLY, 1, 3, now
    )
    assert result == datetime(2026, 7, 16, 0, 0)  # Thursday


def test_leaderboard_weekly_first_reset_anchor_passed_rounds_to_interval():
    """WEEKLY, never reset, anchor weekday already passed this week, interval=2 →
    skips a full interval of weeks rather than just the next occurrence."""
    now = datetime(2026, 7, 16, 10, 0)  # Thursday
    result = next_leaderboard_reset_datetime(
        None, LeaderboardResetMode.WEEKLY, 2, 0, now
    )
    # This week's Monday (2026-07-13) already passed; interval=2 → +2 weeks from it
    assert result == datetime(2026, 7, 27, 0, 0)  # Monday two weeks later


def test_leaderboard_weekly_subsequent():
    """WEEKLY, subsequent reset → last_reset + interval weeks."""
    last = datetime(2026, 7, 13, 0, 0)  # Monday
    now = datetime(2026, 7, 14, 10, 0)
    result = next_leaderboard_reset_datetime(
        last, LeaderboardResetMode.WEEKLY, 2, 0, now
    )
    assert result == datetime(2026, 7, 27, 0, 0)  # 2 weeks later, still Monday


# --- next_leaderboard_reset_datetime — MONTHLY (anchor = day of month) ---


def test_leaderboard_monthly_first_reset_before_anchor_this_month():
    """MONTHLY, never reset, today's day-of-month is before the anchor → this month."""
    now = datetime(2026, 7, 10, 10, 0)
    result = next_leaderboard_reset_datetime(
        None, LeaderboardResetMode.MONTHLY, 1, 15, now
    )
    assert result == datetime(2026, 7, 15, 0, 0)


def test_leaderboard_monthly_first_reset_today_matches_anchor():
    """MONTHLY, never reset, today's day-of-month equals the anchor → due today."""
    now = datetime(2026, 7, 10, 10, 0)
    result = next_leaderboard_reset_datetime(
        None, LeaderboardResetMode.MONTHLY, 1, 10, now
    )
    assert result == datetime(2026, 7, 10, 0, 0)


def test_leaderboard_monthly_first_reset_after_anchor_next_month():
    """MONTHLY, never reset, today's day-of-month is past the anchor → next month."""
    now = datetime(2026, 7, 10, 10, 0)
    result = next_leaderboard_reset_datetime(
        None, LeaderboardResetMode.MONTHLY, 1, 5, now
    )
    assert result == datetime(2026, 8, 5, 0, 0)


def test_leaderboard_monthly_first_reset_anchor_passed_rounds_to_interval():
    """MONTHLY, never reset, anchor already passed this month, interval=2 →
    skips a full interval of months rather than just next month."""
    now = datetime(2026, 7, 16, 10, 0)
    result = next_leaderboard_reset_datetime(
        None, LeaderboardResetMode.MONTHLY, 2, 1, now
    )
    assert result == datetime(2026, 9, 1, 0, 0)


def test_leaderboard_monthly_subsequent():
    """MONTHLY, subsequent reset → interval months later, same anchor day."""
    last = datetime(2026, 7, 15, 0, 0)
    now = datetime(2026, 7, 16, 10, 0)
    result = next_leaderboard_reset_datetime(
        last, LeaderboardResetMode.MONTHLY, 1, 15, now
    )
    assert result == datetime(2026, 8, 15, 0, 0)


def test_leaderboard_monthly_clamps_to_last_valid_day():
    """MONTHLY, anchor=29 lands in a non-leap February → clamped to 28."""
    last = datetime(2026, 1, 29, 0, 0)
    now = datetime(2026, 1, 30, 10, 0)
    result = next_leaderboard_reset_datetime(
        last, LeaderboardResetMode.MONTHLY, 1, 29, now
    )
    assert result == datetime(2026, 2, 28, 0, 0)  # 2026 is not a leap year


# --- next_leaderboard_reset_datetime — YEARLY (anchor = day of year) ---


def test_leaderboard_yearly_first_reset_later_this_year():
    """YEARLY, never reset, anchor day-of-year hasn't passed yet → this year."""
    now = datetime(2026, 1, 15, 10, 0)
    result = next_leaderboard_reset_datetime(
        None, LeaderboardResetMode.YEARLY, 1, 32, now
    )
    assert result == datetime(2026, 2, 1, 0, 0)  # day 32 = Feb 1


def test_leaderboard_yearly_first_reset_already_passed_next_year():
    """YEARLY, never reset, anchor day-of-year already passed → next year."""
    now = datetime(2026, 6, 1, 10, 0)
    result = next_leaderboard_reset_datetime(
        None, LeaderboardResetMode.YEARLY, 1, 1, now
    )
    assert result == datetime(2027, 1, 1, 0, 0)


def test_leaderboard_yearly_first_reset_anchor_passed_rounds_to_interval():
    """YEARLY, never reset, anchor day-of-year already passed, interval=2 →
    skips a full interval of years rather than just next year."""
    now = datetime(2026, 6, 1, 10, 0)
    result = next_leaderboard_reset_datetime(
        None, LeaderboardResetMode.YEARLY, 2, 1, now
    )
    assert result == datetime(2028, 1, 1, 0, 0)


def test_leaderboard_yearly_subsequent():
    """YEARLY, subsequent reset → interval years later, same day-of-year."""
    last = datetime(2026, 2, 1, 0, 0)  # day 32
    now = datetime(2026, 2, 2, 10, 0)
    result = next_leaderboard_reset_datetime(
        last, LeaderboardResetMode.YEARLY, 1, 32, now
    )
    assert result == datetime(2027, 2, 1, 0, 0)


def test_leaderboard_reset_never_mode_asserts():
    """Calling with mode=NEVER is a precondition violation, not a valid input."""
    now = datetime(2026, 7, 13, 10, 0)
    with pytest.raises(AssertionError):
        next_leaderboard_reset_datetime(None, LeaderboardResetMode.NEVER, 1, None, now)
