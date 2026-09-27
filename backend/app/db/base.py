"""Declarative base and shared mixins.

Every table carries an integer primary key and created/updated timestamps so
later modules (audit, soft-delete, replication) have a consistent spine.
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """A timestamp column that is always timezone-aware when read back.

    SQLite has no native timezone type: it stores the wall clock and returns a
    **naive** datetime, so `stored > utcnow()` raises `TypeError` at the moment
    the value is compared in Python rather than in SQL. PostgreSQL returns an
    aware value, so the same code would pass there and fail in tests and local
    development — the worst possible split.

    Re-attaching UTC on load makes the type behave identically on both engines.
    Values are always written as UTC (`utcnow`), so re-attaching is a
    restoration of information SQLite dropped, not a guess.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(
        self, value: datetime | None, dialect: Any
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_result_value(
        self, value: datetime | None, dialect: Any
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


def as_utc(value: datetime | None) -> datetime | None:
    """Coerce a possibly-naive datetime to UTC.

    Needed for values that arrive without going through `UTCDateTime` — a
    hand-built object in a test, or a value read from a legacy column.
    """
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class Base(DeclarativeBase):
    """Root declarative base for all ORM models."""


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class IdMixin:
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)