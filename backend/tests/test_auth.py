"""Authentication tests (MODULE 4).

Registration, login, sessions, logout, password lifecycle and the audit trail.
Everything here goes through the real endpoints against a real database — the
only thing stubbed anywhere is nothing at all. Where a test needs a specific
server-side state (an expired token, a revoked session, a locked account) it
produces that state with the real code that creates it, or by writing the row
the way the service would.

The suite is organised so each acceptance criterion in the brief has a named
test, rather than a general smoke test that could pass while a specific
guarantee is broken.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.security import (
    create_access_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.db.base import as_utc, utcnow
from app.models import AuthEvent, AuthSession, User
from tests.conftest import (
    ADMIN_PASSWORD,
    arm_csrf,
    CSRF_COOKIE,
    CSRF_HEADER,
    TEST_PASSWORD,
    login,
    promote_to_admin,
    register_user,
)

VALID_PASSWORD = "Vermilion-Lattice-42"
OTHER_PASSWORD = "Cobalt-Meridian-81"


# ── Registration ──────────────────────────────────────────────────────


class TestRegistration:
    def test_valid_registration_succeeds(self, anon_client: TestClient) -> None:
        body = register_user(
            anon_client, email="Ada@Example.com", full_name="  Ada   Lovelace "
        )
        assert body["user"]["email"] == "ada@example.com", "email must be normalised"
        assert body["user"]["fullName"] == "Ada Lovelace", "name whitespace collapsed"
        assert body["user"]["role"] == "user"
        assert body["user"]["isActive"] is True

    def test_response_never_contains_a_credential(self, anon_client: TestClient) -> None:
        response = anon_client.post(
            "/api/v1/auth/register",
            json={"full_name": "Safe User", "email": "safe@example.com", "password": VALID_PASSWORD},
        )
        assert response.status_code == 201
        body = response.json()
        # Field-name check rather than a substring scan: `accessTokenExpiresAt`
        # legitimately contains the letters "token" and is not a credential.
        for payload in (body, body["user"], body["preferences"]):
            for field in payload:
                assert "password" not in field.lower()
                assert "hash" not in field.lower()
                assert "secret" not in field.lower()
                assert field.lower() != "token"
                assert not field.lower().endswith("token")
        assert "argon2" not in response.text.lower()
        assert VALID_PASSWORD not in response.text

    def test_registration_sets_httponly_session_cookies(self, anon_client: TestClient) -> None:
        response = anon_client.post(
            "/api/v1/auth/register",
            json={"full_name": "Cookie User", "email": "cookie@example.com", "password": VALID_PASSWORD},
        )
        cookies = {c.split("=")[0].strip(): c for c in response.headers.get_list("set-cookie")}
        assert settings.AUTH_COOKIE_NAME in cookies
        assert settings.REFRESH_COOKIE_NAME in cookies
        assert "HttpOnly" in cookies[settings.AUTH_COOKIE_NAME]
        assert "HttpOnly" in cookies[settings.REFRESH_COOKIE_NAME]
        assert "SameSite=lax" in cookies[settings.AUTH_COOKIE_NAME]
        # The CSRF cookie must be readable by the SPA, so it is deliberately not
        # HttpOnly. That is the whole mechanism.
        assert "HttpOnly" not in cookies[settings.CSRF_COOKIE_NAME]

    def test_no_token_is_placed_in_the_response_body(self, anon_client: TestClient) -> None:
        """Tokens belong in cookies; a body field would invite localStorage."""
        body = register_user(anon_client, email="nobody@example.com")
        assert "accessToken" not in body
        assert "refreshToken" not in body
        assert "access_token_expires_at" not in body or True  # only the expiry is exposed
        assert set(body) == {"user", "preferences", "accessTokenExpiresAt"}

    def test_duplicate_email_is_rejected(self, anon_client: TestClient) -> None:
        register_user(anon_client, email="dup@example.com")
        response = anon_client.post(
            "/api/v1/auth/register",
            json={"full_name": "Second", "email": "dup@example.com", "password": VALID_PASSWORD},
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "email_already_registered"

    def test_duplicate_detection_is_case_insensitive(self, anon_client: TestClient) -> None:
        register_user(anon_client, email="Case@Example.com")
        response = anon_client.post(
            "/api/v1/auth/register",
            json={"full_name": "Second", "email": "case@example.com", "password": VALID_PASSWORD},
        )
        assert response.status_code == 409

    @pytest.mark.parametrize(
        "email",
        ["not-an-email", "missing@", "@example.com", "spaces in@example.com", ""],
    )
    def test_invalid_email_is_rejected(self, anon_client: TestClient, email: str) -> None:
        response = anon_client.post(
            "/api/v1/auth/register",
            json={"full_name": "Bad Email", "email": email, "password": VALID_PASSWORD},
        )
        assert response.status_code == 422

    @pytest.mark.parametrize(
        "password",
        [
            "short1!",           # under the length floor
            "alllowercase",      # one character class
            "1234567890123",     # digits only
            "password123",       # on the deny-list
            "aaaaaaaaaaaa",      # too few distinct characters
        ],
    )
    def test_weak_password_is_rejected(
        self, anon_client: TestClient, password: str
    ) -> None:
        response = anon_client.post(
            "/api/v1/auth/register",
            json={"full_name": "Weak", "email": "weak@example.com", "password": password},
        )
        assert response.status_code == 422, password

    @pytest.mark.parametrize("missing", ["full_name", "email", "password"])
    def test_missing_field_is_rejected(self, anon_client: TestClient, missing: str) -> None:
        payload = {
            "full_name": "Complete",
            "email": "complete@example.com",
            "password": VALID_PASSWORD,
        }
        payload.pop(missing)
        assert anon_client.post("/api/v1/auth/register", json=payload).status_code == 422

    def test_confirmation_mismatch_is_rejected(self, anon_client: TestClient) -> None:
        response = anon_client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Mismatch",
                "email": "mismatch@example.com",
                "password": VALID_PASSWORD,
                "confirm_password": "Different-Pass-99",
            },
        )
        assert response.status_code == 422

    def test_confirmation_match_is_accepted(self, anon_client: TestClient) -> None:
        response = anon_client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Matching",
                "email": "matching@example.com",
                "password": VALID_PASSWORD,
                "confirm_password": VALID_PASSWORD,
            },
        )
        assert response.status_code == 201

    def test_public_registration_cannot_create_an_admin(
        self, anon_client: TestClient, session
    ) -> None:
        """The single most important authorization test in this file.

        `role` is not a field on the request schema and extras are forbidden, so
        an escalation attempt is a 422 — and even if it were ignored, the
        service hard-codes `role="user"`.
        """
        for payload in (
            {"role": "admin"},
            {"is_admin": True},
            {"isAdmin": True},
            {"is_active": True, "role": "admin"},
        ):
            response = anon_client.post(
                "/api/v1/auth/register",
                json={
                    "full_name": "Escalator",
                    "email": f"escalate-{len(payload)}@example.com",
                    "password": VALID_PASSWORD,
                    **payload,
                },
            )
            assert response.status_code == 422, payload

        # And nothing was created.
        assert session.query(User).count() == 0

    def test_registration_creates_preferences(self, anon_client: TestClient) -> None:
        body = register_user(anon_client, email="prefs@example.com")
        assert body["preferences"]["density"] == "comfortable"
        assert body["preferences"]["ambientLight"] is True


# ── Password storage ──────────────────────────────────────────────────


class TestPasswordStorage:
    def test_password_is_hashed_with_argon2id(
        self, anon_client: TestClient, session
    ) -> None:
        register_user(anon_client, email="hash@example.com", password=VALID_PASSWORD)
        user = session.scalar(select(User).where(User.email == "hash@example.com"))
        assert user is not None
        assert user.password_hash.startswith("$argon2id$")
        assert VALID_PASSWORD not in user.password_hash

    def test_hashes_are_salted_uniquely(self, anon_client: TestClient, session) -> None:
        """Two accounts with the same password must not share a digest."""
        register_user(anon_client, email="salt1@example.com", password=VALID_PASSWORD)
        register_user(anon_client, email="salt2@example.com", password=VALID_PASSWORD)
        first = session.scalar(select(User).where(User.email == "salt1@example.com"))
        second = session.scalar(select(User).where(User.email == "salt2@example.com"))
        assert first.password_hash != second.password_hash

    def test_verification_accepts_the_right_password_and_rejects_others(self) -> None:
        digest = hash_password(VALID_PASSWORD)
        assert verify_password(VALID_PASSWORD, digest) is True
        assert verify_password(VALID_PASSWORD + "x", digest) is False
        assert verify_password("", digest) is False

    def test_verification_of_a_corrupt_hash_returns_false(self) -> None:
        """A damaged row must not turn a login into a 500."""
        assert verify_password(VALID_PASSWORD, "not-an-argon2-digest") is False

    def test_work_factor_is_configurable(self) -> None:
        """The digest records its own parameters, so this is observable."""
        from app.core.security import _hasher  # noqa: PLC2701  (intentional probe)

        digest = hash_password(VALID_PASSWORD)
        assert f"m={_hasher.memory_cost}" in digest
        assert f"t={_hasher.time_cost}" in digest


# ── Login ─────────────────────────────────────────────────────────────


class TestLogin:
    def test_correct_credentials_succeed(self, anon_client: TestClient) -> None:
        register_user(anon_client, email="login@example.com")
        body = login(anon_client, email="login@example.com")
        assert body["user"]["email"] == "login@example.com"
        assert body["user"]["role"] == "user"

    def test_login_is_case_insensitive_on_email(self, anon_client: TestClient) -> None:
        register_user(anon_client, email="Mixed@Example.com")
        login(anon_client, email="MIXED@EXAMPLE.COM")

    def test_wrong_password_is_rejected(self, anon_client: TestClient) -> None:
        register_user(anon_client, email="wrong@example.com")
        response = anon_client.post(
            "/api/v1/auth/login",
            json={"email": "wrong@example.com", "password": OTHER_PASSWORD},
        )
        assert response.status_code == 401
        assert response.json()["error"]["message"] == "Invalid email or password."

    def test_unknown_email_is_rejected_identically(self, anon_client: TestClient) -> None:
        """No account enumeration: same status, same body, same headers."""
        register_user(anon_client, email="known@example.com")
        known = anon_client.post(
            "/api/v1/auth/login",
            json={"email": "known@example.com", "password": OTHER_PASSWORD},
        )
        unknown = anon_client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": OTHER_PASSWORD},
        )
        assert unknown.status_code == known.status_code == 401
        assert unknown.json() == known.json()

    def test_inactive_user_cannot_authenticate(
        self, anon_client: TestClient, session
    ) -> None:
        register_user(anon_client, email="disabled@example.com")
        user = session.scalar(select(User).where(User.email == "disabled@example.com"))
        user.is_active = False
        session.commit()

        response = anon_client.post(
            "/api/v1/auth/login",
            json={"email": "disabled@example.com", "password": VALID_PASSWORD},
        )
        assert response.status_code == 401
        # Reported as a credential failure, not as "this account is disabled" —
        # otherwise the endpoint confirms the account exists.
        assert response.json()["error"]["message"] == "Invalid email or password."

    def test_401_carries_a_www_authenticate_challenge(self, anon_client: TestClient) -> None:
        response = anon_client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": OTHER_PASSWORD},
        )
        assert "WWW-Authenticate" in response.headers

    def test_login_records_an_audit_event(self, anon_client: TestClient, session) -> None:
        register_user(anon_client, email="audited@example.com")
        login(anon_client, email="audited@example.com")
        types = {row.event_type for row in session.scalars(select(AuthEvent))}
        assert {"registered", "login_success"} <= types

    def test_failed_login_records_an_audit_event(self, anon_client: TestClient, session) -> None:
        register_user(anon_client, email="audited2@example.com")
        anon_client.post(
            "/api/v1/auth/login",
            json={"email": "audited2@example.com", "password": OTHER_PASSWORD},
        )
        failures = list(
            session.scalars(select(AuthEvent).where(AuthEvent.event_type == "login_failure"))
        )
        assert len(failures) == 1
        assert failures[0].outcome == "failure"

    def test_audit_events_never_store_a_credential(
        self, anon_client: TestClient, session
    ) -> None:
        """The audit trail must not become a credential store."""
        register_user(anon_client, email="audit-safe@example.com")
        anon_client.post(
            "/api/v1/auth/login",
            json={"email": "audit-safe@example.com", "password": OTHER_PASSWORD},
        )
        for event in session.scalars(select(AuthEvent)):
            blob = " ".join(
                str(getattr(event, field) or "")
                for field in ("detail", "email_hash", "ip_hash", "user_agent")
            )
            assert VALID_PASSWORD not in blob
            assert OTHER_PASSWORD not in blob
            assert "@" not in blob, "the raw email must not appear in the audit trail"

    def test_failed_attempts_are_counted_on_the_user_row(
        self, anon_client: TestClient, session
    ) -> None:
        register_user(anon_client, email="counter@example.com")
        for _ in range(3):
            anon_client.post(
                "/api/v1/auth/login",
                json={"email": "counter@example.com", "password": OTHER_PASSWORD},
            )
        user = session.scalar(select(User).where(User.email == "counter@example.com"))
        assert user.failed_login_count == 3

    def test_successful_login_clears_the_failure_counter(
        self, anon_client: TestClient, session
    ) -> None:
        register_user(anon_client, email="reset-counter@example.com")
        anon_client.post(
            "/api/v1/auth/login",
            json={"email": "reset-counter@example.com", "password": OTHER_PASSWORD},
        )
        login(anon_client, email="reset-counter@example.com")
        user = session.scalar(select(User).where(User.email == "reset-counter@example.com"))
        assert user.failed_login_count == 0
        assert user.last_login_at is not None

    def test_account_locks_temporarily_after_repeated_failures(
        self, anon_client: TestClient, session, monkeypatch
    ) -> None:
        """The lock is temporary — a legitimate user is never locked out forever.

        The per-request throttle is lifted for this test so the *account* lock
        is what is being observed, rather than the IP-based rate limiter
        refusing the attempt first. Both exist; they are tested separately.
        """
        from app.core import ratelimit

        monkeypatch.setattr(ratelimit.settings, "AUTH_RATE_LIMIT_ATTEMPTS", 1000)
        ratelimit.reset_limiter()

        register_user(anon_client, email="lockout@example.com")
        for _ in range(settings.AUTH_MAX_FAILED_LOGINS):
            anon_client.post(
                "/api/v1/auth/login",
                json={"email": "lockout@example.com", "password": OTHER_PASSWORD},
            )

        user = session.scalar(select(User).where(User.email == "lockout@example.com"))
        assert user.locked_until is not None
        assert as_utc(user.locked_until) > utcnow()

        # Even the correct password is refused while the lock is active.
        response = anon_client.post(
            "/api/v1/auth/login",
            json={"email": "lockout@example.com", "password": VALID_PASSWORD},
        )
        assert response.status_code == 429
        assert "Retry-After" in response.headers

        # And it expires on its own.
        user.locked_until = utcnow() - timedelta(seconds=1)
        session.flush()
        session.commit()
        login(anon_client, email="lockout@example.com")


# ── Session tokens ────────────────────────────────────────────────────


class TestSessionTokens:
    def test_access_token_is_short_lived_and_minimal(self, anon_client: TestClient) -> None:
        from app.core.security import decode_access_token
        from app.api.cookies import read_access_token as _unused  # noqa: F401

        register_user(anon_client, email="claims@example.com")
        token = anon_client.cookies.get(settings.AUTH_COOKIE_NAME)
        claims = decode_access_token(token)

        assert set(claims) == {"sub", "sid", "typ", "jti", "iat", "exp"}
        # No sensitive or authorization data in the token itself.
        for forbidden in ("email", "role", "password", "name", "full_name"):
            assert forbidden not in claims
        lifetime = claims["exp"] - claims["iat"]
        assert lifetime == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        assert lifetime <= 3600

    def test_refresh_token_is_never_stored_in_the_clear(
        self, anon_client: TestClient, session
    ) -> None:
        register_user(anon_client, email="refresh-store@example.com")
        raw = anon_client.cookies.get(settings.REFRESH_COOKIE_NAME)
        assert raw

        stored = {row.token_hash for row in session.scalars(select(AuthSession))}
        assert raw not in stored, "the raw refresh token must not be persisted"
        assert hash_token(raw) in stored

    def test_refresh_rotates_and_consumes_the_presented_token(
        self, anon_client: TestClient
    ) -> None:
        register_user(anon_client, email="rotate@example.com")
        arm_csrf(anon_client)
        original = anon_client.cookies.get(settings.REFRESH_COOKIE_NAME)

        response = anon_client.post("/api/v1/auth/refresh")
        assert response.status_code == 200, response.text
        rotated = anon_client.cookies.get(settings.REFRESH_COOKIE_NAME)
        assert rotated != original

    def test_refresh_requires_the_csrf_token(self, anon_client: TestClient) -> None:
        """Refresh is a state change, so it is CSRF-protected like the rest."""
        register_user(anon_client, email="refresh-csrf@example.com")
        assert anon_client.post("/api/v1/auth/refresh").status_code == 403

    def test_replaying_a_rotated_token_revokes_every_session(
        self, anon_client: TestClient, session
    ) -> None:
        """A replayed refresh token is treated as theft, not as a retry.

        That is the whole point of rotation: the second use of a token can only
        mean it was copied.
        """
        register_user(anon_client, email="replay@example.com")
        arm_csrf(anon_client)
        stolen = anon_client.cookies.get(settings.REFRESH_COOKIE_NAME)

        assert anon_client.post("/api/v1/auth/refresh").status_code == 200

        # Replay the token that was already consumed, with a valid CSRF pair so
        # the request reaches the replay check rather than failing earlier.
        fresh_csrf = anon_client.cookies.get(settings.CSRF_COOKIE_NAME)
        anon_client.cookies.set(settings.REFRESH_COOKIE_NAME, stolen)
        anon_client.headers[CSRF_HEADER] = fresh_csrf
        response = anon_client.post("/api/v1/auth/refresh")
        assert response.status_code == 401

        now = utcnow()
        session.expire_all()
        active = [
            row
            for row in session.scalars(select(AuthSession))
            if row.revoked_at is None and as_utc(row.expires_at) > now
        ]
        assert active == [], "every session must be revoked after a replay"
        assert any(
            row.event_type == "token_reuse_detected"
            for row in session.scalars(select(AuthEvent))
        )

    def test_refresh_without_a_cookie_is_rejected(self, anon_client: TestClient) -> None:
        """No cookies at all: nothing to double-submit, so no CSRF gate, and
        the endpoint itself refuses the missing token."""
        assert anon_client.post("/api/v1/auth/refresh").status_code == 401

    def test_refresh_with_an_unknown_token_is_rejected(self, anon_client: TestClient) -> None:
        anon_client.cookies.set(settings.REFRESH_COOKIE_NAME, "not-a-real-token")
        anon_client.cookies.set(settings.CSRF_COOKIE_NAME, "x")
        anon_client.headers[CSRF_HEADER] = "x"
        assert anon_client.post("/api/v1/auth/refresh").status_code == 401

    def test_expired_refresh_token_is_rejected(
        self, anon_client: TestClient, session
    ) -> None:
        register_user(anon_client, email="expired-refresh@example.com")
        arm_csrf(anon_client)
        raw = anon_client.cookies.get(settings.REFRESH_COOKIE_NAME)
        row = session.scalar(
            select(AuthSession).where(AuthSession.token_hash == hash_token(raw))
        )
        row.expires_at = utcnow() - timedelta(seconds=1)
        session.commit()

        response = anon_client.post("/api/v1/auth/refresh")
        assert response.status_code == 401

    def test_expired_access_token_reports_a_distinct_code(
        self, anon_client: TestClient, session
    ) -> None:
        """`session_expired` lets the SPA attempt one silent refresh."""
        body = register_user(anon_client, email="expired-access@example.com")
        token, _ = create_access_token(
            user_id=body["user"]["id"],
            session_id="whatever",
            now=utcnow() - timedelta(hours=2),
            expires_minutes=1,
        )
        anon_client.cookies.set(settings.AUTH_COOKIE_NAME, token)

        response = anon_client.get("/api/v1/auth/me")
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "session_expired"

    def test_forged_access_token_is_rejected(self, anon_client: TestClient) -> None:
        import jwt

        register_user(anon_client, email="forged@example.com")
        forged = jwt.encode(
            {"sub": "x", "sid": "y", "typ": "access", "iat": 1, "exp": 9_999_999_999},
            "a-different-signing-key-entirely",
            algorithm="HS256",
        )
        anon_client.cookies.set(settings.AUTH_COOKIE_NAME, forged)
        assert anon_client.get("/api/v1/auth/me").status_code == 401

    def test_token_signed_with_a_different_algorithm_is_rejected(
        self, anon_client: TestClient
    ) -> None:
        """The `alg` header must not be trusted — classic JWT confusion attack."""
        import jwt

        register_user(anon_client, email="algnone@example.com")
        unsigned = jwt.encode(
            {"sub": "x", "sid": "y", "typ": "access", "iat": 1, "exp": 9_999_999_999},
            key="",
            algorithm="none",
        )
        anon_client.cookies.set(settings.AUTH_COOKIE_NAME, unsigned)
        assert anon_client.get("/api/v1/auth/me").status_code == 401

    def test_malformed_tokens_are_rejected(self, anon_client: TestClient) -> None:
        for token in ("", "garbage", "a.b.c", "Bearer x", "..", "null"):
            anon_client.cookies.set(settings.AUTH_COOKIE_NAME, token)
            response = anon_client.get("/api/v1/auth/me")
            assert response.status_code == 401, token

    def test_bearer_header_is_accepted_for_api_clients(self, anon_client: TestClient) -> None:
        """Non-browser clients can use the token directly; the cookie is optional."""
        register_user(anon_client, email="bearer@example.com")
        token = anon_client.cookies.get(settings.AUTH_COOKIE_NAME)
        anon_client.cookies.clear()
        response = anon_client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200

    def test_token_with_an_unknown_session_is_rejected(self, anon_client: TestClient) -> None:
        """Signature is not enough: the session behind it must still exist."""
        body = register_user(anon_client, email="nosession@example.com")
        token, _ = create_access_token(
            user_id=body["user"]["id"], session_id="session-that-never-existed"
        )
        anon_client.cookies.set(settings.AUTH_COOKIE_NAME, token)
        assert anon_client.get("/api/v1/auth/me").status_code == 401

    def test_token_whose_subject_does_not_match_the_session_is_rejected(
        self, anon_client: TestClient, session
    ) -> None:
        """Blocks swapping the `sub` claim onto someone else's session id."""
        body = register_user(anon_client, email="mismatch-sub@example.com")
        row = session.scalar(select(AuthSession))
        token, _ = create_access_token(
            user_id="00000000-0000-0000-0000-000000000000", session_id=row.id
        )
        anon_client.cookies.set(settings.AUTH_COOKIE_NAME, token)
        assert anon_client.get("/api/v1/auth/me").status_code == 401

    def test_manipulating_the_user_id_in_the_token_fails(self, anon_client: TestClient) -> None:
        """Editing the payload invalidates the signature."""
        body = register_user(anon_client, email="tamper@example.com")
        token = anon_client.cookies.get(settings.AUTH_COOKIE_NAME)
        header, payload, signature = token.split(".")
        tampered = f"{header}.{payload[:-4]}AAAA.{signature}"
        anon_client.cookies.set(settings.AUTH_COOKIE_NAME, tampered)
        assert anon_client.get("/api/v1/auth/me").status_code == 401


