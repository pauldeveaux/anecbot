from enum import StrEnum


class PlayerRole(StrEnum):
    """Player role in a guild."""

    SUBMITTER = "submitter"
    TARGET = "target"
    ALL = "all"


class PlayerFilter(StrEnum):
    """Filter for listing players."""

    SUBMITTER = "submitter"
    TARGET = "target"
    BANNED = "banned"


class LeaderboardResetMode(StrEnum):
    """Leaderboard reset cadence unit."""

    NEVER = "never"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class VoteResult(StrEnum):
    """Outcome of attempting to record a vote."""

    RECORDED = "recorded"
    CLOSED = "closed"
