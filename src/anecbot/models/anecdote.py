from dataclasses import dataclass
from typing import ClassVar

from anecbot.models.base import Model
from anecbot.models.enums import AnecdoteState


@dataclass
class Anecdote(Model):
    """Submitted anecdote with state tracking.

    The target (and MCQ wrong choices) live in AnecdoteChoice rows, not on this model, so both
    roster-picked and free-text custom targets are represented identically once created.
    """

    _table: ClassVar[str] = "anecdotes"
    _pk: ClassVar[tuple[str, ...]] = ("id",)

    id: int = 0
    guild_id: int = 0
    author_id: int = 0
    content: str = ""
    state: AnecdoteState = AnecdoteState.PENDING
    created_at: str = ""
    published_at: str | None = None
    anecdote_message_id: int | None = None
    reveal_message_id: int | None = None
    points_awarded: int = 0