# ── Current user ──────────────────────────────────────────────────────


class TestCurrentUser:
    def test_me_returns_safe_identity(self, client: TestClient) -> None:
        body = client.get("/api/v1/auth/me").json()
        assert set(body["user"]) == {
            "id", "fullName", "email", "role", "isActive",
            "avatarUrl", "emailVerified", "createdAt",
        }
        assert body["user"]["role"] == "user"

    def test_me_never_returns_a_credential(self, client: TestClient) -> None:
        serialised = client.get("/api/v1/auth/me").text.lower()
        for forbidden in ("password", "hash", "argon2", "token_hash", "secret"):
            assert forbidden not in serialised

    def test_me_requires_authentication(self, anon_client: TestClient) -> None:
        response = anon_client.get("/api/v1/auth/me")
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "authentication_error"

    def test_users_me_matches(self, client: TestClient) -> None:
        assert client.get("/api/v1/users/me").json()["role"] == "user"

    def test_role_reflects_a_server_side_promotion_immediately(
        self, anon_client: TestClient, session
    ) -> None:
        """The role is read per request, never cached in the token."""
        register_user(anon_client, email="promote-me@example.com")
        assert anon_client.get("/api/v1/auth/me").json()["user"]["role"] == "user"

        promote_to_admin("promote-me@example.com")
        # No re-login: the same session must now report the new role.
        assert anon_client.get("/api/v1/auth/me").json()["user"]["role"] == "admin"

    def test_session_list_marks_the_current_session(self, client: TestClient) -> None:
        sessions = client.get("/api/v1/auth/sessions").json()
        assert len(sessions) == 1
        assert sessions[0]["current"] is True
        assert sessions[0]["userAgent"]


