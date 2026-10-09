"""Conversations and messages.

A conversation owns an ordered list of messages. `message_count` is
denormalised so the sidebar can render without counting rows, and
`last_message_at` drives the "recent threads" ordering.

STEP 6 adds the AI provenance columns to `messages` (`status`, `model`,
`provider`, the token counts and `latency_ms`) plus `ai_usage_events`, which
records one row per model request for the admin usage surface and the future
cost dashboard. The columns are nullable wherever the provider may not report a
value: NULL means "unknown", which is deliberately distinct from zero.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
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

    # ── AI provenance (STEP 6) ────────────────────────────────────────
    # Terminal state of a generated turn: 'streaming' | 'completed' | 'failed'
    # | 'cancelled'. A user message is always 'completed' once persisted; the
    # distinction matters only for assistant turns, where a failed or cancelled
    # generation must never masquerade as a successful one.
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="completed", server_default="completed"
    )
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # The standardised error code when `status` is not 'completed'. Safe to
    # show: it comes from the closed vocabulary in `app.ai.errors`.
    error_code: Mapped[str | None] = mapped_column(String(48), nullable=True)
    # Idempotency key. A client that retries an ambiguous network failure sends
    # the same value and receives the existing turn rather than a second one.
    # Nullable so every pre-STEP-6 row and any keyless request stays valid.
    idempotency_key: Mapped[str | None] = mapped_column(
        String(80), nullable=True, index=True
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")

    __table_args__ = (
        UniqueConstraint("conversation_id", "position", name="uq_messages_thread_pos"),
    )


class AIUsageEvent(Base, TimestampMixin):
    """One row per model request.

    The audit and cost spine for STEP 6: it records *who* spent *what* on which
    model, without ever storing prompt or response content. Deliberately holds
    no provider credentials and no message text, so it can be surfaced to
    administrators without exposing private conversations.

    `user_id`/`conversation_id` are plain indexed strings rather than foreign
    keys: a usage record is an accounting fact and should survive the deletion
    of the conversation it describes, exactly as `auth_events` survives an
    account deletion.
    """

    __tablename__ = "ai_usage_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    conversation_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    message_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    # 'completed' | 'failed' | 'cancelled'
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    error_code: Mapped[str | None] = mapped_column(String(48), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Time to first streamed token, when it was observed. NULL otherwise.
    time_to_first_token_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Cost foundation. NULL unless the deployment configured real pricing.
    estimated_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    pricing_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    request_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    request_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_ai_usage_user_time", "user_id", "request_started_at"),
        Index("ix_ai_usage_status_time", "status", "request_started_at"),
    )