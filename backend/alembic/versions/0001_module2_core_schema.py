"""create module 2 core schema

Revision ID: 0001_module2_core
Revises: 
Create Date: 2026-09-18 16:09:20.782621
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '0001_module2_core'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('ai_modes',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('label', sa.String(length=64), nullable=False),
    sa.Column('caption', sa.String(length=128), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('aura', sa.String(length=32), nullable=False),
    sa.Column('glyph', sa.String(length=8), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('daily_usage',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('day', sa.Date(), nullable=False),
    sa.Column('label', sa.String(length=8), nullable=False),
    sa.Column('value', sa.Integer(), nullable=False),
    sa.Column('secondary', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('day', name='uq_daily_usage_day')
    )
    op.create_table('knowledge_sources',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('kind', sa.String(length=32), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('item_count', sa.Integer(), nullable=False),
    sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('knowledge_sources', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_knowledge_sources_kind'), ['kind'], unique=False)
        batch_op.create_index(batch_op.f('ix_knowledge_sources_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_knowledge_sources_last_synced_at'), ['last_synced_at'], unique=False)

    op.create_table('memory_records',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('statement', sa.Text(), nullable=False),
    sa.Column('scope', sa.String(length=64), nullable=False),
    sa.Column('confidence', sa.Float(), nullable=False),
    sa.Column('learned_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('owner_id', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('memory_records', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_memory_records_owner_id'), ['owner_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_memory_records_scope'), ['scope'], unique=False)
        batch_op.create_index(batch_op.f('ix_memory_records_learned_at'), ['learned_at'], unique=False)

    op.create_table('projects',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('brief', sa.Text(), nullable=False),
    sa.Column('progress', sa.Float(), nullable=False),
    sa.Column('accent', sa.String(length=32), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('tool_integrations',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('category', sa.String(length=64), nullable=False),
    sa.Column('connected', sa.Boolean(), nullable=False),
    sa.Column('permission', sa.String(length=64), nullable=False),
    sa.Column('call_count', sa.Integer(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('tool_integrations', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_tool_integrations_category'), ['category'], unique=False)

    op.create_table('activity_events',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('label', sa.String(length=255), nullable=False),
    sa.Column('mode_id', sa.String(length=32), nullable=False),
    sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['mode_id'], ['ai_modes.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('activity_events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_activity_events_mode_id'), ['mode_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_activity_events_occurred_at'), ['occurred_at'], unique=False)

    op.create_table('conversations',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('preview', sa.Text(), nullable=False),
    sa.Column('mode_id', sa.String(length=32), nullable=False),
    sa.Column('project_id', sa.String(length=64), nullable=True),
    sa.Column('pinned', sa.Boolean(), nullable=False),
    sa.Column('archived', sa.Boolean(), nullable=False),
    sa.Column('message_count', sa.Integer(), nullable=False),
    sa.Column('last_message_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['mode_id'], ['ai_modes.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('conversations', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_conversations_last_message_at'), ['last_message_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_conversations_mode_id'), ['mode_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_conversations_project_id'), ['project_id'], unique=False)
        batch_op.create_index('ix_conversations_recent', ['archived', 'last_message_at'], unique=False)

    op.create_table('messages',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('conversation_id', sa.String(length=64), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('role', sa.String(length=16), nullable=False),
    sa.Column('mode_id', sa.String(length=32), nullable=False),
    sa.Column('blocks', sa.JSON(), nullable=False),
    sa.Column('reasoning', sa.Text(), nullable=True),
    sa.Column('traces', sa.JSON(), nullable=True),
    sa.Column('voice', sa.Boolean(), nullable=False),
    sa.Column('tokens', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['mode_id'], ['ai_modes.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('conversation_id', 'position', name='uq_messages_thread_pos')
    )
    with op.batch_alter_table('messages', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_messages_conversation_id'), ['conversation_id'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('messages', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_messages_conversation_id'))

    op.drop_table('messages')
    with op.batch_alter_table('conversations', schema=None) as batch_op:
        batch_op.drop_index('ix_conversations_recent')
        batch_op.drop_index(batch_op.f('ix_conversations_project_id'))
        batch_op.drop_index(batch_op.f('ix_conversations_mode_id'))
        batch_op.drop_index(batch_op.f('ix_conversations_last_message_at'))

    op.drop_table('conversations')
    with op.batch_alter_table('activity_events', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_activity_events_occurred_at'))
        batch_op.drop_index(batch_op.f('ix_activity_events_mode_id'))

    op.drop_table('activity_events')
    with op.batch_alter_table('tool_integrations', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tool_integrations_category'))

    op.drop_table('tool_integrations')
    op.drop_table('projects')
    with op.batch_alter_table('memory_records', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_memory_records_learned_at'))
        batch_op.drop_index(batch_op.f('ix_memory_records_scope'))
        batch_op.drop_index(batch_op.f('ix_memory_records_owner_id'))

    op.drop_table('memory_records')
    with op.batch_alter_table('knowledge_sources', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_knowledge_sources_last_synced_at'))
        batch_op.drop_index(batch_op.f('ix_knowledge_sources_status'))
        batch_op.drop_index(batch_op.f('ix_knowledge_sources_kind'))

    op.drop_table('knowledge_sources')
    op.drop_table('daily_usage')
    op.drop_table('ai_modes')
