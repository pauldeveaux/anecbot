from anecbot.models.enums import LeaderboardResetMode

RESET_UNIT_LABELS: dict[LeaderboardResetMode, str] = {
    LeaderboardResetMode.NEVER: "",
    LeaderboardResetMode.DAILY: "jour(s)",
    LeaderboardResetMode.WEEKLY: "semaine(s)",
    LeaderboardResetMode.MONTHLY: "mois",
    LeaderboardResetMode.YEARLY: "an(s)",
}

WEEKDAY_NAMES = [
    "lundi",
    "mardi",
    "mercredi",
    "jeudi",
    "vendredi",
    "samedi",
    "dimanche",
]

DEFAULT_ANCHORS: dict[LeaderboardResetMode, int | None] = {
    LeaderboardResetMode.NEVER: None,
    LeaderboardResetMode.DAILY: None,
    LeaderboardResetMode.WEEKLY: 0,
    LeaderboardResetMode.MONTHLY: 1,
    LeaderboardResetMode.YEARLY: 1,
}


def format_leaderboard_reset_interval(mode: LeaderboardResetMode, interval: int) -> str:
    """Format the leaderboard reset interval value according to the given mode."""
    return f"tous les {interval} {RESET_UNIT_LABELS[mode]}"


def format_leaderboard_reset_anchor(
    mode: LeaderboardResetMode, anchor: int | None
) -> str:
    """Format the leaderboard reset anchor value according to the given mode."""
    if mode in (LeaderboardResetMode.NEVER, LeaderboardResetMode.DAILY):
        return "n/a"
    if anchor is None:
        return "non défini"
    if mode == LeaderboardResetMode.WEEKLY:
        return WEEKDAY_NAMES[anchor]
    if mode == LeaderboardResetMode.MONTHLY:
        return f"jour {anchor} du mois"
    return f"jour {anchor} de l'année"