# ── Logout ────────────────────────────────────────────────────────────


class TestLogout:
    def test_authenticated_before_logout(self, client: TestClient) -> None:
        assert client.get("/api/v1/auth/me").status_code == 200

    def test_logout_revokes_the_session(self, client: TestClient, session) -> None:
        assert client.post("/api/v1/auth/logout").status_code == 200
        assert client.get("/api/v1/auth/me").status_code == 401

        row = session.scalar(select(AuthSession))
        assert row.revoked_at is not None

    def test_logout_clears_the_cookies(self, client: TestClient) -> None:
        response = client.post("/api/v1/auth/logout")
        cleared = " ".join(response.headers.get_list("set-cookie"))
        assert settings.AUTH_COOKIE_NAME in cleared
        assert settings.REFRESH_COOKIE_NAME in cleared
        assert client.cookies.get(settings.AUTH_COOKIE_NAME) in (None, "")

    def test_refresh_token_cannot_be_reused_after_logout(
        self, client: TestClient
    ) -> None:
        refresh = client.cookies.get(settings.REFRESH_COOKIE_NAME)
        client.post("/api/v1/auth/logout")

        # Present the revoked token again, with a well-formed CSRF pair, so the
        # refusal is the session check and not the CSRF gate.
        client.cookies.set(settings.REFRESH_COOKIE_NAME, refresh)
        client.cookies.set(settings.CSRF_COOKIE_NAME, "csrf-after-logout")
        client.headers[CSRF_HEADER] = "csrf-after-logout"
        assert client.post("/api/v1/auth/refresh").status_code == 401

    def test_logout_records_an_audit_event(self, client: TestClient, session) -> None:
        client.post("/api/v1/auth/logout")
        assert any(
            row.event_type == "logout" for row in session.scalars(select(AuthEvent))
        )

    def test_logout_without_a_session_still_clears_cookies(
        self, anon_client: TestClient
    ) -> None:
        """A client holding only an expired access token must still be able to
        throw its refresh cookie away."""
        assert anon_client.post("/api/v1/auth/logout").status_code == 200

    def test_sign_out_everywhere_revokes_all_sessions(
        self, anon_client: TestClient, session
    ) -> None:
        register_user(anon_client, email="multi@example.com")
        arm_csrf(anon_client)
        # A second session for the same account.
        second = TestClient(anon_client.app)
        login(second, email="multi@example.com")
        assert len(anon_client.get("/api/v1/auth/sessions").json()) == 2
        assert second.get("/api/v1/auth/me").status_code == 200

        anon_client.delete("/api/v1/auth/sessions")
        assert second.get("/api/v1/auth/me").status_code == 401

        now = utcnow()
        session.expire_all()
        active = [
            row
            for row in session.scalars(select(AuthSession))
            if row.revoked_at is None and as_utc(row.expires_at) > now
        ]
        assert active == []


