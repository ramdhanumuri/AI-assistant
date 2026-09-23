"""Intelligence mode endpoints.

Modes are reference data. Exposing them over HTTP means the frontend's
`AI_MODES` constant becomes a cache rather than a source of truth, and MODULE 10
can manage the palette without a client release.
"""

from fastapi import APIRouter

from app.api.deps import CatalogServiceDep
from app.schemas.catalog import ModeRead

router = APIRouter(prefix="/modes", tags=["Modes"])


@router.get("", response_model=list[ModeRead], summary="List intelligence modes")
def list_modes(service: CatalogServiceDep) -> list[ModeRead]:
    return [service.mode_read(mode) for mode in service.list_modes()]


@router.get("/{mode_id}", response_model=ModeRead, summary="Get one mode")
def get_mode(mode_id: str, service: CatalogServiceDep) -> ModeRead:
    return service.mode_read(service.get_mode_or_404(mode_id))