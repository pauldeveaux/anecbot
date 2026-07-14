from dataclasses import dataclass
from typing import ClassVar

from anecbot.models.base import Model


@dataclass
class Anecdote(Model):
    """Submitted anecdote with state tracking."""

    _table: ClassVar[str] = "anecdotes"
    _pk: ClassVar[tuple[str, ...]] = ("id",)

    id: int = 0
    guild_id: int = 0
    author_id: int = 0
    target_id: int = 0
    content: str = ""
    state: str = "PENDING"
    created_at: str = ""
    published_at: str | None = None
    anecdote_message_id: int | None = None
