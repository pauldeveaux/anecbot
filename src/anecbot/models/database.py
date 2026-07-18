import logging
import re
from pathlib import Path
from typing import LiteralString, cast

import psycopg

logger = logging.getLogger(__name__)


def _parse_migration_number(filename: str) -> int | None:
    """Extract the migration number from a filename like '0001_create_table.sql'."""
    match = re.match(r"^(\d+)_.*\.sql$", filename)
    return int(match.group(1)) if match else None


async def _ensure_schema_version_table(db: psycopg.AsyncConnection) -> None:
    """Create the schema_version table if it doesn't exist, initialize to version 0."""
    await db.execute(
        "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)"
    )
    cursor = await db.execute("SELECT version FROM schema_version")
    rows = await cursor.fetchall()
    if not rows:
        await db.execute("INSERT INTO schema_version (version) VALUES (0)")
    await db.commit()


async def _get_version(db: psycopg.AsyncConnection) -> int:
    """Return the current schema version number."""
    cursor = await db.execute("SELECT version FROM schema_version")
    rows = await cursor.fetchall()
    return int(rows[0][0])


async def run_migrations(db: psycopg.AsyncConnection, migrations_dir: Path) -> None:
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
        if migration_number is not None and migration_number <= current_version:
            continue

        logger.info("Applying migration %s", migration_file.name)
        sql = migration_file.read_text()
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        try:
            for statement in statements:
                await db.execute(cast(LiteralString, statement))
            await db.execute(
                "UPDATE schema_version SET version = %s", (migration_number,)
            )
        except BaseException:
            await db.rollback()
            raise
        else:
            await db.commit()

    final_version = await _get_version(db)
    logger.info("Database at version %d", final_version)


async def init_db(database_url: str, migrations_dir: Path) -> psycopg.AsyncConnection:
    """Open a PostgreSQL connection and run pending migrations."""
    db = await psycopg.AsyncConnection.connect(database_url, autocommit=False)
    await run_migrations(db, migrations_dir)
    return db


async def close_db(db: psycopg.AsyncConnection) -> None:
    """Close the database connection."""
    await db.close()
