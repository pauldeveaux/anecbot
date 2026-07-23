import pytest
import pytest_asyncio

from anecbot.features.quality_vote.service import quality_bonus, record_quality_vote
from anecbot.models.anecdote import Anecdote
from anecbot.models.enums import VoteResult
from anecbot.models.guild import Guild
from anecbot.models.player import Player
from anecbot.models.quality_vote import QualityVote

GUILD_ID = 100
AUTHOR_ID = 1
TARGET_ID = 2
VOTER_ID = 3


@pytest_asyncio.fixture
async def anecdote(db):
    """Create a guild, author, target, and a PUBLISHED anecdote."""
    await Guild.upsert(db, GUILD_ID)
    await Player.upsert(db, GUILD_ID, AUTHOR_ID, can_submit=1)
    await Player.upsert(db, GUILD_ID, TARGET_ID, can_be_target=1)
    created = await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, content="x"
    )
    return await Anecdote.update(db, created.id, state="PUBLISHED")


@pytest.mark.asyncio
async def test_record_quality_vote_saves_rating(db, anecdote):
    """A rating on a PUBLISHED anecdote is saved and RECORDED is returned."""
    result = await record_quality_vote(db, anecdote.id, VOTER_ID, 4)

    assert result == VoteResult.RECORDED
    vote = await QualityVote.get(db, anecdote.id, VOTER_ID)
    assert vote is not None
    assert vote.rating == 4


@pytest.mark.asyncio
async def test_record_quality_vote_auto_registers_unregistered_voter(db, anecdote):
    """An unregistered voter gets a bare Player row (no submit/target rights)."""
    assert await Player.get(db, GUILD_ID, VOTER_ID) is None

    await record_quality_vote(db, anecdote.id, VOTER_ID, 4)

    player = await Player.get(db, GUILD_ID, VOTER_ID)
    assert player is not None
    assert player.can_submit == 0
    assert player.can_be_target == 0


@pytest.mark.asyncio
async def test_record_quality_vote_does_not_reregister_existing_player(db, anecdote):
    """An already-registered voter's existing flags are left untouched."""
    await Player.upsert(db, GUILD_ID, VOTER_ID, can_submit=1)

    await record_quality_vote(db, anecdote.id, VOTER_ID, 4)

    player = await Player.get(db, GUILD_ID, VOTER_ID)
    assert player is not None
    assert player.can_submit == 1


@pytest.mark.asyncio
async def test_record_quality_vote_overwrites_previous_rating(db, anecdote):
    """Rating again changes the recorded rating rather than erroring."""
    await record_quality_vote(db, anecdote.id, VOTER_ID, 2)
    result = await record_quality_vote(db, anecdote.id, VOTER_ID, 5)

    assert result == VoteResult.RECORDED
    vote = await QualityVote.get(db, anecdote.id, VOTER_ID)
    assert vote is not None
    assert vote.rating == 5


@pytest.mark.asyncio
async def test_record_quality_vote_rejected_when_not_published(db):
    """Rating a PENDING (not yet published) anecdote is rejected."""
    await Guild.upsert(db, GUILD_ID)
    await Player.upsert(db, GUILD_ID, AUTHOR_ID, can_submit=1)
    pending = await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, content="x"
    )

    result = await record_quality_vote(db, pending.id, VOTER_ID, 4)

    assert result == VoteResult.CLOSED
    assert await QualityVote.get(db, pending.id, VOTER_ID) is None


@pytest.mark.asyncio
async def test_record_quality_vote_rejected_when_revealed(db, anecdote):
    """Rating a REVEALED anecdote is rejected — closes at the same time as the guess vote."""
    await Anecdote.update(db, anecdote.id, state="REVEALED")

    result = await record_quality_vote(db, anecdote.id, VOTER_ID, 4)

    assert result == VoteResult.CLOSED
    assert await QualityVote.get(db, anecdote.id, VOTER_ID) is None


@pytest.mark.asyncio
async def test_record_quality_vote_rejected_when_anecdote_missing(db):
    """Rating a nonexistent anecdote is rejected."""
    result = await record_quality_vote(db, 999, VOTER_ID, 4)

    assert result == VoteResult.CLOSED


@pytest.mark.asyncio
async def test_record_quality_vote_rejected_when_voter_is_author(db, anecdote):
    """The anecdote's author can't rate their own anecdote."""
    result = await record_quality_vote(db, anecdote.id, AUTHOR_ID, 5)

    assert result == VoteResult.IS_AUTHOR
    assert await QualityVote.get(db, anecdote.id, AUTHOR_ID) is None


@pytest.mark.parametrize(
    ("ratings", "expected"),
    [
        ([], 0),
        ([1], -2),
        ([1, 2], -1),  # average 1.5 falls in the [1.5, 2.5) bucket
        ([2], -1),
        ([3], 0),
        ([2, 4], 0),  # average 3
        ([3, 4], 2),  # average 3.5 falls in the [3.5, 4.5) bucket, not the neutral one
        ([4], 2),
        ([5], 3),
        ([4, 5], 3),  # average 4.5
    ],
)
def test_quality_bonus_buckets(ratings, expected):
    """quality_bonus follows the asymmetric bucket scale."""
    assert quality_bonus(ratings) == expected
