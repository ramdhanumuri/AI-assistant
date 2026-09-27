"""Projects, knowledge sources, tools and memory endpoints.

Every route requires a session. Reads of shared reference data (knowledge
sources, tool integrations) are global; anything that describes the caller's own
content — projects and memory records — is owner-scoped. Writes are
CSRF-protected because they are reachable with a cookie.
"""

from typing import Annotated

from fastapi import APIRouter, Query, Request, status

from app.api.cookies import enforce_csrf
from app.api.deps import CatalogServiceDep, CurrentUser
from app.schemas.catalog import (
    KnowledgeSourceRead,
    MemoryRecordCreate,
    MemoryRecordRead,
    ProjectCreate,
    ProjectRead,
    ToolIntegrationRead,
    ToolIntegrationUpdate,
)

projects_router = APIRouter(prefix="/projects", tags=["Projects"])
knowledge_router = APIRouter(prefix="/knowledge", tags=["Knowledge"])
tools_router = APIRouter(prefix="/tools", tags=["Tools"])
memory_router = APIRouter(prefix="/memory", tags=["Memory"])


# ── Projects ──────────────────────────────────────────────────────────


@projects_router.get("", response_model=list[ProjectRead], summary="List workstreams")
def list_projects(service: CatalogServiceDep, identity: CurrentUser) -> list[ProjectRead]:
    return service.list_projects(owner_id=identity.id)


@projects_router.post(
    "",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a workstream",
)
def create_project(
    payload: ProjectCreate,
    request: Request,
    service: CatalogServiceDep,
    identity: CurrentUser,
) -> ProjectRead:
    enforce_csrf(request)
    project = service.create_project(payload)
    return ProjectRead(
        id=project.id,
        name=project.name,
        brief=project.brief,
        progress=project.progress,
        accent=project.accent,
        threads=0,
    )


# ── Knowledge ─────────────────────────────────────────────────────────


@knowledge_router.get("", response_model=list[KnowledgeSourceRead], summary="List knowledge sources")
def list_knowledge(
    service: CatalogServiceDep,
    identity: CurrentUser,
    kind: Annotated[str | None, Query(description="document | repository | dataset | feed")] = None,
    status_filter: Annotated[
        str | None,
        Query(alias="status", description="indexed | indexing | paused"),
    ] = None,
) -> list[KnowledgeSourceRead]:
    return [
        KnowledgeSourceRead.model_validate(k)
        for k in service.list_knowledge(kind=kind, status=status_filter)
    ]


# ── Tools ─────────────────────────────────────────────────────────────


@tools_router.get("", response_model=list[ToolIntegrationRead], summary="List tool integrations")
def list_tools(
    service: CatalogServiceDep,
    identity: CurrentUser,
    connected: Annotated[bool | None, Query(description="Filter by connection state.")] = None,
) -> list[ToolIntegrationRead]:
    return [
        ToolIntegrationRead.model_validate(t) for t in service.list_tools(connected=connected)
    ]


@tools_router.patch("/{tool_id}", response_model=ToolIntegrationRead, summary="Update a tool")
def update_tool(
    tool_id: str,
    payload: ToolIntegrationUpdate,
    request: Request,
    service: CatalogServiceDep,
    identity: CurrentUser,
) -> ToolIntegrationRead:
    enforce_csrf(request)
    return ToolIntegrationRead.model_validate(service.update_tool(tool_id, payload))


# ── Memory ────────────────────────────────────────────────────────────


@memory_router.get("", response_model=list[MemoryRecordRead], summary="List memory records")
def list_memory(
    service: CatalogServiceDep,
    identity: CurrentUser,
    scope: Annotated[str | None, Query(description="Filter by scope.")] = None,
) -> list[MemoryRecordRead]:
    return [
        service.memory_read(r)
        for r in service.list_memory(owner_id=identity.id, scope=scope)
    ]


@memory_router.post(
    "",
    response_model=MemoryRecordRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record a memory",
)
def create_memory(
    payload: MemoryRecordCreate,
    request: Request,
    service: CatalogServiceDep,
    identity: CurrentUser,
) -> MemoryRecordRead:
    enforce_csrf(request)
    return service.memory_read(service.create_memory(payload, owner_id=identity.id))


@memory_router.delete(
    "/{memory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Forget a memory record",
)
def delete_memory(
    memory_id: str,
    request: Request,
    service: CatalogServiceDep,
    identity: CurrentUser,
) -> None:
    enforce_csrf(request)
    service.delete_memory(memory_id, owner_id=identity.id)