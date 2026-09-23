"""Dashboard aggregate endpoint."""

from fastapi import APIRouter

from app.api.deps import CatalogServiceDep
from app.schemas.catalog import DashboardSummary

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get(
    "/summary",
    response_model=DashboardSummary,
    summary="Aggregate metrics, activity, knowledge and tools",
)
def summary(service: CatalogServiceDep) -> DashboardSummary:
    return service.summary()