from dataclasses import dataclass
from typing import ClassVar

from anecbot.models.base import Model
from anecbot.models.enums import LeaderboardResetMode, RevealMode


@dataclass
class Guild(Model):
    """Per-guild configuration."""

    _table: ClassVar[str] = "guilds"
    _pk: ClassVar[tuple[str, ...]] = ("guild_id",)

    guild_id: int = 0
    channel_id: int | None = None
    interval_days: int = 1
    publish_time: str = "15:00"
    days_off: str = ""
    reveal_mode: RevealMode = RevealMode.AFTER_PUBLISH
    reveal_interval_days: int = 1
    reveal_time: str = "13:30"
    leaderboard_reset_mode: LeaderboardResetMode = LeaderboardResetMode.NEVER
    leaderboard_reset_interval: int = 1
    leaderboard_reset_anchor: int | None = None
    daily_limit: int = 0
    started: int = 0
