"""Tool integrations — external systems the assistant can call."""

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class ToolIntegration(Base, TimestampMixin):
    __tablename__ = "tool_integrations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    connected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Free-text permission scope shown in the UI ('Read', 'Read / Write', …).
    permission: Mapped[str] = mapped_column(String(64), nullable=False)
    call_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)