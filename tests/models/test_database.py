import uuid
from pathlib import Path
from typing import Any, LiteralString, cast
from urllib.parse import quote

import psycopg
import pytest

from anecbot.models.database import close_db, init_db, run_migrations
from tests.conftest import TEST_DATABASE_URL


async def fetchall(db: psycopg.AsyncConnection, sql: str) -> list[Any]:
    """Execute a query and return all rows as a list."""
    cursor = await db.execute(cast(LiteralString, sql))
    return list(await cursor.fetchall())


async def table_names(db: psycopg.AsyncConnection) -> list[str]:
    """Return the names of every table in the current schema."""
    rows = await fetchall(
        db,
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = current_schema() ORDER BY table_name",
    )
    return [r[0] for r in rows]


async def column_names(db: psycopg.AsyncConnection, table: str) -> list[str]:
    """Return the column names of a table in the current schema."""
    rows = await fetchall(
        db,
        "SELECT column_name FROM information_schema.columns "
        f"WHERE table_schema = current_schema() AND table_name = '{table}' "
        "ORDER BY column_name",
    )
    return [r[0] for r in rows]


@pytest.fixture
def migrations_dir(tmp_path):
    """Return a temporary migrations directory path."""
    return tmp_path / "migrations"


@pytest.fixture
def sample_migrations(migrations_dir):
    """Create two sample migration files and return the directory."""
    migrations_dir.mkdir()

    (migrations_dir / "0001_create_foo.sql").write_text(
        "CREATE TABLE foo (id INTEGER PRIMARY KEY, name TEXT NOT NULL);"
    )
    (migrations_dir / "0002_create_bar.sql").write_text(
        "CREATE TABLE bar (id INTEGER PRIMARY KEY, foo_id INTEGER REFERENCES foo(id));"
    )
    return migrations_dir


@pytest.mark.asyncio
async def test_fresh_db_applies_all_migrations(db_connection, sample_migrations):
    """Apply all migrations on a fresh database and verify final state."""
    await run_migrations(db_connection, sample_migrations)

    version = await fetchall(db_connection, "SELECT version FROM schema_version")
    assert version[0][0] == 2

    tables = await table_names(db_connection)
    assert "foo" in tables
    assert "bar" in tables


@pytest.mark.asyncio
async def test_migrations_are_idempotent(db_connection, sample_migrations):
    """Run migrations twice and verify the result is identical."""
    await run_migrations(db_connection, sample_migrations)
    await run_migrations(db_connection, sample_migrations)

    version = await fetchall(db_connection, "SELECT version FROM schema_version")
    assert version[0][0] == 2

    tables = await table_names(db_connection)
    assert "foo" in tables
    assert "bar" in tables


@pytest.mark.asyncio
async def test_migrations_apply_in_order(db_connection, migrations_dir):
    """Apply migrations incrementally and verify ordering is respected."""
    migrations_dir.mkdir()

    (migrations_dir / "0001_create_items.sql").write_text(
        "CREATE TABLE items (id INTEGER PRIMARY KEY);"
    )

    await run_migrations(db_connection, migrations_dir)

    version = await fetchall(db_connection, "SELECT version FROM schema_version")
    assert version[0][0] == 1

    (migrations_dir / "0002_add_column.sql").write_text(
        "ALTER TABLE items ADD COLUMN name TEXT;"
    )

    await run_migrations(db_connection, migrations_dir)

    version = await fetchall(db_connection, "SELECT version FROM schema_version")
    assert version[0][0] == 2

    assert "name" in await column_names(db_connection, "items")


@pytest.mark.asyncio
async def test_non_sql_files_are_ignored(db_connection, migrations_dir):
    """Verify that non-SQL files in the migrations directory are skipped."""
    migrations_dir.mkdir()

    (migrations_dir / "0001_create_foo.sql").write_text(
        "CREATE TABLE foo (id INTEGER PRIMARY KEY);"
    )
    (migrations_dir / "README.md").write_text("This is not a migration.")
    (migrations_dir / "notes.txt").write_text("Ignore me.")

    await run_migrations(db_connection, migrations_dir)

    version = await fetchall(db_connection, "SELECT version FROM schema_version")
    assert version[0][0] == 1


@pytest.mark.asyncio
async def test_migration_failure_rolls_back_and_can_be_retried(
    db_connection, migrations_dir
):
    """A migration that fails partway leaves no trace, and a corrected retry applies cleanly."""
    migrations_dir.mkdir()
    (migrations_dir / "0001_broken.sql").write_text(
        "CREATE TABLE foo (id INTEGER PRIMARY KEY);\n"
        "INSERT INTO not_a_real_table (id) VALUES (1);"
    )

    with pytest.raises(Exception):
        await run_migrations(db_connection, migrations_dir)

    version = await fetchall(db_connection, "SELECT version FROM schema_version")
    assert version[0][0] == 0
    assert "foo" not in await table_names(db_connection)

    (migrations_dir / "0001_broken.sql").write_text(
        "CREATE TABLE foo (id INTEGER PRIMARY KEY);"
    )
    await run_migrations(db_connection, migrations_dir)

    version = await fetchall(db_connection, "SELECT version FROM schema_version")
    assert version[0][0] == 1
    assert "foo" in await table_names(db_connection)


@pytest.mark.asyncio
async def test_init_db_connects_and_runs_migrations():
    """init_db connects, applies the app's real migrations, and returns a usable connection."""
    schema = f"test_{uuid.uuid4().hex}"
    setup_conn = await psycopg.AsyncConnection.connect(
        TEST_DATABASE_URL, autocommit=False
    )
    await setup_conn.execute(cast(LiteralString, f'CREATE SCHEMA "{schema}"'))
    await setup_conn.commit()

    options = quote(f"-c search_path={schema}")
    scoped_url = f"{TEST_DATABASE_URL}?options={options}"
    migrations_path = Path(__file__).resolve().parent.parent.parent / "migrations"

    try:
        db = await init_db(scoped_url, migrations_path)
        try:
            version = await fetchall(db, "SELECT version FROM schema_version")
            assert version[0][0] >= 1
            assert "guilds" in await table_names(db)
        finally:
            await close_db(db)
    finally:
        await setup_conn.execute(cast(LiteralString, f'DROP SCHEMA "{schema}" CASCADE'))
        await setup_conn.commit()
        await setup_conn.close()
