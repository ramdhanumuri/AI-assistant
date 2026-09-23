"""Conversation and message endpoints.

This is the write path the chat surface will use: create a thread, post a
turn, read the transcript. The assistant's reply is generated server-side by
the engine seam, so the client never synthesises content.
"""

from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import ConversationServiceDep, Pagination, page
from app.schemas.common import Page
from app.schemas.conversation import (
    ConversationCreate,
    ConversationRead,
    ConversationUpdate,
    MessageCreate,
    MessageRead,
    TurnResult,
)

router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.get("", response_model=Page[ConversationRead], summary="List conversations")
def list_conversations(
    service: ConversationServiceDep,
    pagination: Pagination,
    include_archived: Annotated[
        bool, Query(alias="includeArchived", description="Include archived threads.")
    ] = False,
    pinned: Annotated[bool | None, Query(description="Filter by pinned state.")] = None,
    project_id: Annotated[
        str | None, Query(alias="projectId", description="Filter by project.")
    ] = None,
    mode_id: Annotated[
        str | None, Query(alias="modeId", description="Filter by intelligence mode.")
    ] = None,
    search: Annotated[
        str | None, Query(description="Substring match on title/preview.")
    ] = None,
) -> Page[ConversationRead]:
    rows, total = service.list_conversations(
        include_archived=include_archived,
        pinned=pinned,
        project_id=project_id,
        mode_id=mode_id,
        search=search,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return Page[ConversationRead](
        **page([ConversationRead.model_validate(r) for r in rows], total, pagination)
    )


@router.post(
    "",
    response_model=ConversationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a conversation",
)
def create_conversation(
    payload: ConversationCreate, service: ConversationServiceDep
) -> ConversationRead:
    return ConversationRead.model_validate(service.create(payload))


@router.get("/{conversation_id}", response_model=ConversationRead, summary="Get a conversation")
def get_conversation(
    conversation_id: str, service: ConversationServiceDep
) -> ConversationRead:
    return ConversationRead.model_validate(service.get_or_404(conversation_id))


@router.patch("/{conversation_id}", response_model=ConversationRead, summary="Update a conversation")
def update_conversation(
    conversation_id: str,
    payload: ConversationUpdate,
    service: ConversationServiceDep,
) -> ConversationRead:
    return ConversationRead.model_validate(service.update(conversation_id, payload))


@router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a conversation and its messages",
)
def delete_conversation(conversation_id: str, service: ConversationServiceDep) -> None:
    service.delete(conversation_id)


@router.get(
    "/{conversation_id}/messages",
    response_model=Page[MessageRead],
    summary="Read a conversation transcript",
)
def list_messages(
    conversation_id: str, service: ConversationServiceDep, pagination: Pagination
) -> Page[MessageRead]:
    rows, total = service.list_messages(
        conversation_id, limit=pagination.limit, offset=pagination.offset
    )
    return Page[MessageRead](
        **page([MessageRead.model_validate(r) for r in rows], total, pagination)
    )


@router.post(
    "/{conversation_id}/messages",
    response_model=TurnResult,
    status_code=status.HTTP_201_CREATED,
    summary="Post a turn and receive the assistant's reply",
)
def post_message(
    conversation_id: str, payload: MessageCreate, service: ConversationServiceDep
) -> TurnResult:
    user_message, assistant_message, conversation = service.post_message(
        conversation_id, payload
    )
    return TurnResult(
        user_message=MessageRead.model_validate(user_message),
        assistant_message=MessageRead.model_validate(assistant_message),
        conversation=ConversationRead.model_validate(conversation),
    )