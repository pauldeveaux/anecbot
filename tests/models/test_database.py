import tempfile
from pathlib import Path
from typing import Any

import aiosqlite
import pytest

from anecbot.models.database import close_db, init_db, run_migrations


async def fetchall(db: aiosqlite.Connection, sql: str) -> list[Any]:
    """Execute a query and return all rows as a list."""
    async with db.execute(sql) as cursor:
        return list(await cursor.fetchall())


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
async def test_fresh_db_applies_all_migrations(sample_migrations):
    """Apply all migrations on a fresh database and verify final state."""
    db = await aiosqlite.connect(":memory:")
    try:
        await run_migrations(db, sample_migrations)

        version = await fetchall(db, "SELECT version FROM schema_version")
        assert version[0][0] == 2

        tables = await fetchall(
            db, "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        table_names = [t[0] for t in tables]
        assert "foo" in table_names
        assert "bar" in table_names
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_migrations_are_idempotent(sample_migrations):
    """Run migrations twice and verify the result is identical."""
    db = await aiosqlite.connect(":memory:")
    try:
        await run_migrations(db, sample_migrations)
        await run_migrations(db, sample_migrations)

        version = await fetchall(db, "SELECT version FROM schema_version")
        assert version[0][0] == 2

        tables = await fetchall(
            db, "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        table_names = [t[0] for t in tables]
        assert "foo" in table_names
        assert "bar" in table_names
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_migrations_apply_in_order(migrations_dir):
    """Apply migrations incrementally and verify ordering is respected."""
    migrations_dir.mkdir()

    (migrations_dir / "0001_create_items.sql").write_text(
        "CREATE TABLE items (id INTEGER PRIMARY KEY);"
    )

    db = await aiosqlite.connect(":memory:")
    try:
        await run_migrations(db, migrations_dir)

        version = await fetchall(db, "SELECT version FROM schema_version")
        assert version[0][0] == 1

        (migrations_dir / "0002_add_column.sql").write_text(
            "ALTER TABLE items ADD COLUMN name TEXT;"
        )

        await run_migrations(db, migrations_dir)

        version = await fetchall(db, "SELECT version FROM schema_version")
        assert version[0][0] == 2

        columns = await fetchall(db, "PRAGMA table_info(items)")
        column_names = [c[1] for c in columns]
        assert "name" in column_names
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_non_sql_files_are_ignored(migrations_dir):
    """Verify that non-SQL files in the migrations directory are skipped."""
    migrations_dir.mkdir()

    (migrations_dir / "0001_create_foo.sql").write_text(
        "CREATE TABLE foo (id INTEGER PRIMARY KEY);"
    )
    (migrations_dir / "README.md").write_text("This is not a migration.")
    (migrations_dir / "notes.txt").write_text("Ignore me.")

    db = await aiosqlite.connect(":memory:")
    try:
        await run_migrations(db, migrations_dir)

        version = await fetchall(db, "SELECT version FROM schema_version")
        assert version[0][0] == 1
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_init_db_creates_file_and_runs_migrations(monkeypatch):
    """Test init_db creates the file, enables WAL and foreign keys, and runs migrations."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "test.db")
        migrations_path = str(
            Path(__file__).resolve().parent.parent.parent / "migrations"
        )
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setenv("MIGRATIONS_DIR", migrations_path)
        db = await init_db()
        try:
            assert Path(db_path).exists()

            version = await fetchall(db, "SELECT version FROM schema_version")
            assert version[0][0] >= 1

            journal = await fetchall(db, "PRAGMA journal_mode")
            assert journal[0][0] == "wal"

            fk = await fetchall(db, "PRAGMA foreign_keys")
            assert fk[0][0] == 1
        finally:
            await close_db(db)
