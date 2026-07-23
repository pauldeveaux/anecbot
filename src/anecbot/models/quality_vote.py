from dataclasses import dataclass
from typing import ClassVar

from anecbot.models.base import Model


@dataclass
class QualityVote(Model):
    """Single 1-5 quality rating on an anecdote, separate from the guess-who MCQ vote."""

    _table: ClassVar[str] = "anecdote_quality_votes"
    _pk: ClassVar[tuple[str, ...]] = ("anecdote_id", "user_id")

    anecdote_id: int = 0
    user_id: int = 0
    rating: int = 0
    voted_at: str = ""
    guild_id: int = 0
