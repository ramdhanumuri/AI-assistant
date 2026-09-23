"""Contract tests: health, metadata, OpenAPI and the seed's integrity.

These guard the things later modules depend on — the probes an orchestrator
calls, the documented API surface, and the reference rows every view needs.
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
}


class TestHealth:
    def test_liveness_is_always_ok(self, client: TestClient) -> None:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["env"] == "test"

    def test_readiness_reports_database(self, client: TestClient) -> None:
        response = client.get("/api/v1/health/ready")
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
    def test_reports_provider_and_docs(self, client: TestClient) -> None:
        body = client.get("/api/v1/system/info").json()
        assert body["aiProvider"] == "simulator"
        assert "simulator" in body["availableProviders"]
        assert body["docsUrl"] == "/docs"
        assert body["apiVersion"] == "v1"


class TestOpenAPI:
    def test_schema_is_valid_and_covers_every_route(self, client: TestClient) -> None:
        schema = client.get("/openapi.json").json()
        assert schema["info"]["title"]
        paths = {
            (method, path)
            for path, operations in schema["paths"].items()
            for method in operations
        }
        assert EXPECTED_PATHS.issubset(paths), EXPECTED_PATHS - paths

    def test_every_operation_has_a_summary(self, client: TestClient) -> None:
        schema = client.get("/openapi.json").json()
        missing = [
            f"{method.upper()} {path}"
            for path, operations in schema["paths"].items()
            for method, operation in operations.items()
            if not operation.get("summary")
        ]
        assert missing == []

    def test_docs_and_redoc_are_served(self, client: TestClient) -> None:
        assert client.get("/docs").status_code == 200
        assert client.get("/redoc").status_code == 200


class TestSeededReferenceData:
    def test_all_tables_exist(self, session) -> None:
        assert EXPECTED_TABLES.issubset(set(inspect(session.bind).get_table_names()))

    def test_seven_modes_with_frontend_aura_tokens(self, client: TestClient) -> None:
        modes = client.get("/api/v1/modes").json()
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
        from app.models import Message

        seeded = session.query(Message).filter_by(conversation_id="c-orbital").count()
        assert seeded > 0

        assert client.delete("/api/v1/conversations/c-orbital").status_code == 204
        assert session.query(Message).filter_by(conversation_id="c-orbital").count() == 0


class TestWireFormatMatchesFrontendTypes:
    """The frozen frontend reads these exact shapes; freeze them here too.

    `src/types.ts` is the source of truth. These assertions are deliberately
    literal — if a rename slips through, this fails loudly instead of letting
    the UI render `undefined` at runtime.
    """

    def test_conversations_use_frontend_field_names(self, client: TestClient) -> None:
        item = client.get("/api/v1/conversations").json()["items"][0]
        assert set(item) == {
            "id", "title", "preview", "mode", "project", "pinned", "archived",
            "messageCount", "updatedAt", "lastMessageAt",
        }

    def test_conversation_timestamps_are_epoch_millis(self, client: TestClient) -> None:
        # `formatRelative(ts: number)` in the UI does arithmetic on these, so a
        # string here would silently render as "NaN ago".
        item = client.get("/api/v1/conversations").json()["items"][0]
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