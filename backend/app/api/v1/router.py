"""v1 router assembly.

Every feature router is mounted here under one prefix, so versioning,
authentication (MODULE 4) and rate limiting (MODULE 5) can be applied at a
single seam rather than per route.
"""

from fastapi import APIRouter

from app.api.v1 import catalog, conversations, dashboard, health, modes, system

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(system.router)
api_router.include_router(modes.router)
api_router.include_router(conversations.router)
api_router.include_router(dashboard.router)
api_router.include_router(catalog.projects_router)
api_router.include_router(catalog.knowledge_router)
api_router.include_router(catalog.tools_router)
api_router.include_router(catalog.memory_router)