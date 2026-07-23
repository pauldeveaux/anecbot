from dataclasses import dataclass
from typing import ClassVar

from anecbot.models.base import Model


@dataclass
class ReleaseAnnouncement(Model):
    """Singleton row tracking the last release message announced to guilds."""

    _table: ClassVar[str] = "release_announcement"
    _pk: ClassVar[tuple[str, ...]] = ("id",)

    id: int = 1
    content_hash: str | None = None
    announced_at: str | None = None
