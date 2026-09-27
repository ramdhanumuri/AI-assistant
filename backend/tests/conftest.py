"""Test fixtures.

Tests run against a real SQLite file and the real application object — no
dependency overrides for the application itself, no mocks of the auth layer.
`DATABASE_URL` is pointed at a temporary file before `app` is imported so the
module-level engine binds to a throwaway database instead of the developer's
`aurelis.db`.

MODULE 4 makes the conversation and dashboard surface authenticated, so the
`client` fixture signs in. That is deliberate rather than convenient: the
existing Module 2/3 behaviour is still verified, but through a real session
established by the real login endpoint. Nothing about authentication is stubbed
out to make an older test pass.

The identity used is a normal user, not an administrator — a fixture that
silently granted admin would hide exactly the privilege bug these tests exist to
catch.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

_TMP_DIR = Path(tempfile.mkdtemp(prefix="aurelis-tests-"))
_DB_PATH = _TMP_DIR / "test.db"

# Must be set before any `app.*` import so config and the engine pick it up.
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"
os.environ["APP_ENV"] = "test"
os.environ["DEBUG"] = "false"
# Argon2 at production cost would make a suite this size unusably slow. The
# algorithm is unchanged — only the work factor is reduced for tests, and the
# hashing tests assert the parameterisation separately.
os.environ.setdefault("PASSWORD_HASH_MEMORY_KIB", "8192")
os.environ.setdefault("PASSWORD_HASH_TIME_COST", "1")
os.environ.setdefault("PASSWORD_HASH_PARALLELISM", "1")

from fastapi.testclient import TestClient  # noqa: E402

from app.api.cookies import CSRF_TOKEN_BYTES  # noqa: E402,F401  (documentation)
from app.core.config import settings  # noqa: E402
from app.core.ratelimit import reset_limiter  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.seed import seed_all  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402

# NOTE: `app.main` already imports the model package, which is what registers
# the mappers on `Base.metadata`. A bare `import app.models` here would rebind
# the name `app` to the package and shadow the FastAPI instance.

# A password that satisfies the shared policy without being on the deny-list.
TEST_PASSWORD = "Vermilion-Lattice-42"
ADMIN_PASSWORD = "Obsidian-Meridian-77"

CSRF_HEADER = settings.CSRF_HEADER_NAME
CSRF_COOKIE = settings.CSRF_COOKIE_NAME


@pytest.fixture(scope="session")
def db_path() -> Path:
    return _DB_PATH


@pytest.fixture
def db() -> Iterator[None]:
    """Rebuild the schema and reseed before every test."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        seed_all(session, reset=True)
    # Rate-limit counters are process-global; a fresh database means a fresh
    # budget, otherwise one test's failed logins would throttle the next.
    reset_limiter()
    yield


@pytest.fixture
def anon_client(db: None) -> Iterator[TestClient]:
    """An unauthenticated client. Use this to test that protection works."""
    with TestClient(app) as test_client:
        yield test_client


def _csrf_headers(client: TestClient) -> dict[str, str]:
    """Header pair for a state-changing request from a cookie client."""
    token = client.cookies.get(CSRF_COOKIE)
    return {CSRF_HEADER: token} if token else {}


def add_second_user(
    client: TestClient, *, email: str, password: str = TEST_PASSWORD
) -> TestClient:
    """Create an account and return a client holding *only* that session.

    Registering on an existing client would replace its cookies, which silently
    turns "the first user" into "the second user" and makes an ownership test
    pass for the wrong reason. This builds a separate jar and leaves the caller's
    client untouched.
    """
    other = TestClient(client.app)
    register_user(other, email=email, password=password)
    arm_csrf(other)
    return other


def arm_csrf(client: TestClient) -> None:
    """Mirror what the SPA does: echo the CSRF cookie on every request.

    The frontend reads `aurelis_csrf` (it is the one cookie that is not
    HttpOnly) and attaches it as a header. Setting it on the client's default
    headers is the same thing without repeating it per call.
    """
    headers = _csrf_headers(client)
    assert headers, "no CSRF cookie was set; did authentication succeed?"
    client.headers.update(headers)


def register_user(
    client: TestClient,
    *,
    email: str,
    password: str = TEST_PASSWORD,
    full_name: str = "Test Operator",
) -> dict:
    """Create an account through the real endpoint and return the auth state."""
    response = client.post(
        "/api/v1/auth/register",
        json={"full_name": full_name, "email": email, "password": password},
    )
    assert response.status_code == 201, response.text
    return response.json()


def login(client: TestClient, *, email: str, password: str = TEST_PASSWORD) -> dict:
    response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()


def promote_to_admin(email: str) -> str:
    """Promote an existing account via the real provisioning path.

    Uses the CLI's `provision` function rather than writing `role = "admin"`
    directly, so the promotion also exercises the same code an operator runs.
    """
    from app.cli.create_admin import provision

    assert provision(email, ADMIN_PASSWORD, "Test Administrator") == 0
    with SessionLocal() as session:
        from sqlalchemy import select

        from app.models import User

        user = session.scalar(select(User).where(User.email == email.lower()))
        assert user is not None
        return user.id


@pytest.fixture
def client(db: None) -> Iterator[TestClient]:
    """An authenticated client holding a normal user's session.

    This is the fixture the Module 2/3 suites use. The user is explicitly
    *not* an administrator.
    """
    with TestClient(app) as test_client:
        register_user(test_client, email="operator@aurelis.dev")
        arm_csrf(test_client)
        yield test_client


@pytest.fixture
def admin_client(db: None) -> Iterator[TestClient]:
    """An authenticated client holding an administrator's session.

    The account is created, promoted, then signed in — in that order — so the
    client's cookie jar ends up holding the *administrator's* session and not
    the registration session it started with.
    """
    with TestClient(app) as test_client:
        register_user(test_client, email="admin@aurelis.dev")
        promote_to_admin("admin@aurelis.dev")
        login(test_client, email="admin@aurelis.dev", password=ADMIN_PASSWORD)
        arm_csrf(test_client)
        assert test_client.get("/api/v1/auth/me").json()["user"]["role"] == "admin"
        yield test_client


@pytest.fixture
def session(db: None) -> Iterator:
    with SessionLocal() as db_session:
        yield db_session
