from dataclasses import dataclass
from typing import ClassVar

from anecbot.models.base import Model


@dataclass
class AnecdoteChoice(Model):
    """Custom-mode MCQ option (the target or one of its wrong choices) for an anecdote."""

    _table: ClassVar[str] = "anecdote_choices"
    _pk: ClassVar[tuple[str, ...]] = ("id",)

    id: int = 0
    anecdote_id: int = 0
    label: str = ""
    is_correct: int = 0
