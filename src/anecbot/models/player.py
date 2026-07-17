from dataclasses import dataclass
from typing import ClassVar

from anecbot.models.base import Model


@dataclass
class Player(Model):
    """Registered player in a guild."""

    _table: ClassVar[str] = "players"
    _pk: ClassVar[tuple[str, ...]] = ("guild_id", "user_id")

    guild_id: int = 0
    user_id: int = 0
    can_submit: int = 0
    can_be_target: int = 0
    alias: str | None = None
    suspended: int = 0
    banned_submit: int = 0
    banned_target: int = 0
    registered_at: str = ""
