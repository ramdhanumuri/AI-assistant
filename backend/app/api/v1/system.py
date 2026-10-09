"""Service metadata endpoints.

Exposes what the deployment is running and which model provider is wired in.
Useful for the frontend to detect a backend, and for MODULE 12 health dashboards.

STEP 6 reports the AI layer's *capability*, never its credentials: the provider
name, the resolved model, and whether the provider is configured. The API key
and base URL are deliberately absent from every response.
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
    ai_configured: bool = False
    ai_streaming_enabled: bool = True
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
        ai_model=settings.ai_model_resolved or None,
        ai_configured=settings.ai_configured,
        ai_streaming_enabled=settings.AI_STREAMING_ENABLED,
        available_providers=list_providers(),
        supabase=SupabaseInfo(**supabase.client_info()),
        docs_url="/docs",
    )