import logging
import os
import re
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)


def _parse_migration_number(filename: str) -> int | None:
    """Extract the migration number from a filename like '0001_create_table.sql'."""
    match = re.match(r"^(\d+)_.*\.sql$", filename)
    return int(match.group(1)) if match else None


async def _ensure_schema_version_table(db: aiosqlite.Connection) -> None:
    """Create the schema_version table if it doesn't exist, initialize to version 0."""
    await db.execute(
        "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)"
    )
    row = await db.execute_fetchall("SELECT version FROM schema_version")
    if not row:
        await db.execute("INSERT INTO schema_version (version) VALUES (0)")
    await db.commit()


async def _get_version(db: aiosqlite.Connection) -> int:
    """Return the current schema version number."""
    row = await db.execute_fetchall("SELECT version FROM schema_version")
    return row[0][0]


async def run_migrations(db: aiosqlite.Connection, migrations_dir: Path) -> None:
    """Apply pending SQL migrations from migrations_dir in order."""
    await _ensure_schema_version_table(db)
    current_version = await _get_version(db)

    migration_files = sorted(
        f
        for f in migrations_dir.iterdir()
        if f.is_file() and _parse_migration_number(f.name) is not None
    )

    for migration_file in migration_files:
        migration_number = _parse_migration_number(migration_file.name)
        if migration_number <= current_version:
            continue

        logger.info("Applying migration %s", migration_file.name)
        sql = migration_file.read_text()
        await db.executescript(sql)
        await db.execute("UPDATE schema_version SET version = ?", (migration_number,))
        await db.commit()

    final_version = await _get_version(db)
    logger.info("Database at version %d", final_version)


async def init_db() -> aiosqlite.Connection:
    """Open a SQLite connection with WAL mode, foreign keys, and run pending migrations."""
    db_path = os.environ.get("DB_PATH", "data/anecbot.db")
    migrations_dir = Path(os.environ.get("MIGRATIONS_DIR", "migrations"))

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(db_path)
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    await run_migrations(db, migrations_dir)
    return db


async def close_db(db: aiosqlite.Connection) -> None:
    """Close the database connection."""
    await db.close()
