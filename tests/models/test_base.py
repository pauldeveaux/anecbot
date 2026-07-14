from dataclasses import dataclass
from typing import ClassVar

import aiosqlite
import pytest
import pytest_asyncio

from anecbot.models.base import Model


@dataclass
class Item(Model):
    """Test model with composite primary key."""

    _table: ClassVar[str] = "items"
    _pk: ClassVar[tuple[str, ...]] = ("group_id", "item_id")

    group_id: int = 0
    item_id: int = 0
    name: str = ""
    value: int = 0


CREATE_ITEMS_SQL = """
CREATE TABLE items (
    group_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    value INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (group_id, item_id)
);
"""


@pytest_asyncio.fixture
async def db():
    """Provide an in-memory database with items table."""
    conn = await aiosqlite.connect(":memory:")
    await conn.executescript(CREATE_ITEMS_SQL)
    yield conn
    await conn.close()


@pytest.mark.asyncio
async def test_get_returns_none_when_missing(db):
    """Model.get returns None for missing composite PK."""
    result = await Item.get(db, 1, 1)
    assert result is None


@pytest.mark.asyncio
async def test_upsert_creates_with_defaults(db):
    """Model.upsert creates a row with default values."""
    result = await Item.upsert(db, 1, 1)
    assert isinstance(result, Item)
    assert result.group_id == 1
    assert result.item_id == 1
    assert result.name == ""
    assert result.value == 0


@pytest.mark.asyncio
async def test_upsert_with_kwargs(db):
    """Model.upsert sets provided fields."""
    result = await Item.upsert(db, 1, 1, name="foo", value=42)
    assert result.name == "foo"
    assert result.value == 42


@pytest.mark.asyncio
async def test_upsert_updates_existing(db):
    """Model.upsert updates only provided fields on conflict."""
    await Item.upsert(db, 1, 1, name="foo", value=10)
    result = await Item.upsert(db, 1, 1, value=20)
    assert result.name == "foo"
    assert result.value == 20


@pytest.mark.asyncio
async def test_upsert_rejects_unknown_column(db):
    """Model.upsert raises ValueError for unknown columns."""
    with pytest.raises(ValueError, match="Unknown column"):
        await Item.upsert(db, 1, 1, bogus=99)


@pytest.mark.asyncio
async def test_delete_existing(db):
    """Model.delete returns True when row existed."""
    await Item.upsert(db, 1, 1, name="foo")
    assert await Item.delete(db, 1, 1) is True
    assert await Item.get(db, 1, 1) is None


@pytest.mark.asyncio
async def test_delete_missing(db):
    """Model.delete returns False when row didn't exist."""
    assert await Item.delete(db, 1, 1) is False


@pytest.mark.asyncio
async def test_list_all(db):
    """Model.list returns all rows when no filters."""
    await Item.upsert(db, 1, 1, name="a")
    await Item.upsert(db, 1, 2, name="b")
    await Item.upsert(db, 2, 1, name="c")
    result = await Item.list(db)
    assert len(result) == 3
    assert all(isinstance(r, Item) for r in result)


@pytest.mark.asyncio
async def test_list_with_filter(db):
    """Model.list filters by column value."""
    await Item.upsert(db, 1, 1, name="a")
    await Item.upsert(db, 1, 2, name="b")
    await Item.upsert(db, 2, 1, name="c")
    result = await Item.list(db, group_id=1)
    assert len(result) == 2
    assert all(r.group_id == 1 for r in result)


@pytest.mark.asyncio
async def test_list_empty(db):
    """Model.list returns empty list when no rows match."""
    result = await Item.list(db, group_id=999)
    assert result == []


@pytest.mark.asyncio
async def test_list_rejects_unknown_column(db):
    """Model.list raises ValueError for unknown filter columns."""
    with pytest.raises(ValueError, match="Unknown column"):
        await Item.list(db, bogus=1)
