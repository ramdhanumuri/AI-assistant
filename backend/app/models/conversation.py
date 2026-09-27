"""Conversations and messages.

A conversation owns an ordered list of messages. `message_count` is
denormalised so the sidebar can render without counting rows, and
`last_message_at` drives the "recent threads" ordering.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    preview: Mapped[str] = mapped_column(Text, nullable=False, default="")
    mode_id: Mapped[str] = mapped_column(
        ForeignKey("ai_modes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # MODULE 4: the account that owns this thread. Nullable so the MODULE 2
    # demo rows remain valid; NULL is treated as "not owned by anyone" and is
    # therefore invisible to every authenticated user. New rows always carry an
    # owner. `ondelete=CASCADE` means deleting an account takes its threads
    # (and, transitively, their messages) with it.
    owner_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    mode: Mapped["AIMode"] = relationship(lazy="joined")  # noqa: F821
    project: Mapped["Project | None"] = relationship(  # noqa: F821
        back_populates="conversations", lazy="joined"
    )
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Message.position",
    )

    __table_args__ = (Index("ix_conversations_recent", "archived", "last_message_at"),)


class Message(Base, TimestampMixin):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Monotonic within a conversation; the unique constraint makes ordering
    # deterministic even when two messages share a timestamp.
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    mode_id: Mapped[str] = mapped_column(
        ForeignKey("ai_modes.id", ondelete="RESTRICT"), nullable=False
    )
    # Rich content blocks (text, code, table, insight, timeline, …) are stored
    # as JSON so the block vocabulary can grow without a migration each time.
    blocks: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    traces: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    voice: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")

    __table_args__ = (
        UniqueConstraint("conversation_id", "position", name="uq_messages_thread_pos"),
    )