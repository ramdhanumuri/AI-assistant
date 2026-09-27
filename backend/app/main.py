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

    app = FastAPI(
        title=settings.APP_NAME,
        version="4.0.0",
        description=(
            "Backend for AURELIS. Module 2 delivered the persistence layer, "
            "the chat write path and the model-provider seam; Module 3 put the "
            "schema on Supabase; Module 4 adds authentication (Argon2id "
            "passwords, short-lived access tokens, rotating refresh sessions) "
            "and server-enforced authorization."
        ),
        openapi_tags=TAGS_METADATA,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        contact={"name": "AURELIS Platform"},
        license_info={"name": "Proprietary"},
    )

    register_exception_handlers(app)

    # Added before CORS so CORS ends up outermost and still decorates the
    # preflight response with the headers a browser needs.
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Retry-After"],
    )

    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    _install_openapi(app)

    logger.info(
        "%s ready | env=%s | provider=%s | db=%s | cookies=%s/%s",
        settings.APP_NAME,
        settings.APP_ENV,
        settings.AI_PROVIDER,
        settings.DATABASE_URL.split("://", 1)[0],
        settings.cookie_samesite,
        "secure" if settings.is_cookie_secure else "insecure",
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