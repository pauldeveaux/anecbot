from enum import StrEnum


class RevealMode(StrEnum):
    """Reveal cadence: per-anecdote offset, or batched on a fixed interval."""

    AFTER_PUBLISH = "after-publish"
    INTERVAL = "interval"


class LeaderboardResetMode(StrEnum):
    """Leaderboard reset cadence unit."""

    NEVER = "never"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
