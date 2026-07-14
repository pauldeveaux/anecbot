from dataclasses import dataclass
from typing import ClassVar

from anecbot.models.base import Model


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
    reveal_interval_days: int = 1
    reveal_time: str = "13:30"
    leaderboard_reset_days: int = 0
    daily_limit: int = 0
    started: int = 0
