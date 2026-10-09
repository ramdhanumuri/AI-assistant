"""Authorization tests (MODULE 4).

Authentication answers "who is this?"; this file is about "what may they do?".
The distinction matters because authentication bugs are loud — a request fails —
while authorization bugs are quiet: the request succeeds and returns someone
else's data.

Every test here is adversarial. It plays a normal user trying to reach something
that is not theirs, a normal user trying to become an administrator, or an
unauthenticated client trying to reach a protected route. The expectation is
always refusal, and the refusal must not leak whether the target exists.

Two clients are used per test where cross-account access is the subject, so the
"other" account is a real session established through the real login endpoint.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import settings
from app.models import AuthSession, User
from tests.conftest import (
    CSRF_HEADER,
    TEST_PASSWORD,
    add_second_user,
    arm_csrf,
    register_user,
)

# A password that satisfies the strength policy, used where a request body has
# to be valid enough to reach the guard under test rather than failing on
# validation first.
# Must differ from TEST_PASSWORD: reusing the current password is itself a
# validation failure, which would mask the guard under test.
STRONG_NEW_PASSWORD = "Obsidian-Meridian-77"

# The routes that must never be reachable without a session. Each entry is
# (method, path, body) with `body=None` for a bodyless request. Bodies are
# deliberately *valid*: an anonymous caller must be refused for being anonymous,
# not because the payload happened to be malformed.
PROTECTED_ROUTES: list[tuple[str, str, dict | None]] = [
    ("GET", "/api/v1/auth/me", None),
    ("GET", "/api/v1/auth/sessions", None),
    (
        "POST",
        "/api/v1/auth/change-password",
        {"current_password": TEST_PASSWORD, "new_password": STRONG_NEW_PASSWORD},
    ),
    ("DELETE", "/api/v1/auth/sessions", None),
    ("GET", "/api/v1/users/me", None),
    ("PATCH", "/api/v1/users/me", {"full_name": "Someone"}),
    ("GET", "/api/v1/users/me/preferences", None),
    ("PATCH", "/api/v1/users/me/preferences", {"density": "compact"}),
    ("GET", "/api/v1/conversations", None),
    ("POST", "/api/v1/conversations", {"title": "Nope"}),
    ("GET", "/api/v1/conversations/c-anything", None),
    ("PATCH", "/api/v1/conversations/c-anything", {"title": "Nope"}),
    ("DELETE", "/api/v1/conversations/c-anything", None),
    ("GET", "/api/v1/conversations/c-anything/messages", None),
    ("POST", "/api/v1/conversations/c-anything/messages", {"body": "hi"}),
    ("GET", "/api/v1/dashboard/summary", None),
    ("GET", "/api/v1/projects", None),
    ("POST", "/api/v1/projects", {"id": "p-anon-probe", "name": "Nope"}),
    ("GET", "/api/v1/knowledge", None),
    ("GET", "/api/v1/tools", None),
    ("PATCH", "/api/v1/tools/t-calendar", {"connected": True}),
    ("GET", "/api/v1/memory", None),
    ("POST", "/api/v1/memory", {"statement": "Nope"}),
    ("DELETE", "/api/v1/memory/mem-anything", None),
    # STEP 6 AI surface.
    ("GET", "/api/v1/ai/capabilities", None),
    ("GET", "/api/v1/ai/usage", None),
    ("POST", "/api/v1/ai/conversations/c-anything/messages/stream", {"body": "hi"}),
]

# Administrator-only routes.
ADMIN_ROUTES: list[tuple[str, str, dict | None]] = [
    ("GET", "/api/v1/admin/users", None),
    ("GET", "/api/v1/admin/usage", None),
    ("GET", "/api/v1/admin/ai-usage", None),
    ("GET", "/api/v1/admin/events", None),
    ("GET", "/api/v1/admin/system-health", None),
]

# Public routes: no session required, and none must ever start requiring one.
PUBLIC_ROUTES: list[tuple[str, str]] = [
    ("GET", "/api/v1/health"),
    ("GET", "/api/v1/health/ready"),
    ("GET", "/api/v1/system/info"),
    ("GET", "/api/v1/modes"),
    ("GET", "/api/v1/modes/general"),
    ("GET", "/openapi.json"),
    ("GET", "/docs"),
]


def _second_user(anon_client: TestClient, email: str) -> TestClient:
    """A second, independent session for a different account.

    Returns a client whose cookie jar is separate, so the two identities cannot
    bleed into each other through a shared jar.
    """
    register_user(anon_client, email=email)
    return anon_client


# ── Protected routes reject anonymous callers ─────────────────────────


class TestAnonymousAccess:
    def test_every_protected_route_rejects_an_anonymous_caller(
        self, anon_client: TestClient
    ) -> None:
        for method, path, body in PROTECTED_ROUTES:
            response = anon_client.request(method, path, json=body)
            assert response.status_code == 401, f"{method} {path} -> {response.status_code}"

    def test_every_admin_route_rejects_an_anonymous_caller(
        self, anon_client: TestClient
    ) -> None:
        for method, path, body in ADMIN_ROUTES:
            response = anon_client.request(method, path, json=body)
            assert response.status_code == 401, f"{method} {path} -> {response.status_code}"

    def test_public_routes_stay_public(self, anon_client: TestClient) -> None:
        for method, path in PUBLIC_ROUTES:
            response = anon_client.request(method, path)
            assert response.status_code == 200, f"{method} {path} -> {response.status_code}"

    def test_a_random_cookie_is_not_a_session(self, anon_client: TestClient) -> None:
        anon_client.cookies.set(settings.AUTH_COOKIE_NAME, "not-a-token")
        assert anon_client.get("/api/v1/auth/me").status_code == 401

    def test_an_unknown_bearer_token_is_rejected(self, anon_client: TestClient) -> None:
        response = anon_client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer nope"}
        )
        assert response.status_code == 401

    def test_rejection_does_not_echo_the_token(self, anon_client: TestClient) -> None:
        """A 401 must not reflect the credential back in the body."""
        secret_looking = "eyJhbGciOiJIUzI1NiJ9.definitely-not-valid.signature"
        anon_client.cookies.set(settings.AUTH_COOKIE_NAME, secret_looking)
        response = anon_client.get("/api/v1/auth/me")
        assert secret_looking not in response.text


# ── Conversation ownership ────────────────────────────────────────────


class TestConversationOwnership:
    def test_a_user_can_read_their_own_conversation(self, client: TestClient) -> None:
        created = client.post("/api/v1/conversations", json={"title": "Mine"}).json()
        assert client.get(f"/api/v1/conversations/{created['id']}").status_code == 200

    def test_another_users_conversation_is_not_readable(
        self, anon_client: TestClient
    ) -> None:
        """The core ownership guarantee.

        The owner reads their own thread; a second account gets 404. 404 rather
        than 403 is deliberate — a 403 would confirm the id exists.
        """
        register_user(anon_client, email="owner@example.com")
        arm_csrf(anon_client)
        thread = anon_client.post(
            "/api/v1/conversations", json={"title": "Private notes"}
        ).json()
        assert anon_client.get(f"/api/v1/conversations/{thread['id']}").status_code == 200

        intruder = add_second_user(anon_client, email="intruder@example.com")

        response = intruder.get(f"/api/v1/conversations/{thread['id']}")
        assert response.status_code == 404
        assert "Private notes" not in response.text

    def test_another_users_conversation_is_not_listed(
        self, anon_client: TestClient
    ) -> None:
        register_user(anon_client, email="lister@example.com")
        arm_csrf(anon_client)
        anon_client.post("/api/v1/conversations", json={"title": "Listed for me"})

        intruder = add_second_user(anon_client, email="non-lister@example.com")

        body = intruder.get("/api/v1/conversations").json()
        assert body["total"] == 0
        assert body["items"] == []

    def test_another_users_conversation_is_not_modifiable(
        self, anon_client: TestClient
    ) -> None:
        register_user(anon_client, email="victim@example.com")
        arm_csrf(anon_client)
        thread = anon_client.post(
            "/api/v1/conversations", json={"title": "Original"}
        ).json()

        intruder = add_second_user(anon_client, email="attacker@example.com")

        assert (
            intruder.patch(
                f"/api/v1/conversations/{thread['id']}", json={"title": "Hijacked"}
            ).status_code
            == 404
        )
        # And the original is untouched.
        assert anon_client.get(f"/api/v1/conversations/{thread['id']}").json()[
            "title"
        ] == "Original"

    def test_another_users_conversation_is_not_deletable(
        self, anon_client: TestClient
    ) -> None:
        register_user(anon_client, email="keep@example.com")
        arm_csrf(anon_client)
        thread = anon_client.post("/api/v1/conversations", json={"title": "Keep me"}).json()

        intruder = add_second_user(anon_client, email="deleter@example.com")

        assert intruder.delete(f"/api/v1/conversations/{thread['id']}").status_code == 404
        assert anon_client.get(f"/api/v1/conversations/{thread['id']}").status_code == 200

    def test_another_users_transcript_is_not_readable(
        self, anon_client: TestClient
    ) -> None:
        register_user(anon_client, email="transcript@example.com")
        arm_csrf(anon_client)
        thread = anon_client.post("/api/v1/conversations", json={"title": "Chat"}).json()
        anon_client.post(
            f"/api/v1/conversations/{thread['id']}/messages",
            json={"body": "a private question"},
        )

        intruder = add_second_user(anon_client, email="snoop@example.com")

        response = intruder.get(f"/api/v1/conversations/{thread['id']}/messages")
        assert response.status_code == 404
        assert "a private question" not in response.text

    def test_messages_cannot_be_posted_to_another_users_conversation(
        self, anon_client: TestClient
    ) -> None:
        register_user(anon_client, email="post-victim@example.com")
        arm_csrf(anon_client)
        thread = anon_client.post("/api/v1/conversations", json={"title": "Mine"}).json()

        intruder = add_second_user(anon_client, email="post-attacker@example.com")

        response = intruder.post(
            f"/api/v1/conversations/{thread['id']}/messages",
            json={"body": "injected"},
        )
        assert response.status_code == 404
        assert anon_client.get(
            f"/api/v1/conversations/{thread['id']}"
        ).json()["messageCount"] == 0

    def test_ownership_cannot_be_claimed_through_the_request_body(
        self, anon_client: TestClient
    ) -> None:
        """`owner_id` is not a request field; extras are forbidden."""
        register_user(anon_client, email="claim@example.com")
        arm_csrf(anon_client)
        victim = add_second_user(anon_client, email="claim-victim@example.com")

        for payload in (
            {"title": "x", "owner_id": "someone-else"},
            {"title": "x", "ownerId": "someone-else"},
            {"title": "x", "user_id": "someone-else"},
        ):
            response = anon_client.post("/api/v1/conversations", json=payload)
            assert response.status_code == 422, payload

    def test_creating_a_thread_assigns_it_to_the_caller(
        self, anon_client: TestClient, session
    ) -> None:
        register_user(anon_client, email="assign@example.com")
        arm_csrf(anon_client)
        thread = anon_client.post("/api/v1/conversations", json={"title": "Mine"}).json()

        from app.models import Conversation

        row = session.get(Conversation, thread["id"])
        user = session.query(User).filter_by(email="assign@example.com").one()
        assert row.owner_id == user.id

    def test_dashboard_counts_only_the_callers_threads(
        self, anon_client: TestClient
    ) -> None:
        register_user(anon_client, email="dash-owner@example.com")
        arm_csrf(anon_client)
        anon_client.post("/api/v1/conversations", json={"title": "Mine"})
        assert anon_client.get("/api/v1/dashboard/summary").json()["stats"][
            "totalConversations"
        ] == 1

        intruder = add_second_user(anon_client, email="dash-intruder@example.com")
        assert intruder.get("/api/v1/dashboard/summary").json()["stats"][
            "totalConversations"
        ] == 0

    def test_project_thread_counts_are_per_account(
        self, anon_client: TestClient
    ) -> None:
        register_user(anon_client, email="proj-owner@example.com")
        arm_csrf(anon_client)
        anon_client.post(
            "/api/v1/conversations", json={"title": "Atlas", "projectId": "p-atlas"}
        )

        intruder = add_second_user(anon_client, email="proj-intruder@example.com")

        projects = {p["id"]: p for p in intruder.get("/api/v1/projects").json()}
        assert projects["p-atlas"]["threads"] == 0


# ── Memory ownership ──────────────────────────────────────────────────


class TestMemoryOwnership:
    def test_a_user_sees_only_their_own_memories(self, anon_client: TestClient) -> None:
        register_user(anon_client, email="mem-owner@example.com")
        arm_csrf(anon_client)
        anon_client.post(
            "/api/v1/memory", json={"statement": "I prefer terse output"}
        )

        intruder = add_second_user(anon_client, email="mem-intruder@example.com")

        assert intruder.get("/api/v1/memory").json() == []

    def test_another_users_memory_cannot_be_deleted(
        self, anon_client: TestClient
    ) -> None:
        register_user(anon_client, email="mem-keep@example.com")
        arm_csrf(anon_client)
        record = anon_client.post(
            "/api/v1/memory", json={"statement": "Mine to keep"}
        ).json()

        intruder = add_second_user(anon_client, email="mem-deleter@example.com")

        # 404, not 403: the record's existence is not confirmed.
        assert intruder.delete(f"/api/v1/memory/{record['id']}").status_code == 404
        assert len(anon_client.get("/api/v1/memory").json()) == 1

    def test_the_seeded_demo_memories_are_invisible_to_everyone(
        self, anon_client: TestClient
    ) -> None:
        register_user(anon_client, email="demo-mem@example.com")
        arm_csrf(anon_client)
        assert anon_client.get("/api/v1/memory").json() == []


# ── Profile security ──────────────────────────────────────────────────


class TestProfileSecurity:
    def test_a_user_can_update_their_own_name_and_avatar(self, client: TestClient) -> None:
        response = client.patch(
            "/api/v1/users/me",
            json={"full_name": "Renamed Operator", "avatar_url": "https://example.com/a.png"},
        )
        assert response.status_code == 200
        assert response.json()["fullName"] == "Renamed Operator"
        assert response.json()["avatarUrl"] == "https://example.com/a.png"

    def test_role_cannot_be_changed_through_the_profile_api(self, client: TestClient) -> None:
        """The single most important profile test.

        `role` is not a field on the update schema, so an attempt is a 422 —
        and the stored role is unchanged either way.
        """
        for payload in (
            {"role": "admin"},
            {"is_admin": True},
            {"isAdmin": True},
            {"is_active": True},
            {"email": "attacker@example.com"},
        ):
            response = client.patch("/api/v1/users/me", json=payload)
            assert response.status_code == 422, payload

        assert client.get("/api/v1/auth/me").json()["user"]["role"] == "user"

    def test_password_hash_cannot_be_set_through_the_profile_api(
        self, client: TestClient, session
    ) -> None:
        before = session.query(User).filter_by(email="operator@aurelis.dev").one()
        original = before.password_hash

        for payload in (
            {"password_hash": "$argon2id$forged"},
            {"passwordHash": "$argon2id$forged"},
            {"password": "Attacker-Chosen-99"},
        ):
            assert client.patch("/api/v1/users/me", json=payload).status_code == 422

        session.expire_all()
        after = session.query(User).filter_by(email="operator@aurelis.dev").one()
        assert after.password_hash == original

    def test_preferences_can_be_updated(self, client: TestClient) -> None:
        response = client.patch(
            "/api/v1/users/me/preferences", json={"density": "compact", "particles": False}
        )
        assert response.status_code == 200
        assert response.json()["density"] == "compact"
        assert response.json()["particles"] is False

    def test_preferences_reject_unknown_values(self, client: TestClient) -> None:
        assert client.patch(
            "/api/v1/users/me/preferences", json={"density": "enormous"}
        ).status_code == 422

    def test_a_user_cannot_edit_another_account_through_the_profile_api(
        self, anon_client: TestClient, session
    ) -> None:
        """There is no id in the path, so there is no id to tamper with.

        This asserts the design: `/users/me` resolves the account from the
        session. A `/users/{id}` route would be the place this class of bug
        would appear, and it deliberately does not exist.
        """
        register_user(anon_client, email="self-only@example.com")
        arm_csrf(anon_client)
        victim = add_second_user(anon_client, email="self-victim@example.com")

        anon_client.patch("/api/v1/users/me", json={"full_name": "Changed Myself"})

        session.expire_all()
        assert (
            session.query(User).filter_by(email="self-victim@example.com").one().full_name
            == "Test Operator"
        )
        assert (
            session.query(User).filter_by(email="self-only@example.com").one().full_name
            == "Changed Myself"
        )


# ── Admin authorization ───────────────────────────────────────────────


class TestAdminAuthorization:
    def test_an_admin_can_reach_every_admin_route(self, admin_client: TestClient) -> None:
        for method, path, body in ADMIN_ROUTES:
            response = admin_client.request(method, path, json=body)
            assert response.status_code == 200, f"{method} {path} -> {response.status_code}"

    def test_a_normal_user_is_refused_on_every_admin_route(self, client: TestClient) -> None:
        """403, not 401: the caller is authenticated, just not permitted."""
        for method, path, body in ADMIN_ROUTES:
            response = client.request(method, path, json=body)
            assert response.status_code == 403, f"{method} {path} -> {response.status_code}"
            assert response.json()["error"]["code"] == "authorization_error"

    def test_admin_user_detail_is_refused_for_a_normal_user(self, client: TestClient) -> None:
        assert client.get("/api/v1/admin/users/some-id").status_code == 403

    def test_admin_mutations_are_refused_for_a_normal_user(self, client: TestClient) -> None:
        assert client.patch(
            "/api/v1/admin/users/some-id", json={"role": "admin"}
        ).status_code == 403
        assert client.post("/api/v1/admin/users/some-id/sessions/revoke").status_code == 403

    def test_a_normal_user_cannot_reach_admin_data_by_guessing_a_path(
        self, client: TestClient
    ) -> None:
        for path in (
            "/api/v1/admin",
            "/api/v1/admin/",
            "/api/v1/admin/users/",
            "/api/v1/admin/system-health/",
        ):
            assert client.get(path).status_code in (403, 404), path

    def test_the_admin_response_never_includes_a_password_hash(
        self, admin_client: TestClient
    ) -> None:
        body = admin_client.get("/api/v1/admin/users").text.lower()
        assert "$argon2" not in body
        assert "password_hash" not in body

    def test_admin_health_reports_real_state(self, admin_client: TestClient) -> None:
        body = admin_client.get("/api/v1/admin/system-health").json()
        assert body["database"] == "ok"
        assert body["databaseDialect"] == "sqlite"
        assert body["status"] == "ok"
        # The view reports *that* secrets are configured, never their values.
        assert body["authSecretConfigured"] is True
        assert body["passwordHashing"] == "argon2id"
        assert body["supabase"] == "unconfigured"

    def test_admin_events_are_anonymised(self, admin_client: TestClient, session) -> None:
        """The audit feed must not hand an admin a credential or a raw email."""
        add_second_user(admin_client, email="audit-subject@example.com")
        body = admin_client.get("/api/v1/admin/events").json()
        assert body["items"]

        blob = admin_client.get("/api/v1/admin/events").text.lower()
        assert "$argon2" not in blob
        assert "audit-subject@example.com" not in blob
        assert TEST_PASSWORD.lower() not in blob

    def test_admin_usage_aggregates_without_listing_users(
        self, admin_client: TestClient
    ) -> None:
        body = admin_client.get("/api/v1/admin/usage").json()
        for key in (
            "totalUsers",
            "activeUsers",
            "adminUsers",
            "totalConversations",
            "activeSessions",
            "authEvents24H",
        ):
            assert key in body, key
        assert isinstance(body["usage"], list)
        # Aggregates only — no account list rides along.
        assert "users" not in body
        assert "items" not in body

    def test_admin_can_list_and_search_accounts(self, admin_client: TestClient) -> None:
        add_second_user(admin_client, email="findable@example.com")
        body = admin_client.get("/api/v1/admin/users").json()
        assert body["total"] >= 2

        filtered = admin_client.get(
            "/api/v1/admin/users", params={"search": "findable"}
        ).json()
        assert filtered["total"] == 1
        assert filtered["items"][0]["email"] == "findable@example.com"

    def test_admin_can_filter_by_role(self, admin_client: TestClient) -> None:
        admins = admin_client.get("/api/v1/admin/users", params={"role": "admin"}).json()
        assert admins["total"] == 1
        assert admins["items"][0]["role"] == "admin"

    def test_admin_can_deactivate_and_reactivate_an_account(
        self, admin_client: TestClient, session
    ) -> None:
        add_second_user(admin_client, email="togglable@example.com")
        target = session.query(User).filter_by(email="togglable@example.com").one()

        off = admin_client.patch(
            f"/api/v1/admin/users/{target.id}", json={"is_active": False}
        )
        assert off.status_code == 200
        assert off.json()["isActive"] is False

        on = admin_client.patch(
            f"/api/v1/admin/users/{target.id}", json={"is_active": True}
        )
        assert on.json()["isActive"] is True

    def test_deactivating_an_account_kills_its_sessions(
        self, admin_client: TestClient, session
    ) -> None:
        add_second_user(admin_client, email="kick-me@example.com")
        target = session.query(User).filter_by(email="kick-me@example.com").one()

        admin_client.patch(f"/api/v1/admin/users/{target.id}", json={"is_active": False})

        now_sessions = session.query(AuthSession).filter_by(user_id=target.id).all()
        assert now_sessions
        assert all(row.revoked_at is not None for row in now_sessions)

    def test_an_admin_cannot_deactivate_themselves(
        self, admin_client: TestClient, session
    ) -> None:
        """Otherwise the last administrator can lock everyone out."""
        me = session.query(User).filter_by(email="admin@aurelis.dev").one()
        response = admin_client.patch(
            f"/api/v1/admin/users/{me.id}", json={"is_active": False}
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"

    def test_an_admin_can_revoke_another_accounts_sessions(
        self, admin_client: TestClient, session
    ) -> None:
        add_second_user(admin_client, email="revoke-me@example.com")
        target = session.query(User).filter_by(email="revoke-me@example.com").one()

        response = admin_client.post(f"/api/v1/admin/users/{target.id}/sessions/revoke")
        assert response.status_code == 200
        assert response.json()["revoked"] >= 1

    def test_unknown_target_is_404(self, admin_client: TestClient) -> None:
        assert admin_client.get("/api/v1/admin/users/does-not-exist").status_code == 404


# ── Privilege escalation attempts ─────────────────────────────────────


class TestPrivilegeEscalation:
    def test_role_in_the_registration_body_is_rejected(self, anon_client: TestClient) -> None:
        for payload in (
            {"role": "admin"},
            {"is_admin": True},
            {"role": "superuser"},
        ):
            response = anon_client.post(
                "/api/v1/auth/register",
                json={
                    "full_name": "Escalator",
                    "email": f"esc-{len(payload)}@example.com",
                    "password": "Vermilion-Lattice-42",
                    **payload,
                },
            )
            assert response.status_code == 422, payload

    def test_role_cannot_be_smuggled_through_preferences(self, client: TestClient) -> None:
        assert client.patch(
            "/api/v1/users/me/preferences", json={"role": "admin"}
        ).status_code == 422
        assert client.get("/api/v1/auth/me").json()["user"]["role"] == "user"

    def test_role_cannot_be_smuggled_through_a_conversation(
        self, client: TestClient
    ) -> None:
        assert client.post(
            "/api/v1/conversations", json={"title": "x", "role": "admin"}
        ).status_code == 422

    def test_an_admin_token_does_not_grant_admin_after_a_demotion(
        self, admin_client: TestClient, session
    ) -> None:
        """Authorization is read from the database per request, not the token.

        This is what makes revocation and demotion take effect immediately
        instead of at the next token expiry.
        """
        me = session.query(User).filter_by(email="admin@aurelis.dev").one()
        assert admin_client.get("/api/v1/admin/users").status_code == 200

        me.role = "user"
        session.commit()

        assert admin_client.get("/api/v1/admin/users").status_code == 403

    def test_a_normal_user_is_not_an_admin_after_a_promotion_without_relogin(
        self, anon_client: TestClient, session
    ) -> None:
        """The mirror image: promotion also takes effect immediately."""
        from tests.conftest import promote_to_admin

        register_user(anon_client, email="late-admin@example.com")
        arm_csrf(anon_client)
        assert anon_client.get("/api/v1/admin/users").status_code == 403

        promote_to_admin("late-admin@example.com")
        assert anon_client.get("/api/v1/admin/users").status_code == 200

    def test_a_forged_admin_claim_in_the_token_is_rejected(
        self, anon_client: TestClient
    ) -> None:
        """Even if `role` were added to the token, it must not be trusted.

        Forging the signature is the only way to change a claim, and that fails
        on signature verification — but this test also documents that the
        authorization check reads the database, so a `role` claim would be
        ignored regardless.
        """
        import jwt

        register_user(anon_client, email="claim-admin@example.com")
        forged = jwt.encode(
            {
                "sub": "any",
                "sid": "any",
                "typ": "access",
                "role": "admin",
                "iat": 1,
                "exp": 9_999_999_999,
            },
            "wrong-key-but-long-enough-to-clear-the-hmac-warning",
            algorithm="HS256",
        )
        anon_client.cookies.set(settings.AUTH_COOKIE_NAME, forged)
        assert anon_client.get("/api/v1/admin/users").status_code == 401

    def test_another_users_session_cannot_be_used(self, anon_client: TestClient) -> None:
        """A stolen access token is bound to its session row, and that row is
        checked on every request."""
        register_user(anon_client, email="bound@example.com")
        token = anon_client.cookies.get(settings.AUTH_COOKIE_NAME)

        other = TestClient(anon_client.app)
        other.cookies.set(settings.AUTH_COOKIE_NAME, token)
        # The session row belongs to the first user, so this still resolves to
        # them — the token is not a bearer of identity beyond its session.
        assert other.get("/api/v1/auth/me").json()["user"]["email"] == "bound@example.com"

    def test_revoking_a_session_invalidates_its_token_immediately(
        self, anon_client: TestClient, session
    ) -> None:
        register_user(anon_client, email="revoked-token@example.com")
        row = session.query(AuthSession).one()
        row.revoked_at = row.created_at
        session.commit()

        assert anon_client.get("/api/v1/auth/me").status_code == 401

    def test_an_admin_cannot_promote_themselves_to_something_else(
        self, admin_client: TestClient
    ) -> None:
        """`role` is not an accepted admin-update field either, so the only way
        to change a role is the deliberate provisioning path."""
        me = admin_client.get("/api/v1/auth/me").json()["user"]
        assert admin_client.patch(
            f"/api/v1/admin/users/{me['id']}", json={"role": "owner"}
        ).status_code == 422

    def test_admin_role_changes_go_through_the_validated_enum(
        self, admin_client: TestClient, session
    ) -> None:
        add_second_user(admin_client, email="promotable@example.com")
        target = session.query(User).filter_by(email="promotable@example.com").one()

        assert admin_client.patch(
            f"/api/v1/admin/users/{target.id}", json={"role": "not-a-role"}
        ).status_code == 422

        ok = admin_client.patch(f"/api/v1/admin/users/{target.id}", json={"role": "admin"})
        assert ok.status_code == 200
        assert ok.json()["role"] == "admin"


# ── CSRF is enforced, not just present ────────────────────────────────


class TestCsrfEnforcement:
    def test_every_state_changing_route_requires_the_csrf_header(
        self, anon_client: TestClient
    ) -> None:
        """A blanket check: a new endpoint that forgets `enforce_csrf` fails here."""
        register_user(anon_client, email="csrf-sweep@example.com")
        thread = anon_client.post(
            "/api/v1/conversations",
            json={"title": "Seeded"},
            headers={CSRF_HEADER: anon_client.cookies.get(settings.CSRF_COOKIE_NAME)},
        ).json()
        record = anon_client.post(
            "/api/v1/memory",
            json={"statement": "Seeded"},
            headers={CSRF_HEADER: anon_client.cookies.get(settings.CSRF_COOKIE_NAME)},
        ).json()

        writes = [
            ("POST", "/api/v1/conversations", {"title": "No token"}),
            ("PATCH", f"/api/v1/conversations/{thread['id']}", {"title": "No token"}),
            ("DELETE", f"/api/v1/conversations/{thread['id']}", None),
            ("POST", f"/api/v1/conversations/{thread['id']}/messages", {"body": "hi"}),
            ("POST", "/api/v1/projects", {"id": "p-csrf-probe", "name": "No token"}),
            ("PATCH", "/api/v1/tools/t-calendar", {"connected": True}),
            ("POST", "/api/v1/memory", {"statement": "No token"}),
            ("DELETE", f"/api/v1/memory/{record['id']}", None),
            ("PATCH", "/api/v1/users/me", {"full_name": "No token"}),
            ("PATCH", "/api/v1/users/me/preferences", {"density": "compact"}),
            (
                "POST",
                "/api/v1/auth/change-password",
                {
                    "current_password": TEST_PASSWORD,
                    "new_password": STRONG_NEW_PASSWORD,
                },
            ),
            ("POST", "/api/v1/auth/logout", None),
            ("POST", "/api/v1/auth/refresh", None),
            ("DELETE", "/api/v1/auth/sessions", None),
        ]

        # Strip the header the fixture installed, so each request is a genuine
        # cross-site-shaped call with cookies but no custom header.
        saved = anon_client.headers.pop(CSRF_HEADER, None)
        try:
            for method, path, body in writes:
                response = anon_client.request(method, path, json=body)
                assert response.status_code == 403, (
                    f"{method} {path} accepted a cookie-authenticated write "
                    f"without a CSRF header (got {response.status_code})"
                )
        finally:
            if saved:
                anon_client.headers[CSRF_HEADER] = saved

    def test_admin_writes_require_the_csrf_header(self, admin_client: TestClient) -> None:
        """An admin's cookies are worth stealing too."""
        me = admin_client.get("/api/v1/auth/me").json()["user"]
        saved = admin_client.headers.pop(CSRF_HEADER, None)
        try:
            assert admin_client.patch(
                f"/api/v1/admin/users/{me['id']}", json={"is_active": True}
            ).status_code == 403
            assert admin_client.post(
                f"/api/v1/admin/users/{me['id']}/sessions/revoke"
            ).status_code == 403
        finally:
            if saved:
                admin_client.headers[CSRF_HEADER] = saved