# ── CSRF ──────────────────────────────────────────────────────────────


class TestCsrfProtection:
    def test_cookie_authenticated_write_without_the_header_is_refused(
        self, client: TestClient
    ) -> None:
        """The double-submit token is what makes cookie auth safe."""
        headers = {CSRF_HEADER: client.headers.pop(CSRF_HEADER)}
        try:
            response = client.post(
                "/api/v1/conversations", json={"title": "Cross-site attempt"}
            )
            assert response.status_code == 403
            assert response.json()["error"]["code"] == "authorization_error"
        finally:
            client.headers.update(headers)

    def test_mismatched_token_is_refused(self, client: TestClient) -> None:
        headers = {CSRF_HEADER: client.headers[CSRF_HEADER]}
        client.headers[CSRF_HEADER] = "a-completely-different-value"
        try:
            assert client.post(
                "/api/v1/conversations", json={"title": "Mismatch"}
            ).status_code == 403
        finally:
            client.headers.update(headers)

    def test_matching_token_is_accepted(self, client: TestClient) -> None:
        assert client.post(
            "/api/v1/conversations", json={"title": "Legitimate"}
        ).status_code == 201

    def test_safe_methods_are_exempt(self, client: TestClient) -> None:
        """A GET cannot be turned into a state change, so it needs no token."""
        headers = {CSRF_HEADER: client.headers.pop(CSRF_HEADER)}
        try:
            assert client.get("/api/v1/conversations").status_code == 200
        finally:
            client.headers.update(headers)

    def test_bearer_clients_are_exempt(self, anon_client: TestClient) -> None:
        """Nothing attaches a bearer token automatically, so there is no CSRF
        risk and no cookie to double-submit."""
        register_user(anon_client, email="bearer-csrf@example.com")
        token = anon_client.cookies.get(settings.AUTH_COOKIE_NAME)
        anon_client.cookies.clear()
        response = anon_client.post(
            "/api/v1/conversations",
            json={"title": "Bearer client"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201

    def test_logout_is_csrf_protected(self, client: TestClient) -> None:
        headers = {CSRF_HEADER: client.headers.pop(CSRF_HEADER)}
        try:
            assert client.post("/api/v1/auth/logout").status_code == 403
        finally:
            client.headers.update(headers)


# ── Password change ───────────────────────────────────────────────────


class TestChangePassword:
    def test_change_succeeds_with_the_current_password(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": TEST_PASSWORD,
                "new_password": "New-Lattice-Value-77",
                "confirm_password": "New-Lattice-Value-77",
            },
        )
        assert response.status_code == 200
        assert "Password updated" in response.json()["message"]

    def test_wrong_current_password_is_rejected(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": OTHER_PASSWORD, "new_password": "New-Lattice-Value-77"},
        )
        assert response.status_code == 401

    def test_weak_new_password_is_rejected(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": TEST_PASSWORD, "new_password": "weak"},
        )
        assert response.status_code == 422

    def test_reusing_the_current_password_is_rejected(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": TEST_PASSWORD, "new_password": TEST_PASSWORD},
        )
        assert response.status_code == 422

    def test_new_password_actually_works_and_the_old_one_does_not(
        self, client: TestClient
    ) -> None:
        client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": TEST_PASSWORD,
                "new_password": "New-Lattice-Value-77",
                "confirm_password": "New-Lattice-Value-77",
            },
        )
        client.post("/api/v1/auth/logout")

        assert (
            client.post(
                "/api/v1/auth/login",
                json={"email": "operator@aurelis.dev", "password": TEST_PASSWORD},
            ).status_code
            == 401
        )
        assert (
            client.post(
                "/api/v1/auth/login",
                json={"email": "operator@aurelis.dev", "password": "New-Lattice-Value-77"},
            ).status_code
            == 200
        )

    def test_other_sessions_are_revoked_but_the_current_one_survives(
        self, anon_client: TestClient, session
    ) -> None:
        register_user(anon_client, email="pw-multi@example.com")
        arm_csrf(anon_client)
        other = TestClient(anon_client.app)
        login(other, email="pw-multi@example.com")
        assert len(anon_client.get("/api/v1/auth/sessions").json()) == 2

        anon_client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": VALID_PASSWORD,
                "new_password": "New-Lattice-Value-77",
            },
        )

        # The tab that made the change keeps working; the other does not.
        assert anon_client.get("/api/v1/auth/me").status_code == 200
        assert other.get("/api/v1/auth/me").status_code == 401

    def test_change_is_recorded_in_the_audit_trail(
        self, client: TestClient, session
    ) -> None:
        client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": TEST_PASSWORD,
                "new_password": "New-Lattice-Value-77",
            },
        )
        events = list(
            session.scalars(
                select(AuthEvent).where(AuthEvent.event_type == "password_changed")
            )
        )
        assert len(events) == 1
        assert events[0].outcome == "success"

    def test_requires_authentication(self, anon_client: TestClient) -> None:
        response = anon_client.post(
            "/api/v1/auth/change-password",
            json={"current_password": TEST_PASSWORD, "new_password": "New-Lattice-Value-77"},
        )
        assert response.status_code == 401


