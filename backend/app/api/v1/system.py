"""Service metadata endpoints.

Exposes what the deployment is running and which model provider is wired in.
Useful for the frontend to detect a backend, and for MODULE 12 health dashboards.
"""

from fastapi import APIRouter
from pydantic import Field

from app.core.config import settings
from app.db import supabase
from app.schemas.common import APIModel
from app.services.engine import list_providers

router = APIRouter(prefix="/system", tags=["System"])


class SupabaseInfo(APIModel):
    configured: bool
    url: str | None = None
    service_role_configured: bool = False


class SystemInfo(APIModel):
    name: str
    env: str
    api_version: str
    ai_provider: str
    ai_model: str | None = None
    available_providers: list[str] = Field(default_factory=list)
    supabase: SupabaseInfo
    docs_url: str


@router.get("/info", response_model=SystemInfo, summary="Service metadata")
def info() -> SystemInfo:
    return SystemInfo(
        name=settings.APP_NAME,
        env=settings.APP_ENV,
        api_version="v1",
        ai_provider=settings.AI_PROVIDER,
        ai_model=settings.AI_MODEL or None,
        available_providers=list_providers(),
        supabase=SupabaseInfo(**supabase.client_info()),
        docs_url="/docs",
    )