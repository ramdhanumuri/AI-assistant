"""FastAPI application factory.

Wiring order matters: logging and error handlers are installed before routers
so failures during route handling are formatted consistently, and CORS is added
last so it wraps every response including error responses.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger

TAGS_METADATA = [
    {"name": "Health", "description": "Liveness and readiness probes."},
    {"name": "System", "description": "Service metadata and model-provider status."},
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
        version="2.0.0",
        description=(
            "Backend foundation for AURELIS. Module 2 delivers the persistence "
            "layer, the chat write path, reference-data endpoints and the "
            "model-provider seam that later modules extend."
        ),
        openapi_tags=TAGS_METADATA,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        contact={"name": "AURELIS Platform"},
        license_info={"name": "Proprietary"},
    )

    register_exception_handlers(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    _install_openapi(app)

    logger.info(
        "%s ready | env=%s | provider=%s | db=%s",
        settings.APP_NAME,
        settings.APP_ENV,
        settings.AI_PROVIDER,
        settings.DATABASE_URL.split("://", 1)[0],
    )
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