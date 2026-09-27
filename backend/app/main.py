"""FastAPI application factory.

Wiring order matters: logging and error handlers are installed before routers
so failures during route handling are formatted consistently, and the
middleware stack is built so security headers wrap every response — including
CORS preflights and error responses — and CORS is added last so it wraps the
headers too.

MODULE 4 adds `SecurityHeadersMiddleware` and extends the documented tag list
with the authentication and administration surfaces.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.request_context import RequestContextMiddleware
from app.core.security_headers import SecurityHeadersMiddleware

TAGS_METADATA = [
    {"name": "Health", "description": "Liveness and readiness probes."},
    {"name": "System", "description": "Service metadata and model-provider status."},
    {
        "name": "Authentication",
        "description": "Registration, login, sessions, passwords and the audit-safe current user.",
    },
    {"name": "Users", "description": "The authenticated user's own profile and preferences."},
    {"name": "Administration", "description": "Administrator-only account, usage and audit endpoints."},
    {"name": "Modes", "description": "Intelligence modes and their design tokens."},
    {
        "name": "Conversations",
        "description": "Chat threads, transcripts and assistant turns.",
    },
    {"name": "Dashboard", "description": "Aggregated metrics, activity and usage."},
    {"name": "Projects", "description": "Long-running workstreams."},
    {"name": "Knowledge", "description": "Indexed context sources."},
    {"name": "Tools", "description": "External integrations the assistant can call."},
    {"name": "Memory", "description": "Durable, scoped facts about the user."},
]


def create_app() -> FastAPI:
    configure_logging()
    logger = get_logger(__name__)

    # The interactive docs are a development tool: they enumerate every schema
    # and endpoint, which is free reconnaissance in production. Served by
    # default locally and hidden outside it unless explicitly re-enabled.
    docs_enabled = settings.docs_enabled

    app = FastAPI(
        title=settings.APP_NAME,
        version="5.0.0",
        description=(
            "Backend for AURELIS. Module 2 delivered the persistence layer, "
            "the chat write path and the model-provider seam; Module 3 put the "
            "schema on Supabase; Module 4 adds authentication (Argon2id "
            "passwords, short-lived access tokens, rotating refresh sessions) "
            "and server-enforced authorization; Module 5 hardens the whole "
            "stack (distributed rate limiting, refresh-token reuse detection, "
            "strict CORS/CSP/CSRF, safe errors and security-event logging)."
        ),
        openapi_tags=TAGS_METADATA,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
        contact={"name": "AURELIS Platform"},
        license_info={"name": "Proprietary"},
    )

    register_exception_handlers(app)

    # Middleware order. Starlette makes the last-added middleware outermost, so
    # from outside in the stack is: CORS → security headers → request context.
    #   * CORS outermost so a rejected response (a 413 from the body guard, a
    #     401, a preflight) still carries the CORS headers a browser needs.
    #   * Security headers next so *every* response — including the request
    #     context's own 413 — is decorated.
    #   * Request context innermost: it assigns the id before routing and stamps
    #     it on every response that passes back out.
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        # Explicit methods/headers rather than `*`: with credentials, a wildcard
        # is invalid per the CORS spec and hides which verbs are actually
        # reachable. These are exactly the ones the API serves.
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Accept",
            settings.CSRF_HEADER_NAME,
            "X-Request-ID",
        ],
        expose_headers=["Retry-After", "X-Request-ID"],
    )

    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    if docs_enabled:
        _install_openapi(app)

    logger.info(
        "%s ready | env=%s | provider=%s | db=%s | cookies=%s/%s | docs=%s | cors_origins=%d",
        settings.APP_NAME,
        settings.APP_ENV,
        settings.AI_PROVIDER,
        settings.DATABASE_URL.split("://", 1)[0],
        settings.cookie_samesite,
        "secure" if settings.is_cookie_secure else "insecure",
        "on" if docs_enabled else "off",
        len(settings.CORS_ORIGINS),
    )
    if settings.is_production and not settings.CORS_ORIGINS:
        logger.warning("CORS_ORIGINS is empty in production; no browser origin will be allowed")
    return app


def _install_openapi(app: FastAPI) -> None:
    """Attach a cached OpenAPI schema.

    FastAPI rebuilds the schema on every `/docs` hit; caching keeps the docs
    endpoint cheap once the schema stops changing at runtime.
    """

    def custom_openapi() -> dict:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            tags=TAGS_METADATA,
            routes=app.routes,
            contact=app.contact,
            license_info=app.license_info,
        )
        schema.setdefault("servers", [{"url": "/", "description": "Current host"}])
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi  # type: ignore[method-assign]


app = create_app()