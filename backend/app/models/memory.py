"""Memory records — durable, scoped facts learned about the user."""

from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class MemoryRecord(Base, TimestampMixin):
    __tablename__ = "memory_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # When the fact was learned. A timestamp, not the "6 weeks ago" text the UI
    # shows, so recency stays accurate and MODULE 9 can decay or rank memories.
    learned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    # MODULE 4 will scope these per user; the column exists now so the
    # migration is additive rather than destructive.
    owner_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)