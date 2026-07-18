import math
import random
from datetime import datetime

import psycopg

from anecbot.features.selector.repository import (
    count_total_published,
    get_author_publish_distances_bulk,
)
from anecbot.models.anecdote import Anecdote
from anecbot.models.enums import AnecdoteState

AUTHOR_TAU_FRACTION = 0.1


def compute_age_weight(created_at: datetime, now: datetime) -> float:
    """Return a soft weight favoring anecdotes that have waited longer in the queue."""
    days_waiting = max((now - created_at).days, 0)
    return math.sqrt(days_waiting + 1)


def compute_author_weight(distances: list[int], tau: float) -> float:
    """Return a weight penalizing an author published frequently/recently, cumulative per anecdote."""
    activity = sum(math.exp(-distance / tau) for distance in distances)
    return 1 / (1 + activity)


async def _pending_weights(
    db: psycopg.AsyncConnection, guild_id: int, anecdotes: list[Anecdote], now: datetime
) -> dict[int, float]:
    """Return {anecdote_id: weight} for the given (already-fetched) PENDING anecdotes."""
    total_published = await count_total_published(db, guild_id)
    tau = max(1.0, total_published * AUTHOR_TAU_FRACTION)

    author_ids = list({anecdote.author_id for anecdote in anecdotes})
    distances_by_author = await get_author_publish_distances_bulk(
        db, guild_id, author_ids
    )

    weights: dict[int, float] = {}
    for anecdote in anecdotes:
        age_weight = compute_age_weight(
            datetime.fromisoformat(anecdote.created_at), now
        )
        distances = distances_by_author[anecdote.author_id]
        weights[anecdote.id] = age_weight * compute_author_weight(distances, tau)
    return weights


async def select_pending_anecdote(
    db: psycopg.AsyncConnection,
    guild_id: int,
    now: datetime,
    rng: random.Random | None = None,
) -> Anecdote | None:
    """Weighted-random pick among PENDING anecdotes, or None if the queue is empty."""
    anecdotes = await Anecdote.list(db, guild_id=guild_id, state=AnecdoteState.PENDING)
    if not anecdotes:
        return None

    weights_by_id = await _pending_weights(db, guild_id, anecdotes, now)
    weights = [weights_by_id[a.id] for a in anecdotes]

    rng = rng or random.Random()
    return rng.choices(anecdotes, weights=weights, k=1)[0]


async def compute_selection_probabilities(
    db: psycopg.AsyncConnection, guild_id: int, now: datetime
) -> dict[int, float]:
    """Return each PENDING anecdote's normalized selection probability (weight / total weight)."""
    anecdotes = await Anecdote.list(db, guild_id=guild_id, state=AnecdoteState.PENDING)
    if not anecdotes:
        return {}
    weights_by_id = await _pending_weights(db, guild_id, anecdotes, now)
    total_weight = sum(weights_by_id.values())
    return {aid: weight / total_weight for aid, weight in weights_by_id.items()}
