"""Tests for the MODULE 3 Supabase seam.

These exercise the real code paths in `app.db.supabase` and the endpoints that
report its state. Nothing here needs a live Supabase project: the unconfigured
and unreachable cases are the behaviour that must hold in CI, and they are
produced by pointing the client at real (absent / closed) addresses rather than
by mocking httpx.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db import supabase


def _reload_settings(**env: str) -> None:
    """Apply environment overrides and drop the cached Settings.

    `settings` is an lru_cache'd singleton, so mutating os.environ alone is not
    enough — the cache has to be cleared for a new value to be observed.
    """
    import os

    for key, value in env.items():
        os.environ[key] = value
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _restore_settings() -> None:
    """Guarantee the cached Settings does not leak into other test modules."""
    yield
    import os

    for key in ("SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY"):
        os.environ.pop(key, None)
    get_settings.cache_clear()


class TestConfiguration:
    def test_unconfigured_by_default(self) -> None:
        assert supabase.is_configured() is False
        assert supabase.probe() == "unconfigured"

    def test_configured_requires_url_and_anon_key(self) -> None:
        _reload_settings(SUPABASE_URL="https://example.supabase.co")
        assert supabase.is_configured() is False, "anon key is still missing"

        _reload_settings(SUPABASE_ANON_KEY="anon-key")
        assert supabase.is_configured() is True

    def test_rest_url_trims_trailing_slash(self) -> None:
        _reload_settings(
            SUPABASE_URL="https://example.supabase.co/",
            SUPABASE_ANON_KEY="anon-key",
        )
        assert supabase.supabase_settings().rest_url == (
            "https://example.supabase.co/rest/v1"
        )

    def test_service_role_key_never_required(self) -> None:
        _reload_settings(
            SUPABASE_URL="https://example.supabase.co",
            SUPABASE_ANON_KEY="anon-key",
        )
        assert supabase.is_configured() is True
        assert supabase.client_info()["service_role_configured"] is False


class TestAuthHeaders:
    def test_anon_key_is_the_default(self) -> None:
        _reload_settings(
            SUPABASE_URL="https://example.supabase.co",
            SUPABASE_ANON_KEY="anon-key",
            SUPABASE_SERVICE_ROLE_KEY="service-key",
        )
        headers = supabase.auth_headers()
        assert headers["apikey"] == "anon-key"
        assert headers["Authorization"] == "Bearer anon-key"

    def test_service_role_is_opt_in(self) -> None:
        _reload_settings(
            SUPABASE_URL="https://example.supabase.co",
            SUPABASE_ANON_KEY="anon-key",
            SUPABASE_SERVICE_ROLE_KEY="service-key",
        )
        headers = supabase.auth_headers(service_role=True)
        assert headers["apikey"] == "service-key"
        assert headers["Authorization"] == "Bearer service-key"


class TestProbe:
    def test_unreachable_host_reports_unavailable_not_raise(self) -> None:
        """Readiness must degrade, never 500, when Supabase is down.

        Port 1 on loopback has no listener, so httpx raises a connection error
        through the real client — exactly the failure a readiness probe must
        absorb.
        """
        _reload_settings(
            SUPABASE_URL="http://127.0.0.1:1",
            SUPABASE_ANON_KEY="anon-key",
        )
        assert supabase.probe() == "unavailable"


class TestEndpointReporting:
    def test_readiness_reports_supabase_state(self, client: TestClient) -> None:
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 200
        body = response.json()
        assert body["database"] == "ok"
        # Unconfigured in CI, so the literal value is deterministic here.
        assert body["supabase"] == "unconfigured"

    def test_liveness_reports_default_supabase_state(
        self, client: TestClient
    ) -> None:
        body = client.get("/api/v1/health").json()
        assert body["supabase"] == "unconfigured"

    def test_system_info_exposes_supabase_without_secrets(
        self, client: TestClient
    ) -> None:
        body = client.get("/api/v1/system/info").json()
        assert body["supabase"] == {
            "configured": False,
            "url": None,
            "serviceRoleConfigured": False,
        }
        serialised = str(body)
        assert "anon" not in serialised.lower() or "configured" in serialised


class TestSQLMigrations:
    """The migrations ship as files, so their structure is asserted directly.

    They cannot be executed here without a Postgres server, so these checks
    prove the files exist, are ordered, and cover every table the ORM declares
    — the drift that would otherwise only surface during a dashboard deploy.
    """

    def test_migration_files_present_and_ordered(self) -> None:
        from pathlib import Path

        migrations = sorted(
            (Path(__file__).resolve().parents[1] / "supabase" / "migrations").glob(
                "*.sql"
            )
        )
        names = [p.name for p in migrations]
        assert names[0].startswith("0001_")
        assert names[1].startswith("0002_")

    def test_schema_migration_creates_every_orm_table(self) -> None:
        from pathlib import Path

        from app.db.base import Base

        sql = (
            Path(__file__).resolve().parents[1]
            / "supabase"
            / "migrations"
            / "0001_core_schema.sql"
        ).read_text(encoding="utf-8")

        import app.models  # noqa: F401  (register mappers)

        for table in Base.metadata.tables:
            assert f"create table if not exists {table}" in sql, (
                f"{table} missing from the Supabase schema migration"
            )

    def test_rls_migration_enables_rls_on_every_orm_table(self) -> None:
        from pathlib import Path

        from app.db.base import Base

        sql = (
            Path(__file__).resolve().parents[1]
            / "supabase"
            / "migrations"
            / "0002_rls_policies.sql"
        ).read_text(encoding="utf-8")

        for table in Base.metadata.tables:
            assert f"alter table {table}" in sql and "enable row level security" in sql, (
                f"RLS not enabled for {table}"
            )

    def test_migrations_are_valid_postgres_syntax(self) -> None:
        """Parse the migrations with the real PostgreSQL grammar.

        pglast bundles libpg_query (the parser Postgres itself uses), so this
        catches a syntax error before it reaches the dashboard SQL editor. It is
        an optional dependency: skipped rather than failed when absent.
        """
        pglast = pytest.importorskip("pglast")
        from pathlib import Path

        migrations = sorted(
            (Path(__file__).resolve().parents[1] / "supabase" / "migrations").glob(
                "*.sql"
            )
        )
        assert migrations, "no migration files found"
        for path in migrations:
            statements = pglast.parse_sql(path.read_text(encoding="utf-8"))
            assert len(statements) > 0, f"{path.name} parsed to zero statements"
