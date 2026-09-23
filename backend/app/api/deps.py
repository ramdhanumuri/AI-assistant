"""Shared route dependencies and response helpers."""

from typing import Annotated, TypeVar

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.catalog import CatalogService
from app.services.conversations import ConversationService

DbSession = Annotated[Session, Depends(get_db)]

T = TypeVar("T")


class LimitOffset:
    """Reusable pagination query parameters."""

    def __init__(
        self,
        limit: Annotated[int, Query(ge=1, le=200, description="Page size.")] = 50,
        offset: Annotated[int, Query(ge=0, description="Rows to skip.")] = 0,
    ) -> None:
        self.limit = limit
        self.offset = offset


Pagination = Annotated[LimitOffset, Depends()]


def get_conversation_service(db: DbSession) -> ConversationService:
    return ConversationService(db)


def get_catalog_service(db: DbSession) -> CatalogService:
    return CatalogService(db)


ConversationServiceDep = Annotated[ConversationService, Depends(get_conversation_service)]
CatalogServiceDep = Annotated[CatalogService, Depends(get_catalog_service)]


def page(items: list[T], total: int, pagination: LimitOffset) -> dict[str, object]:
    return {
        "items": items,
        "total": total,
        "limit": pagination.limit,
        "offset": pagination.offset,
    }


__all__ = [
    "CatalogServiceDep",
    "ConversationServiceDep",
    "DbSession",
    "LimitOffset",
    "Pagination",
    "page",
]