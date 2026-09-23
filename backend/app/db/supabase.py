"""Supabase client seam (MODULE 3).

Only the pieces the backend actually needs are built here:

* ``supabase_settings()`` — a validated view of the Supabase configuration.
* ``probe()`` — a lightweight reachability check used by ``/health/ready``.

Row-level data access stays in SQLAlchemy. The service-role client is what a
future module would use for privileged server-side work (storage, Realtime
broadcasts, admin tasks) where PostgREST is a better fit than SQL.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import httpx

from app.core.config import get_settings

_TIMEOUT = httpx.Timeout(5.0)


@dataclass(frozen=True)
class SupabaseSettings:
    url: str
    anon_key: str
    service_role_key: str

    @property
    def rest_url(self) -> str:
        return f"{self.url.rstrip('/')}/rest/v1"


def supabase_settings() -> SupabaseSettings:
    # Read through `get_settings()` rather than importing the module-level
    # singleton, so a config change (and tests) take effect without the caller
    # needing to reimport this module.
    settings = get_settings()
    return SupabaseSettings(
        url=settings.SUPABASE_URL.strip(),
        anon_key=settings.SUPABASE_ANON_KEY.strip(),
        service_role_key=settings.SUPABASE_SERVICE_ROLE_KEY.strip(),
    )


def is_configured() -> bool:
    return get_settings().is_supabase_configured


def auth_headers(*, service_role: bool = False) -> dict[str, str]:
    """Headers for a PostgREST call.

    ``service_role`` bypasses RLS, so callers must opt in explicitly and only
    on the server. The anon key is the RLS-respecting default.
    """
    cfg = supabase_settings()
    key = cfg.service_role_key if service_role else cfg.anon_key
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }


def probe() -> Literal["ok", "unconfigured", "unavailable"]:
    """Reach the PostgREST root without touching application tables.

    A 200 means the project is up. 401/404 still prove the host answered, which
    is what readiness cares about — a deliberately deny-by-default RLS setup
    returns 401 for the anon key and must not be reported as an outage.

    Never raises: readiness endpoints must not fail because an optional
    dependency is down.
    """
    if not is_configured():
        return "unconfigured"

    cfg = supabase_settings()
    try:
        response = httpx.get(
            f"{cfg.rest_url}/",
            headers=auth_headers(),
            timeout=_TIMEOUT,
        )
    except httpx.HTTPError:
        return "unavailable"

    if response.status_code in (200, 401, 403, 404):
        return "ok"
    return "unavailable"


def client_info() -> dict[str, Any]:
    """Non-secret description of the configured project, for /system/info."""
    cfg = supabase_settings()
    return {
        "configured": is_configured(),
        "url": cfg.url or None,
        "service_role_configured": bool(cfg.service_role_key),
    }


__all__ = [
    "SupabaseSettings",
    "auth_headers",
    "client_info",
    "is_configured",
    "probe",
    "supabase_settings",
]
