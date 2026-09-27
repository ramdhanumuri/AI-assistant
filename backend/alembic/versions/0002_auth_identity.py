"""add identity, sessions and the authentication audit trail

Revision ID: 0002_auth_identity
Revises: 0001_module2_core
Create Date: 2026-09-24 00:00:00.000000

Additive only: no MODULE 2/3 table is dropped, retyped or renamed. The single
change to an existing table is `conversations.owner_id`, which is nullable so
the MODULE 2 demo rows stay valid and no backfill is required.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0002_auth_identity"
down_revision: str | None = "0001_module2_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── Identity ──────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("avatar_url", sa.String(length=512), nullable=True),
        sa.Column("email_verified", sa.Boolean(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_login_count", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_users_email"), ["email"], unique=True)
        batch_op.create_index(batch_op.f("ix_users_role"), ["role"], unique=False)
        batch_op.create_index(batch_op.f("ix_users_is_active"), ["is_active"], unique=False)
        batch_op.create_index("ix_users_role_active", ["role", "is_active"], unique=False)

    op.create_table(
        "user_preferences",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("ambient_light", sa.Boolean(), nullable=False),
        sa.Column("particles", sa.Boolean(), nullable=False),
        sa.Column("reduce_motion", sa.Boolean(), nullable=False),
        sa.Column("streaming", sa.Boolean(), nullable=False),
        sa.Column("memory", sa.Boolean(), nullable=False),
        sa.Column("citations", sa.Boolean(), nullable=False),
        sa.Column("soundscape", sa.Boolean(), nullable=False),
        sa.Column("density", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_user_preferences_user_id"),
    )

    # ── Sessions and reset tokens (digests only) ──────────────────────
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_agent", sa.String(length=400), nullable=True),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("auth_sessions", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_auth_sessions_user_id"), ["user_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_auth_sessions_token_hash"), ["token_hash"], unique=True)
        batch_op.create_index(batch_op.f("ix_auth_sessions_expires_at"), ["expires_at"], unique=False)
        batch_op.create_index(
            "ix_auth_sessions_user_active", ["user_id", "revoked_at"], unique=False
        )

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("password_reset_tokens", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_password_reset_tokens_user_id"), ["user_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_password_reset_tokens_token_hash"), ["token_hash"], unique=True
        )
        batch_op.create_index(
            batch_op.f("ix_password_reset_tokens_expires_at"), ["expires_at"], unique=False
        )

    # ── Audit trail ───────────────────────────────────────────────────
    # No foreign key on `user_id` on purpose: the security record must outlive
    # the account it describes.
    op.create_table(
        "auth_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", sa.String(length=48), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("email_hash", sa.String(length=64), nullable=True),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=400), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("auth_events", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_auth_events_user_id"), ["user_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_auth_events_event_type"), ["event_type"], unique=False)
        batch_op.create_index(batch_op.f("ix_auth_events_email_hash"), ["email_hash"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_auth_events_occurred_at"), ["occurred_at"], unique=False
        )
        batch_op.create_index(
            "ix_auth_events_type_time", ["event_type", "occurred_at"], unique=False
        )

    # ── Ownership on existing content ─────────────────────────────────
    with op.batch_alter_table("conversations", schema=None) as batch_op:
        batch_op.add_column(sa.Column("owner_id", sa.String(length=36), nullable=True))
        batch_op.create_index(batch_op.f("ix_conversations_owner_id"), ["owner_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_conversations_owner_id", "users", ["owner_id"], ["id"], ondelete="CASCADE"
        )


def downgrade() -> None:
    with op.batch_alter_table("conversations", schema=None) as batch_op:
        batch_op.drop_constraint("fk_conversations_owner_id", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_conversations_owner_id"))
        batch_op.drop_column("owner_id")

    with op.batch_alter_table("auth_events", schema=None) as batch_op:
        batch_op.drop_index("ix_auth_events_type_time")
        batch_op.drop_index(batch_op.f("ix_auth_events_occurred_at"))
        batch_op.drop_index(batch_op.f("ix_auth_events_email_hash"))
        batch_op.drop_index(batch_op.f("ix_auth_events_event_type"))
        batch_op.drop_index(batch_op.f("ix_auth_events_user_id"))

    op.drop_table("auth_events")

    with op.batch_alter_table("password_reset_tokens", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_password_reset_tokens_expires_at"))
        batch_op.drop_index(batch_op.f("ix_password_reset_tokens_token_hash"))
        batch_op.drop_index(batch_op.f("ix_password_reset_tokens_user_id"))

    op.drop_table("password_reset_tokens")

    with op.batch_alter_table("auth_sessions", schema=None) as batch_op:
        batch_op.drop_index("ix_auth_sessions_user_active")
        batch_op.drop_index(batch_op.f("ix_auth_sessions_expires_at"))
        batch_op.drop_index(batch_op.f("ix_auth_sessions_token_hash"))
        batch_op.drop_index(batch_op.f("ix_auth_sessions_user_id"))

    op.drop_table("auth_sessions")
    op.drop_table("user_preferences")

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index("ix_users_role_active")
        batch_op.drop_index(batch_op.f("ix_users_is_active"))
        batch_op.drop_index(batch_op.f("ix_users_role"))
        batch_op.drop_index(batch_op.f("ix_users_email"))

    op.drop_table("users")
