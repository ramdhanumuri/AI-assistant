"""Catalog, dashboard and engine-seam tests."""

from fastapi.testclient import TestClient

from app.services.engine import get_engine, list_providers
from app.services.engine.base import EngineRequest, Engine
from app.services.engine.simulator import token_estimate


class TestModes:
    def test_get_one_mode(self, client: TestClient) -> None:
        body = client.get("/api/v1/modes/analysis").json()
        assert body["label"] == "Analysis"
        assert body["caption"] == "Data & decisions"
        assert body["glyph"] == "◈"

    def test_unknown_mode_is_404_with_shaped_error(self, client: TestClient) -> None:
        response = client.get("/api/v1/modes/telepathy")
        assert response.status_code == 404
        assert response.json() == {
            "error": {
                "code": "not_found",
                "message": "Mode 'telepathy' not found.",
            }
        }


class TestProjects:
    def test_thread_counts_reflect_conversations(self, client: TestClient) -> None:
        projects = {p["id"]: p for p in client.get("/api/v1/projects").json()}
        assert projects["p-atlas"]["threads"] == 2
        assert projects["p-helios"]["threads"] == 1
        assert projects["p-ops"]["threads"] == 1

    def test_create_project(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/projects",
            json={"id": "p-new", "name": "New Program", "brief": "Test", "progress": 0.1},
        )
        assert response.status_code == 201
        assert response.json()["threads"] == 0

    def test_progress_is_bounded(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/projects", json={"id": "p-bad", "name": "Bad", "progress": 1.5}
        )
        assert response.status_code == 422


class TestKnowledge:
    def test_lists_all_seeded_sources(self, client: TestClient) -> None:
        sources = client.get("/api/v1/knowledge").json()
        assert len(sources) == 5
        assert {s["kind"] for s in sources} == {"document", "repository", "feed", "dataset"}

    def test_status_filter(self, client: TestClient) -> None:
        paused = client.get("/api/v1/knowledge", params={"status": "paused"}).json()
        assert len(paused) == 1
        assert paused[0]["id"] == "k-legal"

    def test_kind_filter(self, client: TestClient) -> None:
        repos = client.get("/api/v1/knowledge", params={"kind": "repository"}).json()
        assert len(repos) == 1
        assert repos[0]["name"].startswith("atlas-platform")


class TestTools:
    def test_lists_all_tools(self, client: TestClient) -> None:
        assert len(client.get("/api/v1/tools").json()) == 7

    def test_connected_filter(self, client: TestClient) -> None:
        disconnected = client.get("/api/v1/tools", params={"connected": False}).json()
        assert [t["id"] for t in disconnected] == ["t-calendar"]

    def test_update_connection_state(self, client: TestClient) -> None:
        response = client.patch(
            "/api/v1/tools/t-calendar", json={"connected": True, "permission": "Read"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["connected"] is True
        assert body["permission"] == "Read"

    def test_update_unknown_tool_is_404(self, client: TestClient) -> None:
        assert client.patch("/api/v1/tools/t-nope", json={"connected": True}).status_code == 404


class TestMemory:
    def test_seeded_records_are_ordered_by_confidence(self, client: TestClient) -> None:
        records = client.get("/api/v1/memory").json()
        confidences = [r["confidence"] for r in records]
        assert confidences == sorted(confidences, reverse=True)

    def test_scope_filter(self, client: TestClient) -> None:
        style = client.get("/api/v1/memory", params={"scope": "Style"}).json()
        assert len(style) == 1
        assert "British spelling" in style[0]["statement"]

    def test_create_and_forget(self, client: TestClient) -> None:
        created = client.post(
            "/api/v1/memory",
            json={"statement": "Prefers terse output", "scope": "Communication", "confidence": 0.8},
        )
        assert created.status_code == 201
        memory_id = created.json()["id"]

        assert client.delete(f"/api/v1/memory/{memory_id}").status_code == 204
        remaining = client.get("/api/v1/memory").json()
        assert memory_id not in [r["id"] for r in remaining]

    def test_confidence_is_bounded(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/memory", json={"statement": "x", "confidence": 1.7}
        )
        assert response.status_code == 422

    def test_blank_statement_is_rejected(self, client: TestClient) -> None:
        assert client.post("/api/v1/memory", json={"statement": ""}).status_code == 422

    def test_delete_unknown_is_404(self, client: TestClient) -> None:
        assert client.delete("/api/v1/memory/mem-nope").status_code == 404


class TestDashboard:
    def test_summary_aggregates_every_section(self, client: TestClient) -> None:
        body = client.get("/api/v1/dashboard/summary").json()
        stats = body["stats"]
        assert stats["totalConversations"] == 8
        assert stats["pinned"] == 2
        assert stats["activeModes"] == 7
        assert len(body["usage"]) == 7
        assert len(body["activity"]) == 5
        assert len(body["knowledge"]) == 5
        assert len(body["tools"]) == 7

    def test_stats_track_new_work(self, client: TestClient) -> None:
        before = client.get("/api/v1/dashboard/summary").json()["stats"]
        conversation = client.post("/api/v1/conversations", json={}).json()
        client.post(
            f"/api/v1/conversations/{conversation['id']}/messages", json={"body": "hello"}
        )
        after = client.get("/api/v1/dashboard/summary").json()["stats"]
        assert after["totalConversations"] == before["totalConversations"] + 1
        assert after["totalMessages"] == before["totalMessages"] + 2

    def test_message_total_matches_the_messages_table(self, client: TestClient, session) -> None:
        """The denormalised counter must agree with the actual row count."""
        from app.models import Message

        stats = client.get("/api/v1/dashboard/summary").json()["stats"]
        assert stats["totalMessages"] == session.query(Message).count()


class TestEngineSeam:
    def test_registry_resolves_the_simulator(self) -> None:
        engine = get_engine()
        assert isinstance(engine, Engine)
        assert engine.name == "simulator"
        assert list_providers() == ["simulator"]

    def test_unknown_provider_fails_loudly(self, monkeypatch) -> None:
        from app.core.errors import ServiceUnavailableError
        from app.services import engine as engine_module

        monkeypatch.setattr(engine_module.settings, "AI_PROVIDER", "not-registered")
        try:
            engine_module.get_engine()
        except ServiceUnavailableError as exc:
            assert exc.code == "engine_not_configured"
        else:
            raise AssertionError("unknown provider should raise")

    def test_recipes_cover_every_mode(self) -> None:
        engine = get_engine()
        cases = {
            "refactor the api": "coding",
            "compare jurisdictions": "research",
            "model the margin": "analysis",
            "draft a narrative": "creative",
            "review this screenshot": "vision",
            "unmatched prompt": "general",
        }
        for prompt, expected in cases.items():
            turn = engine.generate(EngineRequest(prompt=prompt, mode_id="general"))
            assert turn.mode_id == expected, prompt

    def test_voice_prompts_never_route_to_a_recipe(self) -> None:
        engine = get_engine()
        turn = engine.generate(
            EngineRequest(prompt="refactor the api module", mode_id="general", voice=True)
        )
        assert turn.mode_id == "voice"
        assert turn.route == "voice"

    def test_token_estimate_is_stable_and_positive(self) -> None:
        assert token_estimate("") == 1
        assert token_estimate("x" * 360) == 100