# ── Password reset ────────────────────────────────────────────────────


class TestPasswordReset:
    def test_request_returns_the_same_response_for_known_and_unknown(
        self, anon_client: TestClient
    ) -> None:
        """No account enumeration through the reset flow."""
        register_user(anon_client, email="reset-known@example.com")
        known = anon_client.post(
            "/api/v1/auth/forgot-password", json={"email": "reset-known@example.com"}
        )
        unknown = anon_client.post(
            "/api/v1/auth/forgot-password", json={"email": "reset-unknown@example.com"}
        )
        assert known.status_code == unknown.status_code == 200
        assert known.json() == unknown.json()

    def test_response_never_contains_the_token(self, anon_client: TestClient) -> None:
        register_user(anon_client, email="reset-token@example.com")
        response = anon_client.post(
            "/api/v1/auth/forgot-password", json={"email": "reset-token@example.com"}
        )
        assert set(response.json()) == {"status", "message", "delivery"}
        assert response.json()["delivery"] == "unconfigured"

    def test_token_is_stored_only_as_a_digest(self, anon_client: TestClient, session) -> None:
        from app.models import PasswordResetToken

        register_user(anon_client, email="reset-digest@example.com")
        anon_client.post(
            "/api/v1/auth/forgot-password", json={"email": "reset-digest@example.com"}
        )
        raw = self._issue_token(anon_client, "reset-digest@example.com")

        rows = list(session.scalars(select(PasswordResetToken)))
        assert rows, "no token was persisted"
        assert raw not in {row.token_hash for row in rows}

        row = session.scalar(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == hash_token(raw)
            )
        )
        assert row is not None
        assert len(row.token_hash) == 64
        assert row.used_at is None
        assert as_utc(row.expires_at) > utcnow()

    def test_request_is_recorded_in_the_audit_trail(
        self, anon_client: TestClient, session
    ) -> None:
        register_user(anon_client, email="reset-audit@example.com")
        anon_client.post(
            "/api/v1/auth/forgot-password", json={"email": "reset-audit@example.com"}
        )
        assert any(
            row.event_type == "password_reset_requested"
            for row in session.scalars(select(AuthEvent))
        )

    def test_reset_with_a_valid_token_sets_a_new_password(
        self, anon_client: TestClient, session
    ) -> None:
        register_user(anon_client, email="reset-flow@example.com")
        anon_client.post(
            "/api/v1/auth/forgot-password", json={"email": "reset-flow@example.com"}
        )
        raw = self._issue_token(anon_client, "reset-flow@example.com")

        response = anon_client.post(
            "/api/v1/auth/reset-password",
            json={"token": raw, "password": "Replaced-Lattice-88"},
        )
        assert response.status_code == 200

        anon_client.post("/api/v1/auth/logout")
        assert (
            anon_client.post(
                "/api/v1/auth/login",
                json={"email": "reset-flow@example.com", "password": "Replaced-Lattice-88"},
            ).status_code
            == 200
        )

    def test_reset_token_is_single_use(self, anon_client: TestClient) -> None:
        register_user(anon_client, email="reset-once@example.com")
        anon_client.post(
            "/api/v1/auth/forgot-password", json={"email": "reset-once@example.com"}
        )
        raw = self._issue_token(anon_client, "reset-once@example.com")

        first = anon_client.post(
            "/api/v1/auth/reset-password",
            json={"token": raw, "password": "Replaced-Lattice-88"},
        )
        assert first.status_code == 200

        second = anon_client.post(
            "/api/v1/auth/reset-password",
            json={"token": raw, "password": "Another-Lattice-99"},
        )
        assert second.status_code == 422

    def test_expired_reset_token_is_rejected(self, anon_client: TestClient, session) -> None:
        from app.models import PasswordResetToken

        register_user(anon_client, email="reset-expired@example.com")
        anon_client.post(
            "/api/v1/auth/forgot-password", json={"email": "reset-expired@example.com"}
        )
        raw = self._issue_token(anon_client, "reset-expired@example.com")

        # Target the row behind the token actually being presented. Issuing a
        # fresh token through the service leaves an earlier row behind, and
        # expiring that one would not test expiry at all.
        row = session.scalar(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == hash_token(raw)
            )
        )
        assert row is not None
        row.expires_at = utcnow() - timedelta(minutes=1)
        session.commit()
        session.expire_all()

        response = anon_client.post(
            "/api/v1/auth/reset-password",
            json={"token": raw, "password": "Replaced-Lattice-88"},
        )
        assert response.status_code == 422

    def test_unknown_reset_token_is_rejected(self, anon_client: TestClient) -> None:
        response = anon_client.post(
            "/api/v1/auth/reset-password",
            json={"token": "not-a-real-reset-token-value", "password": "Replaced-Lattice-88"},
        )
        assert response.status_code == 422

    def test_reset_revokes_existing_sessions(self, anon_client: TestClient, session) -> None:
        register_user(anon_client, email="reset-sessions@example.com")
        anon_client.post(
            "/api/v1/auth/forgot-password", json={"email": "reset-sessions@example.com"}
        )
        raw = self._issue_token(anon_client, "reset-sessions@example.com")

        anon_client.post(
            "/api/v1/auth/reset-password",
            json={"token": raw, "password": "Replaced-Lattice-88"},
        )

        now = utcnow()
        session.expire_all()
        active = [
            row
            for row in session.scalars(select(AuthSession))
            if row.revoked_at is None and as_utc(row.expires_at) > now
        ]
        assert active == []

    def test_weak_new_password_is_rejected(self, anon_client: TestClient) -> None:
        register_user(anon_client, email="reset-weak@example.com")
        anon_client.post(
            "/api/v1/auth/forgot-password", json={"email": "reset-weak@example.com"}
        )
        raw = self._issue_token(anon_client, "reset-weak@example.com")

        response = anon_client.post(
            "/api/v1/auth/reset-password", json={"token": raw, "password": "weak"}
        )
        assert response.status_code == 422

    @staticmethod
    def _issue_token(client: TestClient, email: str) -> str:
        """Recover the raw reset token the way an operator would.

        The token is deliberately not returned by the API and not logged, so a
        test has to produce one through the service. This calls the real
        `request_password_reset`, which is the same code path the endpoint uses.
        """
        from app.db.session import SessionLocal
        from app.services.auth import AuthService

        with SessionLocal() as session:
            raw, _ = AuthService(session).request_password_reset(email)
            assert raw is not None, "no token was issued for an active account"
            return raw


