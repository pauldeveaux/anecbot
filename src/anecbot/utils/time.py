import calendar
from datetime import date, datetime, time, timedelta, timezone

from anecbot.models.enums import LeaderboardResetMode

DISCORD_FULL = "f"
DISCORD_RELATIVE = "R"
DISCORD_SHORT_DATE = "d"
DISCORD_LONG_DATE = "D"
DISCORD_SHORT_TIME = "t"
DISCORD_LONG_TIME = "T"
DISCORD_SHORT_DATETIME = "f"
DISCORD_LONG_DATETIME = "F"


def utcnow() -> datetime:
    """Return the current UTC time as a naive datetime."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def discord_timestamp_full_relative(dt: datetime) -> str:
    """Format a datetime as Discord full + relative timestamps on two lines."""
    unix = int(dt.replace(tzinfo=timezone.utc).timestamp())
    return f"<t:{unix}:{DISCORD_FULL}>\n<t:{unix}:{DISCORD_RELATIVE}>"


def discord_timestamp(iso: str, style: str = DISCORD_FULL) -> str:
    """Format an ISO datetime as a Discord timestamp tag (localized per user)."""
    dt = datetime.fromisoformat(iso)
    return f"<t:{int(dt.replace(tzinfo=timezone.utc).timestamp())}:{style}>"


def parse_days_off(days_off_str: str) -> set[int]:
    """Parse comma-separated weekday numbers (0=Mon, 6=Sun) into a set."""
    stripped = days_off_str.strip()
    if not stripped:
        return set()
    return {int(d.strip()) for d in stripped.split(",")}


def next_active_day(from_date: date, interval_days: int, days_off: set[int]) -> date:
    """Return the date after advancing by interval_days active days from from_date."""
    if len(days_off) >= 7:
        raise ValueError("All days are marked as days off — no active days exist")

    if interval_days == 0:
        current = from_date
        while current.weekday() in days_off:
            current += timedelta(days=1)
        return current

    current = from_date
    counted = 0
    while counted < interval_days:
        current += timedelta(days=1)
        if current.weekday() not in days_off:
            counted += 1
    return current


def parse_time(time_str: str) -> time:
    """Parse HH:MM string into a time object."""
    h, m = time_str.strip().split(":")
    return time(int(h), int(m))


def next_publication_datetime(
    last_published: datetime | None,
    interval_days: int,
    publish_time: str,
    days_off: set[int],
    now: datetime,
) -> datetime:
    """Return the next datetime when a publication should happen."""
    target_time = parse_time(publish_time)

    if last_published is None:
        today = now.date()
        if today.weekday() not in days_off and now.time() < target_time:
            return datetime.combine(today, target_time)
        target = next_active_day(
            today, 0 if today.weekday() in days_off else 1, days_off
        )
        return datetime.combine(target, target_time)

    target_date = next_active_day(last_published.date(), interval_days, days_off)
    target_dt = datetime.combine(target_date, target_time)

    if target_dt <= now:
        today = now.date()
        if today.weekday() not in days_off and now.time() < target_time:
            return datetime.combine(today, target_time)
        target_date = next_active_day(
            today, 0 if today.weekday() in days_off else 1, days_off
        )
        return datetime.combine(target_date, target_time)

    return target_dt


def next_reveal_datetime(
    published_at: datetime,
    reveal_interval_days: int,
    reveal_time: str,
    days_off: set[int],
) -> datetime:
    """Return the datetime when a published anecdote should be revealed."""
    rev_time = parse_time(reveal_time)
    target_date = next_active_day(published_at.date(), reveal_interval_days, days_off)
    return datetime.combine(target_date, rev_time)


def _add_months(year: int, month: int, months: int) -> tuple[int, int]:
    """Add a number of months to a (year, month) pair, returning the new pair."""
    total = year * 12 + (month - 1) + months
    new_year, new_month0 = divmod(total, 12)
    return new_year, new_month0 + 1


def _clamped_month_date(year: int, month: int, day: int) -> date:
    """Return a date for (year, month, day), clamping day to the month's last valid day."""
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, last_day))


def next_leaderboard_reset_datetime(
    last_reset: datetime | None,
    mode: LeaderboardResetMode,
    interval: int,
    anchor: int | None,
    now: datetime,
) -> datetime:
    """Return the next datetime when the leaderboard should reset."""
    assert mode != LeaderboardResetMode.NEVER

    if mode == LeaderboardResetMode.DAILY:
        if last_reset is None:
            return now
        return last_reset + timedelta(days=interval)

    if mode == LeaderboardResetMode.WEEKLY:
        assert anchor is not None
        if last_reset is None:
            current_monday = now.date() - timedelta(days=now.weekday())
            this_week_anchor = current_monday + timedelta(days=anchor)
            if this_week_anchor < now.date():
                this_week_anchor += timedelta(weeks=interval)
            return datetime.combine(this_week_anchor, time())
        return last_reset + timedelta(weeks=interval)

    if mode == LeaderboardResetMode.MONTHLY:
        assert anchor is not None
        if last_reset is None:
            year, month = now.year, now.month
            if now.day > anchor:
                year, month = _add_months(year, month, interval)
        else:
            year, month = _add_months(last_reset.year, last_reset.month, interval)
        return datetime.combine(_clamped_month_date(year, month, anchor), time())

    assert anchor is not None
    if last_reset is None:
        year = now.year
        candidate = date(year, 1, 1) + timedelta(days=anchor - 1)
        if candidate < now.date():
            year += interval
    else:
        year = last_reset.year + interval
    target_date = date(year, 1, 1) + timedelta(days=anchor - 1)
    return datetime.combine(target_date, time())
