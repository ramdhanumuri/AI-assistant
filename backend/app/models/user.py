"""Identity, credentials, sessions and the authentication audit trail.

One `users` table, not an `auth_users`/`users` pair: the account *is* the user,
so splitting it would only add a join and a place for the two rows to drift.
`owner_id` on `memory_records` was already reserved for exactly this table
(MODULE 2 left it nullable for that reason) and `conversations` gains the same
column here.

`auth_sessions` holds one row per refresh token, storing only its SHA-256
digest. Rotation, revocation and "sign out everywhere" are therefore ordinary
row updates, and a leaked database does not hand over usable tokens.

`auth_events` is a separate table rather than a reuse of `activity_events`:
that feed is user-visible product telemetry, while these are security records
that must be tamper-evident and must survive the deletion of the account they
describe — so `user_id` is a plain indexed column with no foreign key.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UTCDateTime

ROLE_USER = "user"
ROLE_ADMIN = "admin"
ROLES = (ROLE_USER, ROLE_ADMIN)

# Event vocabulary. Kept as constants so a typo cannot invent a new event type
# that no dashboard or alert would ever match.
EVENT_REGISTERED = "registered"
EVENT_LOGIN_SUCCESS = "login_success"
EVENT_LOGIN_FAILURE = "login_failure"
EVENT_LOGIN_LOCKED = "login_locked"
EVENT_LOGOUT = "logout"
EVENT_TOKEN_REFRESHED = "token_refreshed"
EVENT_TOKEN_REUSE_DETECTED = "token_reuse_detected"
EVENT_PASSWORD_CHANGED = "password_changed"
EVENT_PASSWORD_RESET_REQUESTED = "password_reset_requested"
EVENT_PASSWORD_RESET_COMPLETED = "password_reset_completed"
EVENT_ACCOUNT_DEACTIVATED = "account_deactivated"
EVENT_ACCOUNT_REACTIVATED = "account_reactivated"
EVENT_ROLE_CHANGED = "role_changed"
EVENT_PROFILE_UPDATED = "profile_updated"
EVENT_RATE_LIMITED = "rate_limited"
EVENT_AUTHZ_DENIED = "authorization_denied"


def new_id() -> str:
    """Opaque primary key.

    UUID4 rather than a sequence so a user id is not enumerable and does not
    leak registration order through the API.
    """
    return str(uuid4())


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Stored lowercased and trimmed; `email_normalise` in the service layer is
    # the only writer. The unique index is what actually prevents duplicates —
    # a check-then-insert alone would race.
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # Server-owned. Never accepted from a request body; see UserService.
    role: Mapped[str] = mapped_column(String(16), nullable=False, default=ROLE_USER, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime, nullable=True
    )
    # Throttling counters live on the row so a lockout survives a process
    # restart and applies across workers.
    failed_login_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(
        UTCDateTime, nullable=True
    )

    preferences: Mapped["UserPreferences | None"] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    sessions: Mapped[list["AuthSession"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (Index("ix_users_role_active", "role", "is_active"),)

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN


class UserPreferences(Base, TimestampMixin):
    """Per-user settings mirroring the frontend's `Settings` shape.

    Server-side so preferences follow the account across devices, which is what
    the product promises; the client keeps its own copy only as a render cache.
    """

    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    ambient_light: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    particles: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    reduce_motion: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    streaming: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    memory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    citations: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    soundscape: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # 'comfortable' | 'compact'
    density: Mapped[str] = mapped_column(String(16), nullable=False, default="comfortable")

    user: Mapped[User] = relationship(back_populates="preferences")


class AuthSession(Base, TimestampMixin):
    """One refresh token, identified by the digest of the token itself.

    The access token carries this row's id (`sid`), so a single lookup both
    validates the session and lets a revoked session reject an otherwise
    perfectly signed access token.
    """

    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(400), nullable=True)
    # HMAC digest, not the address itself — see `hash_identifier`.
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    user: Mapped[User] = relationship(back_populates="sessions")

    __table_args__ = (Index("ix_auth_sessions_user_active", "user_id", "revoked_at"),)

    def is_usable(self, now: datetime) -> bool:
        return self.revoked_at is None and self.expires_at > now


class PasswordResetToken(Base, TimestampMixin):
    """Single-use, short-lived password-reset token (digest only)."""

    __tablename__ = "password_reset_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, index=True)
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class AuthEvent(Base, TimestampMixin):
    """Append-only authentication audit record.

    Deliberately stores no password, no token, no reset link and no raw
    identifier — only a keyed digest of the email/address so repeated attempts
    can be correlated without the log itself becoming a credential store.
    """

    __tablename__ = "auth_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    # 'success' | 'failure' | 'denied'
    outcome: Mapped[str] = mapped_column(String(16), nullable=False, default="success")
    email_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(400), nullable=True)
    # Short, non-sensitive context ("password policy", "expired session").
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, index=True
    )

    __table_args__ = (Index("ix_auth_events_type_time", "event_type", "occurred_at"),)
