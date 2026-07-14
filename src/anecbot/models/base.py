from dataclasses import dataclass, fields
from typing import ClassVar, Self

import aiosqlite


@dataclass
class Model:
    """Abstract base for all database models."""

    _table: ClassVar[str]
    _pk: ClassVar[tuple[str, ...]]

    @classmethod
    def _updatable_columns(cls) -> set[str]:
        """Return field names excluding primary key columns."""
        pk = set(cls._pk)
        return {f.name for f in fields(cls) if f.name not in pk}

    @classmethod
    def _from_row(cls, row: aiosqlite.Row) -> Self:
        """Build a model instance from a database row."""
        return cls(**dict(row))  # type: ignore[arg-type]

    @classmethod
    def _pk_where(cls) -> str:
        """Build WHERE clause for primary key columns."""
        return " AND ".join(f"{col} = ?" for col in cls._pk)

    @classmethod
    async def get(cls, db: aiosqlite.Connection, *pk_values) -> Self | None:
        """Fetch a row by primary key, return model instance or None."""
        sql = f"SELECT * FROM {cls._table} WHERE {cls._pk_where()}"
        db.row_factory = aiosqlite.Row
        async with db.execute(sql, pk_values) as cursor:
            row = await cursor.fetchone()
        db.row_factory = None
        return cls._from_row(row) if row else None

    @classmethod
    async def upsert(cls, db: aiosqlite.Connection, *pk_values, **kwargs) -> Self:
        """Insert or update a row, return full model instance."""
        updatable = cls._updatable_columns()
        for key in kwargs:
            if key not in updatable:
                raise ValueError(f"Unknown column: {key}")

        pk_dict = dict(zip(cls._pk, pk_values))

        if kwargs:
            set_clause = ", ".join(f"{col} = excluded.{col}" for col in kwargs)
            columns = (*pk_dict.keys(), *kwargs.keys())
            placeholders = ", ".join("?" for _ in columns)
            values = (*pk_dict.values(), *kwargs.values())
            sql = (
                f"INSERT INTO {cls._table} ({', '.join(columns)}) "
                f"VALUES ({placeholders}) "
                f"ON CONFLICT({', '.join(cls._pk)}) DO UPDATE SET {set_clause}"
            )
        else:
            columns = tuple(pk_dict.keys())
            placeholders = ", ".join("?" for _ in columns)
            values = tuple(pk_dict.values())
            sql = (
                f"INSERT INTO {cls._table} ({', '.join(columns)}) "
                f"VALUES ({placeholders}) "
                f"ON CONFLICT({', '.join(cls._pk)}) DO NOTHING"
            )

        await db.execute(sql, values)
        await db.commit()
        result = await cls.get(db, *pk_values)
        assert result is not None
        return result

    @classmethod
    async def delete(cls, db: aiosqlite.Connection, *pk_values) -> bool:
        """Delete a row by primary key, return True if row existed."""
        sql = f"DELETE FROM {cls._table} WHERE {cls._pk_where()}"
        cursor = await db.execute(sql, pk_values)
        await db.commit()
        return cursor.rowcount > 0

    @classmethod
    async def list(cls, db: aiosqlite.Connection, **filters) -> list[Self]:
        """Fetch rows matching filters, return list of model instances."""
        if filters:
            updatable = cls._updatable_columns() | set(cls._pk)
            for key in filters:
                if key not in updatable:
                    raise ValueError(f"Unknown column: {key}")
            where = " AND ".join(f"{col} = ?" for col in filters)
            sql = f"SELECT * FROM {cls._table} WHERE {where}"
            values = tuple(filters.values())
        else:
            sql = f"SELECT * FROM {cls._table}"
            values = ()

        db.row_factory = aiosqlite.Row
        async with db.execute(sql, values) as cursor:
            rows = await cursor.fetchall()
        db.row_factory = None
        return [cls._from_row(row) for row in rows]
