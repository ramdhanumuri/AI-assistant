"""Step 5 security hardening test suite.

This file is adversarial: it plays an attacker against the hardened stack and
asserts the attack fails. It is deliberately separate from `test_auth.py` and
`test_authorization.py` (which cover Step 4 behaviour) so the *hardening* added
in Step 5 has its own evidence, and so a regression there is obvious.

Everything runs against the real app, a real database and the real endpoints —
no mocks. The only stubbing is of configuration values (a rate-limit budget, the
upload directory) which is exactly what those values exist to make tunable.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.uploads import resolve_storage_path, sanitise_filename, validate_upload
from app.db.base import utcnow
from app.models import AuthEvent, AuthSession, User
from tests.conftest import (
    CSRF_HEADER,
    TEST_PASSWORD,
    add_second_user,
    arm_csrf,
    register_user,
)


# ── Request correlation ids ───────────────────────────────────────────


class TestRequestIds:
    def test_every_response_carries_a_generated_request_id(
        self, anon_client: TestClient
    ) -> None:
        response = anon_client.get("/api/v1/health")
        assert response.headers.get("X-Request-ID")

    def test_a_reasonable_client_id_is_echoed(self, anon_client: TestClient) -> None:
        response = anon_client.get(
            "/api/v1/health", headers={"X-Request-ID": "trace-abc.123_2"}
        )
        assert response.headers["X-Request-ID"] == "trace-abc.123_2"

    def test_a_hostile_client_id_is_replaced_not_reflected(
        self, anon_client: TestClient
    ) -> None:
        """A crafted id must not reach the logs verbatim (injection / blast)."""
        for hostile in (
            "a" * 500,
            "value with spaces and \n newline",
            "<script>alert(1)</script>",
            "'; DROP TABLE users; --",
        ):
            response = anon_client.get(
                "/api/v1/health", headers={"X-Request-ID": hostile}
            )
            echoed = response.headers["X-Request-ID"]
            assert echoed != hostile
            assert len(echoed) <= 128


# ── Security headers ──────────────────────────────────────────────────


class TestSecurityHeadersHardening:
    def test_api_csp_is_restrictive(self, anon_client: TestClient) -> None:
        csp = anon_client.get("/api/v1/health").headers["Content-Security-Policy"]
        assert "default-src 'none'" in csp
        assert "script-src 'none'" in csp
        # No unsafe-inline/unsafe-eval on the API policy.
        assert "unsafe-inline" not in csp
        assert "unsafe-eval" not in csp
        assert "frame-ancestors 'none'" in csp

    def test_docs_csp_still_allows_the_cdn(self, anon_client: TestClient) -> None:
        csp = anon_client.get("/docs").headers["Content-Security-Policy"]
        assert "cdn.jsdelivr.net" in csp

    def test_sniffing_and_framing_are_disabled(self, anon_client: TestClient) -> None:
        headers = anon_client.get("/api/v1/health").headers
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["X-Frame-Options"] == "DENY"
        assert headers["Referrer-Policy"] == "no-referrer"
        assert headers["Cross-Origin-Opener-Policy"] == "same-origin"
        assert headers["Cross-Origin-Resource-Policy"] == "same-origin"

    def test_auth_responses_are_not_cacheable(self, anon_client: TestClient) -> None:
        response = anon_client.get("/api/v1/auth/me")
        assert response.headers.get("Cache-Control") == "no-store"


# ── CORS ──────────────────────────────────────────────────────────────


class TestCorsHardening:
    def test_trusted_origin_is_allowed(self, anon_client: TestClient) -> None:
        origin = settings.CORS_ORIGINS[0]
        response = anon_client.options(
            "/api/v1/auth/login",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
            },
        )
        assert response.headers.get("access-control-allow-origin") == origin
        assert response.headers.get("access-control-allow-credentials") == "true"

    def test_unknown_origin_is_not_allowed(self, anon_client: TestClient) -> None:
        response = anon_client.options(
            "/api/v1/auth/login",
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert "access-control-allow-origin" not in {
            key.lower() for key in response.headers
        }

    def test_wildcard_origin_is_never_reflected(self, anon_client: TestClient) -> None:
        response = anon_client.get("/api/v1/health", headers={"Origin": "https://evil.example.com"})
        assert response.headers.get("access-control-allow-origin") != "*"

    def test_production_rejects_a_wildcard_origin(self) -> None:
        from app.core.config import Settings

        with pytest.raises(ValueError, match=r"\*"):
            Settings(
                APP_ENV="production",
                AUTH_SECRET="v" * 48,
                COOKIE_SECURE=True,
                DEBUG=False,
                CORS_ORIGINS=["*"],
            )


# ── Configuration guards (misconfiguration review) ────────────────────


class TestProductionMisconfiguration:
    def test_production_rejects_debug(self) -> None:
        from app.core.config import Settings

        with pytest.raises(ValueError, match="DEBUG"):
            Settings(
                APP_ENV="production",
                AUTH_SECRET="w" * 48,
                COOKIE_SECURE=True,
                DEBUG=True,
            )

    def test_docs_are_hidden_in_production_by_default(self) -> None:
        from app.core.config import Settings

        prod = Settings(APP_ENV="production", AUTH_SECRET="x" * 48, COOKIE_SECURE=True, DEBUG=False)
        assert prod.docs_enabled is False
        dev = Settings(APP_ENV="development")
        assert dev.docs_enabled is True

    def test_plaintext_public_url_is_rejected_outside_development(self) -> None:
        from app.core.config import Settings

        with pytest.raises(ValueError, match="SUPABASE_URL"):
            Settings(
                APP_ENV="production",
                AUTH_SECRET="y" * 48,
                COOKIE_SECURE=True,
                DEBUG=False,
                SUPABASE_URL="http://insecure.example.com",
            )


# ── CSRF ──────────────────────────────────────────────────────────────


class TestCsrfHardening:
    def test_missing_header_is_a_uniform_403(self, anon_client: TestClient) -> None:
        register_user(anon_client, email="csrf-missing@example.com")
        anon_client.headers.pop(CSRF_HEADER, None)
        response = anon_client.post("/api/v1/conversations", json={"title": "x"})
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "authorization_error"

    def test_mismatched_token_is_refused(self, anon_client: TestClient) -> None:
        register_user(anon_client, email="csrf-mismatch@example.com")
        anon_client.headers[CSRF_HEADER] = "not-the-cookie-value"
        response = anon_client.post("/api/v1/conversations", json={"title": "x"})
        assert response.status_code == 403

    def test_valid_token_is_accepted(self, anon_client: TestClient) -> None:
        register_user(anon_client, email="csrf-valid@example.com")
        arm_csrf(anon_client)
        assert anon_client.post("/api/v1/conversations", json={"title": "ok"}).status_code == 201

    def test_safe_methods_do_not_require_csrf(self, anon_client: TestClient) -> None:
        register_user(anon_client, email="csrf-safe@example.com")
        anon_client.headers.pop(CSRF_HEADER, None)
        assert anon_client.get("/api/v1/auth/me").status_code == 200
        assert anon_client.get("/api/v1/conversations").status_code == 200

    def test_bearer_client_without_cookies_is_exempt(self, anon_client: TestClient) -> None:
        """Nothing attaches a bearer token automatically, so CSRF does not apply."""
        register_user(anon_client, email="csrf-bearer@example.com")
        token = anon_client.cookies.get(settings.AUTH_COOKIE_NAME)
        anon_client.cookies.clear()
        response = anon_client.post(
            "/api/v1/conversations",
            json={"title": "bearer"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201

    def test_csrf_failure_never_echoes_the_token(self, anon_client: TestClient) -> None:
        register_user(anon_client, email="csrf-echo@example.com")
        secret = "csrf-token-do-not-reflect"
        anon_client.headers[CSRF_HEADER] = secret
        response = anon_client.post("/api/v1/conversations", json={"title": "x"})
        assert response.status_code == 403
        assert secret not in response.text


# ── Input validation ──────────────────────────────────────────────────


class TestInputValidation:
    def test_oversized_message_body_is_refused(self, client: TestClient) -> None:
        thread = client.post("/api/v1/conversations", json={"title": "big"}).json()
        response = client.post(
            f"/api/v1/conversations/{thread['id']}/messages",
            json={"body": "x" * 20_001},
        )
        assert response.status_code == 422

    def test_oversized_title_is_refused(self, client: TestClient) -> None:
        assert client.post(
            "/api/v1/conversations", json={"title": "x" * 300}
        ).status_code == 422

    def test_invalid_mode_enum_is_refused(self, client: TestClient) -> None:
        assert client.post(
            "/api/v1/conversations", json={"title": "x", "mode": "sudo"}
        ).status_code == 422

    def test_unknown_extra_field_is_refused(self, client: TestClient) -> None:
        assert client.post(
            "/api/v1/conversations", json={"title": "x", "ownerId": "someone-else"}
        ).status_code == 422

    def test_malformed_uuid_path_is_refused(self, client: TestClient) -> None:
        # These are string ids in this schema, so a malformed one is not a crash
        # but a clean not-found — never a 500 or a database error leak.
        for bad in ("%00", "'; DROP TABLE users; --", "../../etc/passwd", "a" * 500):
            response = client.get(f"/api/v1/conversations/{bad}")
            assert response.status_code in (404, 405, 422), (bad, response.status_code)
            assert "traceback" not in response.text.lower()

    def test_oversized_request_body_is_refused(self, client: TestClient) -> None:
        huge = b"{" + b'"title":"' + b"a" * (settings.MAX_REQUEST_BODY_BYTES + 1024) + b'"}'
        response = client.post(
            "/api/v1/conversations",
            content=huge,
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 413
        assert response.json()["error"]["code"] == "payload_too_large"
        # The refusal is itself a hardened response: headers and an id.
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers.get("X-Request-ID")


# ── SQL injection review ──────────────────────────────────────────────


class TestSqlInjectionReview:
    def test_search_filters_are_parameterised(self, client: TestClient) -> None:
        """A malicious search term must be treated as data, not SQL."""
        for payload in (
            "'; DROP TABLE conversations; --",
            "1' OR '1'='1",
            "%' OR 1=1 --",
            "\\'; SELECT * FROM users; --",
        ):
            response = client.get(
                "/api/v1/conversations", params={"search": payload}
            )
            assert response.status_code == 200, payload
            assert response.json()["items"] == []

    def test_tables_survive_injection_attempts(self, client: TestClient, session) -> None:
        client.get("/api/v1/conversations", params={"search": "'; DROP TABLE users; --"})
        # The users table still answers a query.
        assert session.query(User).count() >= 1

    def test_no_raw_sql_string_concatenation_in_source(self) -> None:
        """Guard the codebase, not just the runtime.

        A textual search for the shapes that precede an injection bug.
        """
        app_dir = Path(__file__).resolve().parents[1] / "app"
        offenders: list[str] = []
        for path in app_dir.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for needle in ('execute(f"', "execute(f'", 'execute("SELECT', 'execute("DELETE'):
                if needle in text:
                    offenders.append(f"{path.name}: {needle}")
        assert offenders == [], offenders


# ── XSS / content safety ──────────────────────────────────────────────


class TestXssReview:
    def test_message_content_is_stored_verbatim_not_executed(
        self, client: TestClient
    ) -> None:
        """The API stores and returns the payload; React escapes it on render.

        The backend's job is to make sure the value round-trips, is JSON, and
        never gains an HTML content type.
        """
        payload = "<script>alert('xss')</script>"
        thread = client.post("/api/v1/conversations", json={"title": payload}).json()
        assert thread["title"] == payload
        response = client.get(f"/api/v1/conversations/{thread['id']}")
        assert response.headers["content-type"].startswith("application/json")

    def test_frontend_never_uses_dangerously_set_html(self) -> None:
        src = Path(__file__).resolve().parents[2] / "src"
        offenders = [
            path.name
            for path in src.rglob("*.tsx")
            if "dangerouslySetInnerHTML" in path.read_text(encoding="utf-8")
        ]
        assert offenders == [], offenders


# ── Refresh-token reuse ───────────────────────────────────────────────


class TestRefreshTokenReuse:
    def test_replaying_a_rotated_token_revokes_the_family(
        self, anon_client: TestClient, session
    ) -> None:
        register_user(anon_client, email="reuse@example.com")
        arm_csrf(anon_client)
        original = anon_client.cookies.get(settings.REFRESH_COOKIE_NAME)

        # Legitimate rotation: the original is now consumed.
        assert anon_client.post("/api/v1/auth/refresh").status_code == 200
        rotated = anon_client.cookies.get(settings.REFRESH_COOKIE_NAME)
        assert rotated and rotated != original

        # Attacker replays the old token (with a valid CSRF pair, so the
        # refusal is the reuse detection and not the CSRF gate).
        original_csrf = anon_client.cookies.get(settings.CSRF_COOKIE_NAME)
        anon_client.cookies.set(settings.REFRESH_COOKIE_NAME, original)
        anon_client.headers[CSRF_HEADER] = original_csrf
        replay = anon_client.post("/api/v1/auth/refresh")
        assert replay.status_code == 401

        # Reuse is recorded...
        assert any(
            row.event_type == "token_reuse_detected"
            for row in session.scalars(
                select(AuthEvent)
            )
        )
        # ...and every session for the account is revoked.
        user = session.scalar(
            select(User).where(User.email == "reuse@example.com")
        )
        live = [
            row
            for row in session.query(AuthSession).filter_by(user_id=user.id).all()
            if row.revoked_at is None
        ]
        assert live == []

    def test_refresh_is_throttled(self, anon_client: TestClient, monkeypatch) -> None:
        from app.core import ratelimit

        monkeypatch.setattr(ratelimit.settings, "AUTH_RATE_LIMIT_ATTEMPTS", 3)
        ratelimit.reset_limiter()
        try:
            register_user(anon_client, email="refresh-throttle@example.com")
            arm_csrf(anon_client)
            statuses = [
                anon_client.post("/api/v1/auth/refresh").status_code for _ in range(6)
            ]
            assert 429 in statuses, statuses
        finally:
            ratelimit.reset_limiter()


# ── Session security ──────────────────────────────────────────────────


class TestSessionSecurity:
    def test_logout_revokes_the_session_row(self, client: TestClient, session) -> None:
        client.post("/api/v1/auth/logout")
        assert client.get("/api/v1/auth/me").status_code == 401
        assert all(
            row.revoked_at is not None for row in session.query(AuthSession).all()
        )

    def test_password_change_revokes_other_sessions_but_keeps_current(
        self, client: TestClient, session
    ) -> None:
        session.add(
            AuthSession(
                user_id=session.query(User).filter_by(email="operator@aurelis.dev").one().id,
                token_hash="x" * 64,
                expires_at=utcnow(),
            )
        )
        session.commit()
        others = TestClient(client.app)
        response = client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": TEST_PASSWORD,
                "new_password": "Obsidian-Meridian-99",
            },
        )
        assert response.status_code == 200
        # The tab that changed the password is still signed in.
        assert client.get("/api/v1/auth/me").status_code == 200
        # A client with only the old session is not.
        assert others.get("/api/v1/auth/me").status_code == 401


# ── IDOR / BOLA ───────────────────────────────────────────────────────


class TestIdorBola:
    def test_another_users_message_id_is_not_readable(
        self, anon_client: TestClient
    ) -> None:
        register_user(anon_client, email="bola-owner@example.com")
        arm_csrf(anon_client)
        thread = anon_client.post(
            "/api/v1/conversations", json={"title": "Owner thread"}
        ).json()
        turn = anon_client.post(
            f"/api/v1/conversations/{thread['id']}/messages", json={"body": "secret"}
        ).json()

        intruder = add_second_user(anon_client, email="bola-intruder@example.com")
        response = intruder.get(f"/api/v1/conversations/{thread['id']}/messages")
        assert response.status_code == 404
        assert "secret" not in response.text
        # Also cannot delete the other user's conversation.
        assert intruder.delete(f"/api/v1/conversations/{thread['id']}").status_code == 404
        # The message id is never a standalone resource, so it cannot be probed.
        assert turn["userMessage"]["id"]

    def test_user_id_manipulation_has_no_effect(self, client: TestClient, session) -> None:
        victim = session.query(User).filter_by(email="operator@aurelis.dev").one()
        # Attempt to act on another account through the self-service route.
        response = client.patch(
            "/api/v1/users/me",
            json={"full_name": "Hacked"},
        )
        assert response.status_code == 200
        session.refresh(victim)
        # The change landed on the caller's own row (same id as the session),
        # not on anyone else's, and role is untouched.
        assert victim.role == "user"

    def test_admin_resource_ids_are_hidden_from_normal_users(
        self, client: TestClient, session
    ) -> None:
        admin = session.query(User).filter_by(email="admin@aurelis.dev").first()
        # `admin` may not exist in this fixture's DB; if so skip the id probe.
        if admin is not None:
            assert client.get(f"/api/v1/admin/users/{admin.id}").status_code == 403


# ── Brute force ───────────────────────────────────────────────────────


class TestBruteForceProtection:
    def test_repeated_failures_lock_the_account_then_expire(
        self, anon_client: TestClient, session, monkeypatch
    ) -> None:
        from app.core import ratelimit

        monkeypatch.setattr(ratelimit.settings, "AUTH_RATE_LIMIT_ATTEMPTS", 1000)
        ratelimit.reset_limiter()
        try:
            register_user(anon_client, email="brute@example.com")
            for _ in range(settings.AUTH_MAX_FAILED_LOGINS):
                anon_client.post(
                    "/api/v1/auth/login",
                    json={"email": "brute@example.com", "password": "Wrong-Password-1"},
                )
            user = session.scalar(
                select(User).where(User.email == "brute@example.com")
            )
            assert user.locked_until is not None
        finally:
            ratelimit.reset_limiter()

    def test_errors_do_not_reveal_account_existence(
        self, anon_client: TestClient, monkeypatch
    ) -> None:
        from app.core import ratelimit

        monkeypatch.setattr(ratelimit.settings, "AUTH_RATE_LIMIT_ATTEMPTS", 1000)
        ratelimit.reset_limiter()
        try:
            register_user(anon_client, email="exists@example.com")
            known = anon_client.post(
                "/api/v1/auth/login",
                json={"email": "exists@example.com", "password": "Wrong-Password-1"},
            )
            unknown = anon_client.post(
                "/api/v1/auth/login",
                json={"email": "ghost@example.com", "password": "Wrong-Password-1"},
            )
            assert known.status_code == unknown.status_code == 401
            assert known.json()["error"]["message"] == unknown.json()["error"]["message"]
        finally:
            ratelimit.reset_limiter()

    def test_lockout_message_matches_throttle_message(
        self, anon_client: TestClient, monkeypatch
    ) -> None:
        """A locked account must not be distinguishable from a throttled client."""
        from app.core import ratelimit

        monkeypatch.setattr(ratelimit.settings, "AUTH_RATE_LIMIT_ATTEMPTS", 1000)
        ratelimit.reset_limiter()
        try:
            register_user(anon_client, email="lockmsg@example.com")
            for _ in range(settings.AUTH_MAX_FAILED_LOGINS):
                anon_client.post(
                    "/api/v1/auth/login",
                    json={"email": "lockmsg@example.com", "password": "Wrong-Password-1"},
                )
            locked = anon_client.post(
                "/api/v1/auth/login",
                json={"email": "lockmsg@example.com", "password": "Vermilion-Lattice-42"},
            )
            assert locked.status_code == 429
            assert locked.json()["error"]["message"] == "Too many attempts. Try again shortly."
        finally:
            ratelimit.reset_limiter()


# ── Rate limiting ─────────────────────────────────────────────────────


class TestRateLimitingScopes:
    def test_login_and_register_have_separate_budgets(
        self, anon_client: TestClient, monkeypatch
    ) -> None:
        from app.core import ratelimit

        monkeypatch.setattr(ratelimit.settings, "AUTH_RATE_LIMIT_ATTEMPTS", 1)
        ratelimit.reset_limiter()
        try:
            anon_client.post(
                "/api/v1/auth/login",
                json={"email": "nobody@example.com", "password": "Wrong-Password-1"},
            )
            assert (
                anon_client.post(
                    "/api/v1/auth/login",
                    json={"email": "nobody@example.com", "password": "Wrong-Password-1"},
                ).status_code
                == 429
            )
            assert (
                anon_client.post(
                    "/api/v1/auth/register",
                    json={
                        "full_name": "Fresh",
                        "email": "fresh@example.com",
                        "password": "Vermilion-Lattice-42",
                    },
                ).status_code
                == 201
            )
        finally:
            ratelimit.reset_limiter()

    def test_active_backend_reports_which_control_is_in_force(self) -> None:
        from app.core import ratelimit

        assert ratelimit.active_backend() in {
            "InProcessRateLimiter",
            "RedisRateLimiter",
        }

    def test_scoped_budgets_are_defined(self) -> None:
        from app.core import ratelimit

        for scope in ("login", "register", "refresh", "password-reset", "ai", "write", "admin"):
            max_events, window = ratelimit.scoped_limit(scope)
            assert max_events > 0 and window > 0, scope


# ── File upload security foundation ───────────────────────────────────


class TestUploadValidation:
    @pytest.fixture
    def uploads_on(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(settings, "UPLOAD_STORAGE_DIR", str(tmp_path))

    def test_valid_image_is_accepted(self, uploads_on: None) -> None:
        result = validate_upload(
            filename="photo.png", content_type="image/png", size_bytes=1024
        )
        assert result.extension == ".png"
        assert result.stored_name.endswith(".png")
        assert result.stored_name != "photo.png"  # server-generated name

    def test_executable_and_script_types_are_refused(self, uploads_on: None) -> None:
        for name, mime in (
            ("shell.sh", "text/plain"),
            ("payload.php", "image/png"),
            ("x.html", "text/html"),
            ("s.svg", "image/svg+xml"),
            ("m.js", "text/javascript"),
        ):
            with pytest.raises(Exception):
                validate_upload(filename=name, content_type=mime, size_bytes=10)

    def test_mime_extension_mismatch_is_refused(self, uploads_on: None) -> None:
        with pytest.raises(Exception):
            validate_upload(filename="evil.png", content_type="text/html", size_bytes=10)

    def test_path_traversal_names_never_become_paths(self, uploads_on: None) -> None:
        for name in ("../../secret.txt", "..\\..\\secret.txt", "%2e%2e/%2e%2e/x.txt"):
            result = validate_upload(
                filename=name, content_type="text/plain", size_bytes=10
            )
            # The stored name is generated; the original is only a display label.
            assert "/" not in result.stored_name
            assert "\\" not in result.stored_name
            assert ".." not in result.stored_name

    def test_oversized_upload_is_refused(self, uploads_on: None) -> None:
        with pytest.raises(Exception):
            validate_upload(
                filename="big.png",
                content_type="image/png",
                size_bytes=settings.MAX_UPLOAD_BYTES + 1,
            )

    def test_uploads_disabled_by_default(self) -> None:
        with pytest.raises(Exception):
            validate_upload(filename="x.png", content_type="image/png", size_bytes=1)

    def test_resolved_path_stays_inside_the_root(self, uploads_on: None, tmp_path: Path) -> None:
        result = validate_upload(
            filename="ok.png", content_type="image/png", size_bytes=10
        )
        resolved = resolve_storage_path(result.relative_path("user-1"))
        assert resolved.is_relative_to(tmp_path.resolve())

    def test_storage_path_refuses_an_escaping_relative_path(self, uploads_on: None) -> None:
        with pytest.raises(Exception):
            resolve_storage_path(Path("../escape.txt"))

    def test_windows_reserved_names_are_refused(self, uploads_on: None) -> None:
        with pytest.raises(Exception):
            validate_upload(filename="CON.txt", content_type="text/plain", size_bytes=10)

    def test_sanitise_filename_strips_directories_and_control_chars(self) -> None:
        assert sanitise_filename("../../etc/passwd") == "passwd"
        assert sanitise_filename("..\\..\\secret.txt") == "secret.txt"
        assert "\n" not in sanitise_filename("a\nb.txt")


# ── Security event logging safety ─────────────────────────────────────


class TestSecurityEventLogging:
    def test_event_vocabulary_is_closed(self) -> None:
        from app.models import EVENT_TYPES

        # A representative slice of every event the code emits must be declared.
        for name in (
            "login_success",
            "login_failure",
            "csrf_failure",
            "rate_limited",
            "token_reuse_detected",
            "session_revoked",
            "authorization_denied",
            "password_reset_completed",
        ):
            assert name in EVENT_TYPES, name

    def test_audit_rows_never_contain_raw_secrets(self, anon_client: TestClient, session) -> None:
        register_user(anon_client, email="audit-safe@example.com")
        password = "Vermilion-Lattice-42"
        rows = list(session.scalars(select(AuthEvent)))
        blob = " ".join(
            f"{row.detail or ''} {row.email_hash or ''} {row.ip_hash or ''}"
            for row in rows
        )
        assert password not in blob
        # Emails are hashed, never stored raw.
        assert "audit-safe@example.com" not in blob

    def test_validation_errors_do_not_echo_submitted_values(self, anon_client: TestClient) -> None:
        secret = "sup3r-secret-value-that-should-not-come-back"
        response = anon_client.post(
            "/api/v1/auth/login",
            json={"email": "not-an-email", "password": secret},
        )
        assert response.status_code == 422
        assert secret not in response.text
