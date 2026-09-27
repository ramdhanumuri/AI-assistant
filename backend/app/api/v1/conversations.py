"""Conversation and message endpoints.

This is the write path the chat surface uses: create a thread, post a turn,
read the transcript. The assistant's reply is generated server-side by the
engine seam, so the client never synthesises content.

Every route depends on `CurrentUser`, and the owner id comes from that identity
— never from the request. A thread belonging to someone else is reported as
404, not 403, so the API does not confirm that another account's id exists.
"""

from typing import Annotated

from fastapi import APIRouter, Query, Request, status

from app.api.cookies import enforce_csrf
from app.api.deps import ConversationServiceDep, CurrentUser, Pagination, page, user_rate_limit
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

AUTH_RESPONSES = {401: {"description": "Authentication required"}}


@router.get(
    "",
    response_model=Page[ConversationRead],
    summary="List conversations",
    responses=AUTH_RESPONSES,
)
def list_conversations(
    service: ConversationServiceDep,
    identity: CurrentUser,
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
        owner_id=identity.id,
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
    responses=AUTH_RESPONSES,
)
def create_conversation(
    payload: ConversationCreate,
    request: Request,
    service: ConversationServiceDep,
    identity: CurrentUser,
) -> ConversationRead:
    enforce_csrf(request)
    user_rate_limit(identity, scope="write")
    # The owner comes from the session, so a client cannot create a thread on
    # another account's behalf.
    return ConversationRead.model_validate(service.create(payload, owner_id=identity.id))


@router.get(
    "/{conversation_id}",
    response_model=ConversationRead,
    summary="Get a conversation",
    responses={404: {"description": "Not found, or not owned by the caller"}},
)
def get_conversation(
    conversation_id: str, service: ConversationServiceDep, identity: CurrentUser
) -> ConversationRead:
    return ConversationRead.model_validate(
        service.get_or_404(conversation_id, owner_id=identity.id)
    )


@router.patch(
    "/{conversation_id}",
    response_model=ConversationRead,
    summary="Update a conversation",
)
def update_conversation(
    conversation_id: str,
    payload: ConversationUpdate,
    request: Request,
    service: ConversationServiceDep,
    identity: CurrentUser,
) -> ConversationRead:
    enforce_csrf(request)
    return ConversationRead.model_validate(
        service.update(conversation_id, payload, owner_id=identity.id)
    )


@router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a conversation and its messages",
)
def delete_conversation(
    conversation_id: str,
    request: Request,
    service: ConversationServiceDep,
    identity: CurrentUser,
) -> None:
    enforce_csrf(request)
    service.delete(conversation_id, owner_id=identity.id)


@router.get(
    "/{conversation_id}/messages",
    response_model=Page[MessageRead],
    summary="Read a conversation transcript",
)
def list_messages(
    conversation_id: str,
    service: ConversationServiceDep,
    identity: CurrentUser,
    pagination: Pagination,
) -> Page[MessageRead]:
    rows, total = service.list_messages(
        conversation_id,
        owner_id=identity.id,
        limit=pagination.limit,
        offset=pagination.offset,
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
    conversation_id: str,
    payload: MessageCreate,
    request: Request,
    service: ConversationServiceDep,
    identity: CurrentUser,
) -> TurnResult:
    enforce_csrf(request)
    # The AI request path: a separate budget from ordinary writes so a runaway
    # client cannot exhaust the write scope with generated turns.
    user_rate_limit(identity, scope="ai")
    user_message, assistant_message, conversation = service.post_message(
        conversation_id, payload, owner_id=identity.id
    )
    return TurnResult(
        user_message=MessageRead.model_validate(user_message),
        assistant_message=MessageRead.model_validate(assistant_message),
        conversation=ConversationRead.model_validate(conversation),
    )
