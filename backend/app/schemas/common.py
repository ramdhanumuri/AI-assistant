"""Shared schema primitives.

The API's wire format is the contract the frontend already speaks: the
TypeScript types in `src/types/index.ts`. So responses use the same field
names the UI reads (`mode`, `threads`, `calls`, `items`, `learned`, `at`) and
timestamps that feed `formatRelative` are epoch milliseconds, because that
helper does arithmetic on a number rather than parsing a date string.

Requests accept both the frontend spelling and the older `modeId`/`projectId`
camelCase variant via `AliasChoices`, so a client written against either
generation of the contract keeps working.
"""

from datetime import datetime, timezone
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer
from pydantic.alias_generators import to_camel

T = TypeVar("T")


class APIModel(BaseModel):
    """Base for every request/response body."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        extra="forbid",
    )


class ORMModel(APIModel):
    """Response model read straight off an ORM instance."""


def _epoch_ms(value: datetime) -> int:
    """Serialise a timestamp the way `formatRelative` expects to receive it."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return int(value.timestamp() * 1000)


def _optional_epoch_ms(value: datetime | None) -> int | None:
    return None if value is None else _epoch_ms(value)


def _relative_label(value: datetime) -> str:
    """Render a timestamp as the relative wording the UI displays.

    Mirrors `formatRelative` in `src/lib/utils.ts` for the sub-week range, then
    continues into weeks and months: the UI prints these fields verbatim, and a
    memory learned two months ago reads better as "2 months ago" than as a bare
    calendar date. The subdivision is coarse on purpose — these labels describe
    a knowledge index's freshness, not a precise event time.
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    seconds = max(0.0, (datetime.now(timezone.utc) - value).total_seconds())
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{int(seconds // 60)} min ago"
    if seconds < 86_400:
        return f"{int(seconds // 3600)} hr ago"
    days = int(seconds // 86_400)
    if days < 7:
        return f"{days} d ago"

    def _plural(count: int, unit: str) -> str:
        return f"{count} {unit}{'' if count == 1 else 's'} ago"

    if days < 30:
        return _plural(days // 7, "week")
    if days < 365:
        return _plural(days // 30, "month")
    return _plural(days // 365, "year")


def _optional_relative_label(value: datetime | None) -> str | None:
    return None if value is None else _relative_label(value)


# The UI's `formatRelative(ts: number)` does arithmetic on a number, so
# timestamps cross the wire as epoch milliseconds rather than ISO strings.
# SQLite drops tzinfo on round-trip, so UTC is re-attached here instead of
# trusting the stored value to be timezone-aware.
EpochMillis = Annotated[datetime, PlainSerializer(_epoch_ms, return_type=int)]
OptionalEpochMillis = Annotated[
    datetime | None, PlainSerializer(_optional_epoch_ms, return_type=int | None)
]
# For fields the UI prints verbatim as text (activity `at`, knowledge `updated`).
RelativeLabel = Annotated[datetime, PlainSerializer(_relative_label, return_type=str)]
OptionalRelativeLabel = Annotated[
    datetime | None,
    PlainSerializer(_optional_relative_label, return_type=str | None),
]


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int = Field(description="Total rows matching the query, ignoring paging.")
    limit: int
    offset: int


class HealthResponse(APIModel):
    status: str
    app: str
    env: str
    database: str
    version: str