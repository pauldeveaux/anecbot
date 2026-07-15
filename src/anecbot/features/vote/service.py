import aiosqlite

from anecbot.models.anecdote import Anecdote
from anecbot.models.enums import VoteResult
from anecbot.models.player import Player
from anecbot.models.vote import Vote


async def record_vote(
    db: aiosqlite.Connection, anecdote_id: int, voter_id: int, target_id: int
) -> VoteResult:
    """Record a vote for the anecdote, auto-registering the voter as a player if needed."""
    anecdote = await Anecdote.get(db, anecdote_id)
    if anecdote is None or anecdote.state != "PUBLISHED":
        return VoteResult.CLOSED

    existing = await Player.get(db, anecdote.guild_id, voter_id)
    if existing is None:
        await Player.upsert(
            db, anecdote.guild_id, voter_id, can_submit=0, can_be_target=0
        )

    await Vote.upsert(db, anecdote_id, voter_id, voted_for_id=target_id)
    return VoteResult.RECORDED
