"""Health and readiness probes.

`/health` is liveness (process is up). `/health/ready` additionally pings the
database, which is what MODULE 12's orchestrator should gate traffic on.
"""

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.api.deps import DbSession
from app.core.config import settings
from app.db import supabase
from app.schemas.common import HealthResponse

router = APIRouter(tags=["Health"])

VERSION = "2.0.0"


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        app=settings.APP_NAME,
        env=settings.APP_ENV,
        database="unknown",
        version=VERSION,
    )


@router.get(
    "/health/ready",
    response_model=HealthResponse,
    summary="Readiness probe (includes database)",
    responses={503: {"description": "Database unreachable"}},
)
def readiness(db: DbSession, response: Response) -> HealthResponse:
    database = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001  (any driver failure means "not ready")
        database = "unavailable"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    # Supabase is probed for visibility only; SQLAlchemy is the path the API
    # serves traffic from, so this never decides readiness.
    supabase_state = supabase.probe()

    return HealthResponse(
        status="ok" if database == "ok" else "degraded",
        app=settings.APP_NAME,
        env=settings.APP_ENV,
        database=database,
        version=VERSION,
        supabase=supabase_state,
    )