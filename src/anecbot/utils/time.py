from datetime import date, timedelta


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
