from dataclasses import dataclass
from typing import ClassVar

from anecbot.models.base import Model


@dataclass
class LeaderboardEntry(Model):
    """Cumulative score for a user in a guild."""

    _table: ClassVar[str] = "leaderboard"
    _pk: ClassVar[tuple[str, ...]] = ("guild_id", "user_id")

    guild_id: int = 0
    user_id: int = 0
    points: int = 0


def rank_of(entries: list[LeaderboardEntry], user_id: int) -> int | None:
    """Return the user's 1-indexed rank among the entries, or None if they have no entry."""
    ranked = sorted(entries, key=lambda e: e.points, reverse=True)
    for rank, entry in enumerate(ranked, start=1):
        if entry.user_id == user_id:
            return rank
    return None
