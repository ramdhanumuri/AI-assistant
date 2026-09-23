"""Migration and schema-shape tests.

These prove the Alembic migration produces exactly the schema the models
declare — the failure mode this catches is a model edited without a migration,
which would otherwise only surface in production.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect

from app.db.base import Base

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _run_alembic(database_url: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-x", f"db_url={database_url}", *args],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "DATABASE_URL": database_url},
    )


class TestMigration:
    def test_upgrade_head_creates_every_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            url = f"sqlite:///{Path(tmp) / 'migrated.db'}"
            result = _run_alembic(url, "upgrade", "head")
            assert result.returncode == 0, result.stderr

            engine = create_engine(url)
            tables = set(inspect(engine).get_table_names())
            engine.dispose()

            assert "alembic_version" in tables
            expected = set(Base.metadata.tables.keys())
            assert expected.issubset(tables), expected - tables

    def test_migration_matches_models_exactly(self) -> None:
        """Autogenerate against a migrated DB must find nothing to change."""
        with tempfile.TemporaryDirectory() as tmp:
            url = f"sqlite:///{Path(tmp) / 'migrated.db'}"
            assert _run_alembic(url, "upgrade", "head").returncode == 0

            result = _run_alembic(url, "check")
            assert result.returncode == 0, (
                "Model/migration drift detected — run "
                f"`alembic revision --autogenerate`. Output:\n{result.stdout}\n{result.stderr}"
            )

    def test_downgrade_removes_the_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            url = f"sqlite:///{Path(tmp) / 'migrated.db'}"
            assert _run_alembic(url, "upgrade", "head").returncode == 0
            result = _run_alembic(url, "downgrade", "base")
            assert result.returncode == 0, result.stderr

            engine = create_engine(url)
            tables = set(inspect(engine).get_table_names())
            engine.dispose()

            expected = set(Base.metadata.tables.keys())
            assert not (expected & tables), expected & tables


class TestSchemaShape:
    @pytest.mark.parametrize(
        ("table", "columns"),
        [
            ("ai_modes", {"id", "label", "caption", "description", "aura", "glyph"}),
            (
                "conversations",
                {"id", "title", "preview", "mode_id", "project_id", "pinned", "archived",
                 "message_count", "last_message_at"},
            ),
            (
                "messages",
                {"id", "conversation_id", "position", "role", "mode_id", "blocks",
                 "reasoning", "traces", "voice", "tokens"},
            ),
            ("memory_records", {"id", "statement", "scope", "confidence", "owner_id", "learned_at"}),
            ("knowledge_sources", {"id", "name", "kind", "status", "item_count", "last_synced_at"}),
            ("tool_integrations", {"id", "name", "category", "connected", "permission"}),
            ("daily_usage", {"id", "day", "label", "value", "secondary"}),
            ("activity_events", {"id", "label", "mode_id", "occurred_at"}),
        ],
    )
    def test_expected_columns_exist(self, session, table: str, columns: set[str]) -> None:
        actual = {c["name"] for c in inspect(session.bind).get_columns(table)}
        assert columns.issubset(actual), columns - actual

    def test_timestamps_are_mixed_into_content_tables(self, session) -> None:
        for table in ("conversations", "messages", "memory_records", "projects"):
            columns = {c["name"] for c in inspect(session.bind).get_columns(table)}
            assert {"created_at", "updated_at"}.issubset(columns), table

    def test_thread_position_is_unique_per_conversation(self, session) -> None:
        constraints = inspect(session.bind).get_unique_constraints("messages")
        names = {c["name"] for c in constraints}
        assert "uq_messages_thread_pos" in names

    def test_used_indexes_exist(self, session) -> None:
        expected = {
            "conversations": {"ix_conversations_mode_id", "ix_conversations_project_id"},
            "messages": {"ix_messages_conversation_id"},
            "activity_events": {"ix_activity_events_mode_id"},
            "knowledge_sources": {"ix_knowledge_sources_last_synced_at"},
            "memory_records": {"ix_memory_records_learned_at"},
        }
        for table, names in expected.items():
            actual = {i["name"] for i in inspect(session.bind).get_indexes(table)}
            assert names.issubset(actual), (table, names - actual)

    def test_relative_time_columns_are_timestamps_not_text(self, session) -> None:
        """The UI shows "4 min ago"; the column must stay a real datetime.

        Storing the rendered string would freeze the wording and make the
        column unsortable, so this guards the choice to derive labels on read.
        """
        for table, column in (
            ("activity_events", "occurred_at"),
            ("knowledge_sources", "last_synced_at"),
            ("memory_records", "learned_at"),
        ):
            columns = {c["name"]: c for c in inspect(session.bind).get_columns(table)}
            assert "DATETIME" in str(columns[column]["type"]).upper(), (table, column)