from dataclasses import dataclass
from typing import ClassVar

from anecbot.models.base import Model


@dataclass
class Vote(Model):
    """Single vote on an anecdote MCQ."""

    _table: ClassVar[str] = "votes"
    _pk: ClassVar[tuple[str, ...]] = ("anecdote_id", "user_id")

    anecdote_id: int = 0
    user_id: int = 0
    voted_for_id: int = 0
    voted_at: str = ""