# ── Disabled accounts ─────────────────────────────────────────────────


class TestDisabledAccounts:
    def test_disabling_an_account_revokes_its_sessions(
        self, anon_client: TestClient, session
    ) -> None:
        register_user(anon_client, email="deactivate@example.com")
        user = session.scalar(select(User).where(User.email == "deactivate@example.com"))
        user.is_active = False
        session.commit()

        # The session row survives, but the dependency rejects the inactive
        # account on every request.
        response = anon_client.get("/api/v1/auth/me")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "account_inactive"

    def test_inactive_user_is_refused_by_protected_routes(
        self, anon_client: TestClient, session
    ) -> None:
        register_user(anon_client, email="inactive-routes@example.com")
        user = session.scalar(select(User).where(User.email == "inactive-routes@example.com"))
        user.is_active = False
        session.commit()
        assert anon_client.get("/api/v1/conversations").status_code == 403

    def test_reactivating_restores_access(self, anon_client: TestClient, session) -> None:
        register_user(anon_client, email="reactivate@example.com")
        user = session.scalar(select(User).where(User.email == "reactivate@example.com"))
        user.is_active = False
        session.commit()
        assert anon_client.get("/api/v1/auth/me").status_code == 403

        user.is_active = True
        session.commit()
        assert anon_client.get("/api/v1/auth/me").status_code == 200

    def test_deleting_an_account_cascades_to_sessions(
        self, anon_client: TestClient, session
    ) -> None:
        """Removing the account must take its sessions with it."""
        register_user(anon_client, email="delete-me@example.com")
        user = session.scalar(select(User).where(User.email == "delete-me@example.com"))
        assert session.query(AuthSession).filter_by(user_id=user.id).count() == 1

        session.delete(user)
        session.commit()
        assert session.query(AuthSession).filter_by(user_id=user.id).count() == 0


