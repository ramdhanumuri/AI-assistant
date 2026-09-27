"""v1 router assembly.

Every feature router is mounted here under one prefix, so versioning and rate
limiting can be applied at a single seam rather than per route.

Protection is applied per route (via the `CurrentUser` / `AdminUser`
dependencies) rather than as a blanket prefix guard, because the same prefix
carries public reference data the frontend reads before login. The one rule
that matters: a router handling user content declares its dependency
explicitly, so adding an endpoint without one is a visible omission rather than
a silent hole.
"""

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    auth,
    catalog,
    conversations,
    dashboard,
    health,
    modes,
    system,
    users,
)

api_router = APIRouter()
# Public: probes, service metadata, and the authentication endpoints.
api_router.include_router(health.router)
api_router.include_router(system.router)
api_router.include_router(auth.router)
# Authenticated identity surface.
api_router.include_router(users.router)
# Reference data the UI themes itself from before login.
api_router.include_router(modes.router)
# User content: every route in these two requires a session.
api_router.include_router(conversations.router)
api_router.include_router(dashboard.router)
api_router.include_router(catalog.projects_router)
api_router.include_router(catalog.knowledge_router)
api_router.include_router(catalog.tools_router)
api_router.include_router(catalog.memory_router)
# Administrator-only.
api_router.include_router(admin.router)