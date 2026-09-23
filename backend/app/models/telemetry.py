"""Activity events and daily usage rollups for the dashboard."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class ActivityEvent(Base, TimestampMixin):
    __tablename__ = "activity_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    mode_id: Mapped[str] = mapped_column(
        ForeignKey("ai_modes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # A real timestamp, not a display string: the feed's relative wording
    # ("18 min ago") is derived at read time so it stays accurate as the row
    # ages, and the column remains sortable and queryable by later modules.
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class DailyUsage(Base, TimestampMixin):
    """One row per day: primary (conversations) and secondary (tools) counts."""

    __tablename__ = "daily_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    day: Mapped[date] = mapped_column(Date, nullable=False)
    label: Mapped[str] = mapped_column(String(8), nullable=False)
    value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    secondary: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (UniqueConstraint("day", name="uq_daily_usage_day"),)