"""Projects, knowledge sources, tools and memory endpoints."""

from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import CatalogServiceDep
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
def list_projects(service: CatalogServiceDep) -> list[ProjectRead]:
    return service.list_projects()


@projects_router.post(
    "",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a workstream",
)
def create_project(payload: ProjectCreate, service: CatalogServiceDep) -> ProjectRead:
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
    connected: Annotated[bool | None, Query(description="Filter by connection state.")] = None,
) -> list[ToolIntegrationRead]:
    return [
        ToolIntegrationRead.model_validate(t) for t in service.list_tools(connected=connected)
    ]


@tools_router.patch("/{tool_id}", response_model=ToolIntegrationRead, summary="Update a tool")
def update_tool(
    tool_id: str, payload: ToolIntegrationUpdate, service: CatalogServiceDep
) -> ToolIntegrationRead:
    return ToolIntegrationRead.model_validate(service.update_tool(tool_id, payload))


# ── Memory ────────────────────────────────────────────────────────────


@memory_router.get("", response_model=list[MemoryRecordRead], summary="List memory records")
def list_memory(
    service: CatalogServiceDep,
    scope: Annotated[str | None, Query(description="Filter by scope.")] = None,
) -> list[MemoryRecordRead]:
    return [service.memory_read(r) for r in service.list_memory(scope=scope)]


@memory_router.post(
    "",
    response_model=MemoryRecordRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record a memory",
)
def create_memory(
    payload: MemoryRecordCreate, service: CatalogServiceDep
) -> MemoryRecordRead:
    return service.memory_read(service.create_memory(payload))


@memory_router.delete(
    "/{memory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Forget a memory record",
)
def delete_memory(memory_id: str, service: CatalogServiceDep) -> None:
    service.delete_memory(memory_id)