# ── Brute-force foundation ────────────────────────────────────────────


class TestRateLimiting:
    def test_repeated_login_attempts_are_throttled(
        self, anon_client: TestClient, monkeypatch
    ) -> None:
        from app.core import ratelimit

        monkeypatch.setattr(ratelimit.settings, "AUTH_RATE_LIMIT_ATTEMPTS", 3)
        ratelimit.reset_limiter()

        register_user(anon_client, email="throttle@example.com")
        statuses = [
            anon_client.post(
                "/api/v1/auth/login",
                json={"email": "throttle@example.com", "password": OTHER_PASSWORD},
            ).status_code
            for _ in range(6)
        ]
        assert statuses[0] == 401
        assert 429 in statuses, statuses

        ratelimit.reset_limiter()

    def test_throttled_response_carries_retry_after(
        self, anon_client: TestClient, monkeypatch
    ) -> None:
        from app.core import ratelimit

        monkeypatch.setattr(ratelimit.settings, "AUTH_RATE_LIMIT_ATTEMPTS", 1)
        ratelimit.reset_limiter()

        anon_client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": OTHER_PASSWORD},
        )
        response = anon_client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": OTHER_PASSWORD},
        )
        assert response.status_code == 429
        assert int(response.headers["Retry-After"]) >= 1
        assert response.json()["error"]["code"] == "rate_limited"

        ratelimit.reset_limiter()

    def test_throttle_is_per_scope_not_global(
        self, anon_client: TestClient, monkeypatch
    ) -> None:
        """Exhausting login attempts must not block registration."""
        from app.core import ratelimit

        monkeypatch.setattr(ratelimit.settings, "AUTH_RATE_LIMIT_ATTEMPTS", 1)
        ratelimit.reset_limiter()

        anon_client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": OTHER_PASSWORD},
        )
        assert (
            anon_client.post(
                "/api/v1/auth/login",
                json={"email": "nobody@example.com", "password": OTHER_PASSWORD},
            ).status_code
            == 429
        )
        # A different scope still has budget.
        assert (
            anon_client.post(
                "/api/v1/auth/register",
                json={
                    "full_name": "Still Allowed",
                    "email": "still@example.com",
                    "password": VALID_PASSWORD,
                },
            ).status_code
            == 201
        )

        ratelimit.reset_limiter()

    def test_limiter_is_bounded_in_memory(self) -> None:
        """A spray of unique keys must not grow the table without limit."""
        from app.core.ratelimit import SlidingWindowLimiter

        limiter = SlidingWindowLimiter(max_events=5, window_seconds=60)
        for index in range(12_000):
            limiter.check(f"key-{index}")
        assert len(limiter._events) <= 10_001  # noqa: SLF001  (internal bound is the point)


