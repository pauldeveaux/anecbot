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


class AnecdoteState(StrEnum):
    """Lifecycle state of an anecdote in the idempotent batch (PENDING -> RUNNING -> PUBLISHED -> REVEALING -> REVEALED)."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PUBLISHED = "PUBLISHED"
    REVEALING = "REVEALING"
    REVEALED = "REVEALED"


class LeaderboardKind(StrEnum):
    """Ranking metric for a /leaderboard subcommand."""

    POINTS = "points"
    ACCURACY = "accuracy"
    PUBLISHED = "published"
    VOTES = "votes"


class VoteResult(StrEnum):
    """Outcome of attempting to record a vote."""

    RECORDED = "recorded"
    CLOSED = "closed"
    IS_AUTHOR = "is_author"


class GuildTimezone(StrEnum):
    """Predefined timezone choices for /config timezone (Discord caps choices at 25)."""

    EUROPE_PARIS = "Europe/Paris"
    EUROPE_BRUSSELS = "Europe/Brussels"
    EUROPE_ZURICH = "Europe/Zurich"
    EUROPE_LUXEMBOURG = "Europe/Luxembourg"
    EUROPE_LONDON = "Europe/London"
    AMERICA_TORONTO = "America/Toronto"
    AMERICA_MARTINIQUE = "America/Martinique"
    AMERICA_GUADELOUPE = "America/Guadeloupe"
    AMERICA_NEW_YORK = "America/New_York"
    INDIAN_REUNION = "Indian/Reunion"
    INDIAN_MAYOTTE = "Indian/Mayotte"
    PACIFIC_NOUMEA = "Pacific/Noumea"
    PACIFIC_TAHITI = "Pacific/Tahiti"
    AFRICA_ABIDJAN = "Africa/Abidjan"
    AFRICA_KINSHASA = "Africa/Kinshasa"
    UTC = "UTC"
