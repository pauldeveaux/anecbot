from statistics import mean

import psycopg

from anecbot.models.anecdote import Anecdote
from anecbot.models.enums import AnecdoteState, VoteResult
from anecbot.models.player import Player
from anecbot.models.quality_vote import QualityVote


async def record_quality_vote(
    db: psycopg.AsyncConnection, anecdote_id: int, voter_id: int, rating: int
) -> VoteResult:
    """Record a 1-5 quality rating for the anecdote, closing at the same time as the guess vote."""
    anecdote = await Anecdote.get(db, anecdote_id)
    if anecdote is None or anecdote.state != AnecdoteState.PUBLISHED:
        return VoteResult.CLOSED

    if voter_id == anecdote.author_id:
        return VoteResult.IS_AUTHOR

    existing = await Player.get(db, anecdote.guild_id, voter_id)
    if existing is None:
        await Player.upsert(
            db, anecdote.guild_id, voter_id, can_submit=0, can_be_target=0
        )

    await QualityVote.upsert(
        db, anecdote_id, voter_id, rating=rating, guild_id=anecdote.guild_id
    )
    return VoteResult.RECORDED


def quality_bonus(ratings: list[int]) -> int:
    """Return the author's bonus points from the average quality rating, 0 if none cast.

    Asymmetric bucket scale rewarding excellence more than it punishes weak anecdotes:
    [1, 1.5) -> -2, [1.5, 2.5) -> -1, [2.5, 3.5) -> 0, [3.5, 4.5) -> +2, [4.5, 5] -> +3.
    """
    if not ratings:
        return 0
    average = mean(ratings)
    if average < 1.5:
        return -2
    if average < 2.5:
        return -1
    if average < 3.5:
        return 0
    if average < 4.5:
        return 2
    return 3
