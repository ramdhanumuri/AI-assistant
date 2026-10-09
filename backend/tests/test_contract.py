"""Contract tests: health, metadata, OpenAPI and the seed's integrity.

These guard the things later modules depend on — the probes an orchestrator
calls, the documented API surface, and the reference rows every view needs.

MODULE 4 note: this file uses `anon_client` for the public surface (probes,
metadata, docs, modes) and `client` for the authenticated surface. The set of
routes that *require* a session is asserted explicitly in
`test_authorization.py`; here the concern is the wire format, not access.
"""

from fastapi.testclient import TestClient
from sqlalchemy import inspect, text

from app.main import app

EXPECTED_PATHS = {
    ("get", "/api/v1/health"),
    ("get", "/api/v1/health/ready"),
    ("get", "/api/v1/system/info"),
    ("get", "/api/v1/modes"),
    ("get", "/api/v1/modes/{mode_id}"),
    ("get", "/api/v1/conversations"),
    ("post", "/api/v1/conversations"),
    ("get", "/api/v1/conversations/{conversation_id}"),
    ("patch", "/api/v1/conversations/{conversation_id}"),
    ("delete", "/api/v1/conversations/{conversation_id}"),
    ("get", "/api/v1/conversations/{conversation_id}/messages"),
    ("post", "/api/v1/conversations/{conversation_id}/messages"),
    ("get", "/api/v1/dashboard/summary"),
    ("get", "/api/v1/projects"),
    ("post", "/api/v1/projects"),
    ("get", "/api/v1/knowledge"),
    ("get", "/api/v1/tools"),
    ("patch", "/api/v1/tools/{tool_id}"),
    ("get", "/api/v1/memory"),
    ("post", "/api/v1/memory"),
    ("delete", "/api/v1/memory/{memory_id}"),
    # STEP 6 AI surface.
    ("get", "/api/v1/ai/capabilities"),
    ("get", "/api/v1/ai/usage"),
    ("post", "/api/v1/ai/conversations/{conversation_id}/messages/stream"),
    # MODULE 4 surface.
    ("post", "/api/v1/auth/register"),
    ("post", "/api/v1/auth/login"),
    ("post", "/api/v1/auth/logout"),
    ("post", "/api/v1/auth/refresh"),
    ("get", "/api/v1/auth/me"),
    ("post", "/api/v1/auth/change-password"),
    ("post", "/api/v1/auth/forgot-password"),
    ("post", "/api/v1/auth/reset-password"),
    ("get", "/api/v1/users/me"),
    ("get", "/api/v1/admin/users"),
    ("get", "/api/v1/admin/usage"),
    ("get", "/api/v1/admin/ai-usage"),
    ("get", "/api/v1/admin/events"),
    ("get", "/api/v1/admin/system-health"),
}

EXPECTED_TABLES = {
    "ai_modes",
    "projects",
    "conversations",
    "messages",
    "knowledge_sources",
    "tool_integrations",
    "memory_records",
    "activity_events",
    "daily_usage",
    # MODULE 4 identity and session tables.
    "users",
    "user_preferences",
    "auth_sessions",
    "password_reset_tokens",
    "auth_events",
    # STEP 6 AI usage ledger.
    "ai_usage_events",
}