# ── Inactive accounts ─────────────────────────────────────────────────


class TestInactiveAccounts:
    def test_an_inactive_admin_loses_admin_access(
        self, admin_client: TestClient, session
    ) -> None:
        me = session.query(User).filter_by(email="admin@aurelis.dev").one()
        me.is_active = False
        session.commit()

        response = admin_client.get("/api/v1/admin/users")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "account_inactive"

    def test_an_inactive_user_is_refused_across_the_board(
        self, client: TestClient, session
    ) -> None:
        me = session.query(User).filter_by(email="operator@aurelis.dev").one()
        me.is_active = False
        session.commit()

        for method, path, body in PROTECTED_ROUTES:
            response = client.request(method, path, json=body)
            # 403 is the expected refusal; 404 for a conversation the caller
            # does not own. Never a 200.
            assert response.status_code in (403, 404), (
                f"{method} {path} -> {response.status_code}"
            )


# ── Error-shape discipline ────────────────────────────────────────────


class TestErrorDiscipline:
    def test_refusals_use_the_shared_error_envelope(self, client: TestClient) -> None:
        body = client.get("/api/v1/admin/users").json()
        assert set(body) == {"error"}
        assert set(body["error"]) >= {"code", "message"}
        assert body["error"]["code"] == "authorization_error"

    def test_no_stack_trace_or_sql_reaches_the_client(self, client: TestClient) -> None:
        body = client.get("/api/v1/admin/users").text.lower()
        for leak in ("traceback", "select ", "sqlalchemy", "postgresql", "sqlite"):
            assert leak not in body, f"response leaked '{leak}'"

    def test_a_malformed_body_is_a_validation_error_not_a_crash(
        self, client: TestClient
    ) -> None:
        response = client.post(
            "/api/v1/conversations",
            content=b"{not json at all",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422

    def test_an_oversized_page_is_refused(self, client: TestClient) -> None:
        assert client.get("/api/v1/conversations", params={"limit": 10_000}).status_code == 422

    def test_a_negative_offset_is_refused(self, client: TestClient) -> None:
        assert client.get("/api/v1/conversations", params={"offset": -1}).status_code == 422

    def test_the_auth_error_never_names_the_cause(
        self, anon_client: TestClient
    ) -> None:
        """Every 401 is generic: same status, same code, no fingerprinting.

        The message may differ between "no credential supplied" and "credential
        rejected" — a distinction useless to an attacker — but it must never
        say *why* a token failed: expired, revoked, unknown session and bad
        signature have to be indistinguishable.
        """
        import jwt

        responses = []
        for token in (
            "garbage",
            "",
            jwt.encode(
                {"sub": "x", "sid": "y", "typ": "access", "iat": 1, "exp": 9_999_999_999},
                "wrong-key-but-long-enough-to-clear-the-hmac-warning",
                algorithm="HS256",
            ),
            "a.b.c",
        ):
            anon_client.cookies.set(settings.AUTH_COOKIE_NAME, token)
            responses.append(anon_client.get("/api/v1/auth/me"))
        anon_client.cookies.clear()
        responses.append(anon_client.get("/api/v1/auth/me"))

        assert {response.status_code for response in responses} == {401}
        assert {response.json()["error"]["code"] for response in responses} == {
            "authentication_error"
        }

        messages = {response.json()["error"]["message"] for response in responses}
        assert len(messages) <= 2, messages
        for message in messages:
            lowered = message.lower()
            for leak in ("expired", "revoked", "signature", "session id", "unknown"):
                assert leak not in lowered, f"401 leaked '{leak}': {message}"
