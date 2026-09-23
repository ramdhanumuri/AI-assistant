"""Knowledge sources — the assistant's indexed context layer."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class KnowledgeSource(Base, TimestampMixin):
    __tablename__ = "knowledge_sources"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # document | repository | dataset | feed
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # indexed | indexing | paused
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # The connector's last successful sync. Stored as a timestamp (not the
    # "4 min ago" text the UI shows) so later modules can re-index on staleness
    # and the column stays sortable; the relative wording is derived on read.
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)