class TestHealth:
    def test_liveness_is_always_ok(self, anon_client: TestClient) -> None:
        response = anon_client.get("/api/v1/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["env"] == "test"

    def test_readiness_reports_database(self, anon_client: TestClient) -> None:
        response = anon_client.get("/api/v1/health/ready")
        assert response.status_code == 200
        assert response.json()["database"] == "ok"

    def test_readiness_fails_when_database_is_down(self, db: None) -> None:
        """An unreachable database must surface as 503, not a 500 stack trace."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session as SASession

        from app.api.deps import get_db

        # Points at a directory that does not exist, so `SELECT 1` genuinely
        # fails at connect time rather than being simulated.
        unusable = create_engine("sqlite:////nonexistent-dir/aurelis.db")

        def broken_db():
            with SASession(unusable) as bad_session:
                yield bad_session

        app.dependency_overrides[get_db] = broken_db
        try:
            with TestClient(app) as local_client:
                response = local_client.get("/api/v1/health/ready")
            assert response.status_code == 503
            body = response.json()
            assert body["status"] == "degraded"
            assert body["database"] == "unavailable"
            assert "nonexistent-dir" not in response.text
        finally:
            app.dependency_overrides.clear()
            unusable.dispose()

    def test_liveness_is_unaffected_by_a_down_database(self, db: None) -> None:
        """Liveness must not depend on the database, or a blip restarts the app."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session as SASession

        from app.api.deps import get_db

        unusable = create_engine("sqlite:////nonexistent-dir/aurelis.db")

        def broken_db():
            with SASession(unusable) as bad_session:
                yield bad_session

        app.dependency_overrides[get_db] = broken_db
        try:
            with TestClient(app) as local_client:
                assert local_client.get("/api/v1/health").status_code == 200
        finally:
            app.dependency_overrides.clear()
            unusable.dispose()


class TestSystemInfo:
    def test_reports_provider_and_docs(self, anon_client: TestClient) -> None:
        body = anon_client.get("/api/v1/system/info").json()
        assert body["aiProvider"] == "simulator"
        assert "simulator" in body["availableProviders"]
        assert body["docsUrl"] == "/docs"
        assert body["apiVersion"] == "v1"


class TestOpenAPI:
    def test_schema_is_valid_and_covers_every_route(self, anon_client: TestClient) -> None:
        schema = anon_client.get("/openapi.json").json()
        assert schema["info"]["title"]
        paths = {
            (method, path)
            for path, operations in schema["paths"].items()
            for method in operations
        }
        assert EXPECTED_PATHS.issubset(paths), EXPECTED_PATHS - paths

    def test_every_operation_has_a_summary(self, anon_client: TestClient) -> None:
        schema = anon_client.get("/openapi.json").json()
        missing = [
            f"{method.upper()} {path}"
            for path, operations in schema["paths"].items()
            for method, operation in operations.items()
            if not operation.get("summary")
        ]
        assert missing == []

    def test_docs_and_redoc_are_served(self, anon_client: TestClient) -> None:
        assert anon_client.get("/docs").status_code == 200
        assert anon_client.get("/redoc").status_code == 200


class TestSeededReferenceData:
    def test_all_tables_exist(self, session) -> None:
        assert EXPECTED_TABLES.issubset(set(inspect(session.bind).get_table_names()))

    def test_seven_modes_with_frontend_aura_tokens(self, anon_client: TestClient) -> None:
        modes = anon_client.get("/api/v1/modes").json()
        assert [m["id"] for m in modes] == [
            "general",
            "research",
            "coding",
            "creative",
            "analysis",
            "vision",
            "voice",
        ]
        for mode in modes:
            parts = mode["aura"].split(" ")
            assert len(parts) == 3 and all(0 <= int(p) <= 255 for p in parts)

    def test_seed_is_idempotent(self, session) -> None:
        from app.db.seed import seed_all

        before = session.execute(text("SELECT COUNT(*) FROM conversations")).scalar()
        seed_all(session)
        seed_all(session)
        after = session.execute(text("SELECT COUNT(*) FROM conversations")).scalar()
        assert before == after

    def test_seed_creates_no_accounts(self, session) -> None:
        """No user is ever seeded — least of all an administrator.

        A seeded account is a shipped credential. The only way to get an admin
        is the explicit `create_admin` command.
        """
        from app.models import User

        assert session.query(User).count() == 0

    def test_foreign_keys_are_enforced(self, session) -> None:
        from sqlalchemy.exc import IntegrityError

        from app.models import Conversation

        session.add(
            Conversation(
                id="c-bad-mode",
                title="Bad",
                preview="",
                mode_id="does-not-exist",
                message_count=0,
            )
        )
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
        else:
            raise AssertionError("FK constraint was not enforced")

    def test_cascade_delete_removes_messages(self, client: TestClient, session) -> None:
        """A thread the caller owns is deletable, and takes its messages with it."""
        from app.models import Message

        created = client.post("/api/v1/conversations", json={"title": "Cascade probe"}).json()
        client.post(
            f"/api/v1/conversations/{created['id']}/messages", json={"body": "hello"}
        )
        assert session.query(Message).filter_by(conversation_id=created["id"]).count() == 2

        assert client.delete(f"/api/v1/conversations/{created['id']}").status_code == 204
        assert session.query(Message).filter_by(conversation_id=created["id"]).count() == 0


class TestWireFormatMatchesFrontendTypes:
    """The frozen frontend reads these exact shapes; freeze them here too.

    `src/types.ts` is the source of truth. These assertions are deliberately
    literal — if a rename slips through, this fails loudly instead of letting
    the UI render `undefined` at runtime.
    """

    def test_conversations_use_frontend_field_names(self, client: TestClient) -> None:
        client.post("/api/v1/conversations", json={"title": "Format probe"})
        item = client.get("/api/v1/conversations").json()["items"][0]
        assert set(item) == {
            "id", "title", "preview", "mode", "project", "pinned", "archived",
            "messageCount", "updatedAt", "lastMessageAt",
        }

    def test_conversation_timestamps_are_epoch_millis(self, client: TestClient) -> None:
        # `formatRelative(ts: number)` in the UI does arithmetic on these, so a
        # string here would silently render as "NaN ago".
        created = client.post(
            "/api/v1/conversations", json={"title": "Timestamp probe"}
        ).json()
        client.post(
            f"/api/v1/conversations/{created['id']}/messages", json={"body": "hello"}
        )
        item = client.get(f"/api/v1/conversations/{created['id']}").json()
        assert isinstance(item["updatedAt"], int)
        assert isinstance(item["lastMessageAt"], int)
        assert item["updatedAt"] > 1_600_000_000_000  # a plausible epoch-ms value

    def test_catalog_fields_match_frontend_names(self, client: TestClient) -> None:
        assert set(client.get("/api/v1/projects").json()[0]) == {
            "id", "name", "brief", "progress", "accent", "threads",
        }
        assert set(client.get("/api/v1/knowledge").json()[0]) == {
            "id", "name", "kind", "status", "items", "updated",
        }
        assert set(client.get("/api/v1/tools").json()[0]) == {
            "id", "name", "category", "connected", "permission", "calls",
        }
        # Memory is per-account, so the shape is asserted against a record the
        # caller just created rather than against the Module 2 demo rows.
        client.post("/api/v1/memory", json={"statement": "Wire format probe"})
        assert set(client.get("/api/v1/memory").json()[0]) == {
            "id", "statement", "scope", "confidence", "learned",
        }

    def test_activity_and_freshness_are_rendered_text(self, client: TestClient) -> None:
        """These two are printed verbatim by the UI, unlike the epoch fields."""
        activity = client.get("/api/v1/dashboard/summary").json()["activity"][0]
        assert set(activity) == {"id", "label", "mode", "at"}
        assert isinstance(activity["at"], str)

        knowledge = client.get("/api/v1/knowledge").json()[0]
        assert isinstance(knowledge["updated"], str)
        assert knowledge["updated"].endswith("ago")

    def test_request_aliases_still_accept_legacy_camel_case(self, client: TestClient) -> None:
        """POST bodies keep accepting `modeId`/`projectId`, not just `mode`."""
        created = client.post(
            "/api/v1/conversations",
            json={"title": "Alias probe", "modeId": "general", "projectId": "p-atlas"},
        )
        assert created.status_code == 201
        body = created.json()
        assert body["mode"] == "general"
        assert body["project"] == "p-atlas"


class TestSecurityHeaders:
    """MODULE 4: the header foundation. Full policy work is Step 5."""

    def test_baseline_headers_on_every_response(self, anon_client: TestClient) -> None:
        headers = anon_client.get("/api/v1/health").headers
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["X-Frame-Options"] == "DENY"
        assert headers["Referrer-Policy"] == "no-referrer"
        assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]

    def test_headers_are_present_on_error_responses_too(self, anon_client: TestClient) -> None:
        response = anon_client.get("/api/v1/conversations")
        assert response.status_code == 401
        assert response.headers["X-Content-Type-Options"] == "nosniff"

    def test_docs_get_a_compatible_csp(self, anon_client: TestClient) -> None:
        """The API docs need a looser policy than the app or Swagger breaks."""
        docs_csp = anon_client.get("/docs").headers["Content-Security-Policy"]
        app_csp = anon_client.get("/api/v1/health").headers["Content-Security-Policy"]
        assert "cdn.jsdelivr.net" in docs_csp
        assert "cdn.jsdelivr.net" not in app_csp

    def test_no_hsts_over_plain_http(self, anon_client: TestClient) -> None:
        """In development the API is served over HTTP; HSTS would poison localhost."""
        assert "Strict-Transport-Security" not in anon_client.get("/api/v1/health").headers