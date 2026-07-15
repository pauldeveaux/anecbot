from datetime import date, datetime, time, timedelta

DISCORD_FULL = "f"
DISCORD_RELATIVE = "R"
DISCORD_SHORT_DATE = "d"
DISCORD_LONG_DATE = "D"
DISCORD_SHORT_TIME = "t"
DISCORD_LONG_TIME = "T"
DISCORD_SHORT_DATETIME = "f"
DISCORD_LONG_DATETIME = "F"


def discord_timestamp(iso: str, style: str = DISCORD_FULL) -> str:
    """Format an ISO datetime as a Discord timestamp tag (localized per user)."""
    dt = datetime.fromisoformat(iso)
    return f"<t:{int(dt.timestamp())}:{style}>"


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
    pub_time = parse_time(publish_time)

    if last_published is None:
        today = now.date()
        if today.weekday() not in days_off and now.time() < pub_time:
            return datetime.combine(today, pub_time)
        target = next_active_day(
            today, 0 if today.weekday() in days_off else 1, days_off
        )
        return datetime.combine(target, pub_time)

    target_date = next_active_day(last_published.date(), interval_days, days_off)
    target_dt = datetime.combine(target_date, pub_time)

    if target_dt <= now:
        today = now.date()
        if today.weekday() not in days_off and now.time() < pub_time:
            return datetime.combine(today, pub_time)
        target_date = next_active_day(
            today, 0 if today.weekday() in days_off else 1, days_off
        )
        return datetime.combine(target_date, pub_time)

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
