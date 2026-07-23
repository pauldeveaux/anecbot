from dataclasses import dataclass
from typing import ClassVar

from anecbot.models.base import Model


@dataclass
class AnecdoteMedia(Model):
    """The image attached to an anecdote, if any."""

    _table: ClassVar[str] = "anecdote_media"
    _pk: ClassVar[tuple[str, ...]] = ("id",)

    id: int = 0
    anecdote_id: int = 0
    position: int = 0
    media_url: str = ""
    dm_channel_id: int | None = None
    dm_message_id: int | None = None
    attachment_index: int | None = None
