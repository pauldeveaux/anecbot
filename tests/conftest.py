import asyncio
import os
import sys
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import LiteralString, cast

import psycopg
import pytest_asyncio

from anecbot.models.database import run_migrations

if sys.platform == "win32":
    # psycopg's async mode can't use Windows' default ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    os.environ.get(
        "DATABASE_URL", "postgresql://anecbot:anecbot@127.0.0.1:5432/anecbot"
    ),
)


@pytest_asyncio.fixture
async def db_connection() -> AsyncIterator[psycopg.AsyncConnection]:
    """Provide a Postgres connection scoped to a freshly created, isolated schema.

    Tests write through Model/repository code that commits mid-test, so isolation can't rely
    on a rolled-back transaction — each test instead gets its own throwaway schema, dropped at
    teardown.
    """
    schema = f"test_{uuid.uuid4().hex}"
    conn = await psycopg.AsyncConnection.connect(TEST_DATABASE_URL, autocommit=False)
    await conn.execute(cast(LiteralString, f'CREATE SCHEMA "{schema}"'))
    await conn.execute(cast(LiteralString, f'SET search_path TO "{schema}"'))
    await conn.commit()
    try:
        yield conn
    finally:
        # A test that intentionally triggers an IntegrityError leaves the transaction aborted;
        # roll back before DROP SCHEMA so teardown doesn't fail on top of it.
        await conn.rollback()
        await conn.execute(cast(LiteralString, f'DROP SCHEMA "{schema}" CASCADE'))
        await conn.commit()
        await conn.close()


@pytest_asyncio.fixture
async def db(
    db_connection: psycopg.AsyncConnection,
) -> psycopg.AsyncConnection:
    """Provide an isolated-schema connection with the app's migrations applied."""
    await run_migrations(db_connection, MIGRATIONS_DIR)
    return db_connection
