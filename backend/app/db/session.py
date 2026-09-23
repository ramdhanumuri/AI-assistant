"""Engine, session factory and the FastAPI session dependency.

One place owns connection concerns so MODULE 3 can move to a pooled
PostgreSQL deployment (and MODULE 4 can add per-request identity) without
touching repositories or routes.
"""

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.base import Base

_connect_args: dict[str, object] = {}
_engine_kwargs: dict[str, object] = {}

if settings.is_sqlite:
    # SQLite is single-file and used for local dev/test only, so the default
    # thread check must be relaxed for FastAPI's threadpool.
    _connect_args["check_same_thread"] = False
else:
    # Production target (PostgreSQL) gets real pooling.
    _engine_kwargs.update(pool_pre_ping=True, pool_size=5, max_overflow=10)

engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    connect_args=_connect_args,
    **_engine_kwargs,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection: object, _: object) -> None:
    """SQLite ignores FK constraints unless explicitly enabled per connection."""
    if not settings.is_sqlite:
        return
    cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_db() -> Generator[Session, None, None]:
    """Yield a request-scoped session and always close it."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def create_all() -> None:
    """Create tables from metadata.

    Alembic owns schema evolution; this exists so test fixtures and a
    first-run dev bootstrap can stand the schema up without the CLI.
    """
    import app.models  # noqa: F401  (register mappers before create_all)

    Base.metadata.create_all(bind=engine)