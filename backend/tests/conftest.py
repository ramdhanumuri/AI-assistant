"""Test fixtures.

Tests run against a real SQLite file and the real application object — no
dependency overrides, no mocks. `DATABASE_URL` is pointed at a temporary file
before `app` is imported so the module-level engine binds to a throwaway
database instead of the developer's `aurelis.db`.

Each test starts from a clean, seeded schema, so assertions can rely on the
counts the seed produces.
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

from fastapi.testclient import TestClient  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.seed import seed_all  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402

# NOTE: `app.main` already imports the model package, which is what registers
# the mappers on `Base.metadata`. A bare `import app.models` here would rebind
# the name `app` to the package and shadow the FastAPI instance.


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
    yield


@pytest.fixture
def client(db: None) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def session(db: None) -> Iterator:
    with SessionLocal() as db_session:
        yield db_session