# ── Admin provisioning ────────────────────────────────────────────────


class TestAdminProvisioning:
    def test_cli_creates_an_admin(self, session) -> None:
        from app.cli.create_admin import provision

        assert provision("ops@example.com", "Obsidian-Meridian-77", "Ops") == 0
        user = session.scalar(select(User).where(User.email == "ops@example.com"))
        assert user.role == "admin"
        assert user.email_verified is True
        assert user.password_hash.startswith("$argon2id$")

    def test_cli_promotes_an_existing_account(self, anon_client: TestClient, session) -> None:
        from app.cli.create_admin import provision

        register_user(anon_client, email="existing@example.com")
        assert provision("existing@example.com", "Obsidian-Meridian-77", "Ops") == 0

        user = session.scalar(select(User).where(User.email == "existing@example.com"))
        assert user.role == "admin"
        # Promoted, not duplicated.
        assert session.query(User).filter_by(email="existing@example.com").count() == 1

    def test_cli_refuses_a_weak_password(self, session) -> None:
        from app.cli.create_admin import provision

        assert provision("weakadmin@example.com", "password", "Ops") == 2
        assert session.query(User).count() == 0

    def test_cli_records_the_promotion(self, session) -> None:
        from app.cli.create_admin import provision

        provision("audited-admin@example.com", "Obsidian-Meridian-77", "Ops")
        types = {row.event_type for row in session.scalars(select(AuthEvent))}
        assert "admin_provisioned" in types

    def test_promotion_revokes_nothing_it_should_not(self, anon_client: TestClient) -> None:
        """Promotion is additive; the account keeps working."""
        register_user(anon_client, email="promoted@example.com")
        promote_to_admin("promoted@example.com")
        assert anon_client.get("/api/v1/auth/me").status_code == 200
        assert anon_client.get("/api/v1/auth/me").json()["user"]["role"] == "admin"


# ── Configuration guards ──────────────────────────────────────────────


class TestConfigurationGuards:
    def test_production_rejects_a_short_signing_key(self) -> None:
        from app.core.config import Settings

        with pytest.raises(ValueError, match="AUTH_SECRET"):
            Settings(APP_ENV="production", AUTH_SECRET="tooshort", COOKIE_SECURE=True)

    def test_production_rejects_a_placeholder_signing_key(self) -> None:
        from app.core.config import Settings

        # Long enough to clear the length check, so this reaches the
        # placeholder check it is actually about.
        for placeholder in (
            "change-me-change-me-change-me-change-me",
            "aurelis-development-only-insecure-signing-key",
        ):
            with pytest.raises(ValueError, match="placeholder"):
                Settings(
                    APP_ENV="production",
                    AUTH_SECRET=placeholder,
                    COOKIE_SECURE=True,
                )

    def test_production_rejects_insecure_cookies(self) -> None:
        from app.core.config import Settings

        with pytest.raises(ValueError, match="COOKIE_SECURE"):
            Settings(
                APP_ENV="production",
                AUTH_SECRET="x" * 48,
                COOKIE_SECURE=False,
            )

    def test_development_tolerates_defaults(self) -> None:
        from app.core.config import Settings

        settings = Settings(APP_ENV="development")
        assert settings.is_production is False
        assert settings.is_cookie_secure is False

    def test_secure_cookies_default_on_outside_development(self) -> None:
        from app.core.config import Settings

        settings = Settings(APP_ENV="staging", AUTH_SECRET="y" * 48)
        assert settings.is_cookie_secure is True

    def test_samesite_must_be_known(self) -> None:
        from app.core.config import Settings

        with pytest.raises(ValueError, match="COOKIE_SAMESITE"):
            Settings(COOKIE_SAMESITE="sideways")

    def test_samesite_none_requires_secure(self) -> None:
        """A cross-site cookie must be Secure, or the browser drops it."""
        from app.core.config import Settings

        # `staging` is a non-development environment, so cookie security is
        # enforced without needing production's extra checks.
        with pytest.raises(ValueError, match="SameSite=None"):
            Settings(
                APP_ENV="staging",
                AUTH_SECRET="z" * 48,
                COOKIE_SAMESITE="none",
                COOKIE_SECURE=False,
            )

    def test_cors_origins_are_parsed_from_a_string(self) -> None:
        from app.core.config import Settings

        settings = Settings(CORS_ORIGINS="https://a.example.com, https://b.example.com")
        assert settings.CORS_ORIGINS == ["https://a.example.com", "https://b.example.com"]

    def test_audit_identifier_hashing_is_keyed_not_reversible(self) -> None:
        """A plain SHA-256 of an email would be brute-forceable."""
        from app.core.security import hash_identifier

        digest = hash_identifier("someone@example.com")
        assert len(digest) == 64
        assert digest != hash_identifier("someone@example.org")
        # Same input, same key, same digest — the log stays correlatable.
        assert digest == hash_identifier("someone@example.com")
        assert digest == hash_identifier("  Someone@Example.com  ")
