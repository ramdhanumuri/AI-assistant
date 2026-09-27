"""Conversation write-path tests.

The highest-value tests in Module 2: they exercise the full turn — persist the
user message, generate through the engine seam, persist the reply, keep the
denormalised counters correct — against a real database.

MODULE 4: the `client` fixture holds a real session, and the Module 2 demo
threads have no owner, so they are deliberately invisible. Every test here
therefore creates its own threads; the assertions are unchanged in substance.
The one that did rely on seeded rows (`seeded_transcripts_are_available`) now
verifies the seed through the database instead, because serving unowned rows to
an authenticated user would be the bug, not the feature.
"""

from fastapi.testclient import TestClient

VALID_BLOCKS = {
    "text",
    "code",
    "list",
    "table",
    "insight",
    "cards",
    "file",
    "suggestions",
    "timeline",
}


def _create(client: TestClient, **overrides) -> dict:
    payload = {"title": "Test thread", "modeId": "general", **overrides}
    response = client.post("/api/v1/conversations", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _post_turn(client: TestClient, conversation_id: str, body: str, **extra) -> dict:
    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"body": body, **extra},
    )
    assert response.status_code == 201, response.text
    return response.json()


class TestCreateConversation:
    def test_creates_with_defaults(self, client: TestClient) -> None:
        conversation = _create(client)
        assert conversation["messageCount"] == 0
        assert conversation["pinned"] is False
        assert conversation["archived"] is False
        assert conversation["lastMessageAt"] is None
        assert conversation["id"].startswith("conv-")

    def test_rejects_unknown_mode(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/conversations", json={"title": "x", "modeId": "telepathy"}
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"

    def test_rejects_empty_title(self, client: TestClient) -> None:
        response = client.post("/api/v1/conversations", json={"title": ""})
        assert response.status_code == 422

    def test_links_to_a_project(self, client: TestClient) -> None:
        conversation = _create(client, projectId="p-helios")
        assert conversation["project"] == "p-helios"


class TestPostMessage:
    def test_returns_both_halves_of_the_turn(self, client: TestClient) -> None:
        conversation = _create(client)
        result = _post_turn(client, conversation["id"], "Model the margin impact")

        user, assistant = result["userMessage"], result["assistantMessage"]
        assert user["role"] == "user"
        assert assistant["role"] == "assistant"
        assert user["position"] < assistant["position"]
        assert user["blocks"][0]["body"] == "Model the margin impact"

    def test_persists_an_ordered_transcript(self, client: TestClient) -> None:
        conversation = _create(client)
        for body in ("first", "second", "third"):
            _post_turn(client, conversation["id"], body)

        listed = client.get(
            f"/api/v1/conversations/{conversation['id']}/messages"
        ).json()
        assert listed["total"] == 6
        positions = [m["position"] for m in listed["items"]]
        assert positions == sorted(positions)
        roles = [m["role"] for m in listed["items"]]
        assert roles == ["user", "assistant"] * 3

    def test_updates_conversation_counters_and_preview(self, client: TestClient) -> None:
        conversation = _create(client)
        result = _post_turn(client, conversation["id"], "Compare three jurisdictions")

        refreshed = result["conversation"]
        assert refreshed["messageCount"] == 2
        assert refreshed["preview"]
        assert refreshed["lastMessageAt"] is not None

    def test_first_turn_titles_an_untitled_conversation(self, client: TestClient) -> None:
        conversation = client.post("/api/v1/conversations", json={}).json()
        assert conversation["title"] == "New conversation"

        result = _post_turn(
            client, conversation["id"], "Summarise the vendor trade-off matrix"
        )
        assert result["conversation"]["title"] == "Summarise the vendor trade-off matrix"

    def test_long_prompt_title_is_truncated(self, client: TestClient) -> None:
        conversation = client.post("/api/v1/conversations", json={}).json()
        prompt = "word " * 40
        title = _post_turn(client, conversation["id"], prompt)["conversation"]["title"]
        assert len(title) <= 61
        assert title.endswith("…")

    def test_existing_title_is_not_overwritten(self, client: TestClient) -> None:
        conversation = _create(client, title="Deliberate title")
        result = _post_turn(client, conversation["id"], "anything at all")
        assert result["conversation"]["title"] == "Deliberate title"

    def test_route_changes_mode_from_the_prompt(self, client: TestClient) -> None:
        """The engine seam, not the client, decides the response mode."""
        conversation = _create(client, modeId="general")
        result = _post_turn(
            client, conversation["id"], "refactor the api module and fix the bug"
        )
        assert result["assistantMessage"]["mode"] == "coding"

    def test_explicit_mode_is_respected_for_generic_prompts(self, client: TestClient) -> None:
        conversation = _create(client)
        result = _post_turn(client, conversation["id"], "hello", modeId="research")
        # No recipe matches, so the requested mode carries through.
        assert result["assistantMessage"]["mode"] == "research"

    def test_assistant_blocks_are_wellformed(self, client: TestClient) -> None:
        conversation = _create(client)
        result = _post_turn(
            client, conversation["id"], "model the margin sensitivity"
        )
        assistant = result["assistantMessage"]
        assert assistant["blocks"], "assistant must return at least one block"
        kinds = [block["kind"] for block in assistant["blocks"]]
        assert set(kinds).issubset(VALID_BLOCKS)
        assert assistant["reasoning"]
        assert assistant["tokens"] > 0
        assert all(trace["state"] == "done" for trace in assistant["traces"])

    def test_engine_is_deterministic(self, client: TestClient) -> None:
        first = _create(client)
        second = _create(client)
        prompt = "model the margin sensitivity"
        a = _post_turn(client, first["id"], prompt)["assistantMessage"]
        b = _post_turn(client, second["id"], prompt)["assistantMessage"]
        assert a["blocks"] == b["blocks"]
        assert a["tokens"] == b["tokens"]

    def test_voice_turn_uses_the_voice_mode(self, client: TestClient) -> None:
        conversation = _create(client, modeId="voice")
        result = _post_turn(client, conversation["id"], "give me a status update", voice=True)
        assistant = result["assistantMessage"]
        assert assistant["mode"] == "voice"
        assert assistant["voice"] is True
        assert len(assistant["blocks"]) == 1

    def test_rejects_empty_body(self, client: TestClient) -> None:
        conversation = _create(client)
        response = client.post(
            f"/api/v1/conversations/{conversation['id']}/messages",
            json={"body": ""},
        )
        assert response.status_code == 422

    def test_rejects_unknown_mode_on_turn(self, client: TestClient) -> None:
        conversation = _create(client)
        response = client.post(
            f"/api/v1/conversations/{conversation['id']}/messages",
            json={"body": "hi", "modeId": "telepathy"},
        )
        assert response.status_code == 422

    def test_unknown_conversation_is_404(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/conversations/conv-missing/messages", json={"body": "hi"}
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"

    def test_failed_turn_writes_nothing(self, client: TestClient) -> None:
        """A rejected payload must not leave a half-written exchange behind."""
        conversation = _create(client)
        client.post(
            f"/api/v1/conversations/{conversation['id']}/messages",
            json={"body": "hi", "modeId": "telepathy"},
        )
        messages = client.get(
            f"/api/v1/conversations/{conversation['id']}/messages"
        ).json()
        assert messages["total"] == 0


class TestReadAndFilter:
    def test_pinned_filter(self, client: TestClient) -> None:
        pinned = _create(client, title="Pinned one")
        client.patch(f"/api/v1/conversations/{pinned['id']}", json={"pinned": True})
        result = client.get("/api/v1/conversations", params={"pinned": True}).json()
        assert result["total"] == 1
        assert all(item["pinned"] for item in result["items"])

    def test_project_filter(self, client: TestClient) -> None:
        _create(client, title="Atlas work", projectId="p-atlas")
        result = client.get("/api/v1/conversations", params={"projectId": "p-atlas"}).json()
        assert result["total"] == 1
        assert all(item["project"] == "p-atlas" for item in result["items"])

    def test_mode_filter(self, client: TestClient) -> None:
        _create(client, title="Coding work", modeId="coding")
        result = client.get("/api/v1/conversations", params={"modeId": "coding"}).json()
        assert result["total"] == 1
        assert all(item["mode"] == "coding" for item in result["items"])

    def test_search_matches_title_case_insensitively(self, client: TestClient) -> None:
        _create(client, title="Orbital margin model")
        result = client.get("/api/v1/conversations", params={"search": "MARGIN"}).json()
        assert result["total"] == 1
        assert result["items"][0]["title"] == "Orbital margin model"

    def test_pagination_reports_total_independently(self, client: TestClient) -> None:
        for index in range(4):
            _create(client, title=f"Thread {index}")

        result = client.get(
            "/api/v1/conversations", params={"limit": 3, "offset": 0}
        ).json()
        assert result["total"] == 4
        assert len(result["items"]) == 3
        assert result["limit"] == 3

        second = client.get(
            "/api/v1/conversations", params={"limit": 3, "offset": 3}
        ).json()
        assert second["total"] == 4
        assert [i["id"] for i in result["items"]] != [i["id"] for i in second["items"]]

    def test_limit_is_bounded(self, client: TestClient) -> None:
        assert client.get("/api/v1/conversations", params={"limit": 500}).status_code == 422

    def test_list_is_empty_until_the_user_creates_a_thread(self, client: TestClient) -> None:
        assert client.get("/api/v1/conversations").json()["total"] == 0
        _create(client, title="Mine")
        assert client.get("/api/v1/conversations").json()["total"] == 1

    def test_archived_threads_are_excluded_by_default(self, client: TestClient) -> None:
        conversation = _create(client)
        client.patch(
            f"/api/v1/conversations/{conversation['id']}", json={"archived": True}
        )
        visible = client.get("/api/v1/conversations").json()
        assert conversation["id"] not in [i["id"] for i in visible["items"]]

        included = client.get(
            "/api/v1/conversations", params={"includeArchived": True}
        ).json()
        assert conversation["id"] in [i["id"] for i in included["items"]]

    def test_module2_demo_threads_are_not_served_to_a_user(self, client: TestClient) -> None:
        """The seeded demo rows have no owner, so they belong to nobody.

        This is the ownership rule stated as a test: `owner_id IS NULL` matches
        no caller, so an authenticated user cannot read the Module 2 demo
        transcript even though it is still in the database.
        """
        assert client.get("/api/v1/conversations/c-orbital").status_code == 404
        assert client.get("/api/v1/conversations/c-orbital/messages").status_code == 404
        assert client.get("/api/v1/conversations").json()["total"] == 0


class TestUpdateAndDelete:
    def test_patch_updates_only_supplied_fields(self, client: TestClient) -> None:
        conversation = _create(client, title="Original", modeId="research")
        updated = client.patch(
            f"/api/v1/conversations/{conversation['id']}", json={"pinned": True}
        ).json()
        assert updated["pinned"] is True
        assert updated["title"] == "Original"
        assert updated["mode"] == "research"

    def test_patch_rejects_unknown_mode(self, client: TestClient) -> None:
        conversation = _create(client)
        response = client.patch(
            f"/api/v1/conversations/{conversation['id']}", json={"modeId": "telepathy"}
        )
        assert response.status_code == 422

    def test_delete_removes_the_conversation(self, client: TestClient) -> None:
        conversation = _create(client)
        assert client.delete(f"/api/v1/conversations/{conversation['id']}").status_code == 204
        assert client.get(f"/api/v1/conversations/{conversation['id']}").status_code == 404

    def test_delete_is_idempotent_in_effect(self, client: TestClient) -> None:
        conversation = _create(client)
        client.delete(f"/api/v1/conversations/{conversation['id']}")
        assert client.delete(f"/api/v1/conversations/{conversation['id']}").status_code == 404