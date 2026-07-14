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
