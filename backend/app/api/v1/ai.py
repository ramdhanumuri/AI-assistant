"""AI endpoints: capabilities, streaming chat and usage.

The streaming chat endpoint lives here rather than beside the other
conversation routes because it has a different transport contract (SSE) and a
different failure model (a failure after the first byte cannot be an HTTP error
code). Keeping it separate makes that difference explicit rather than hiding it
behind a shared route decorator.

Validation ordering is the load-bearing detail. Everything that can fail with a
proper status code — authentication, CSRF, rate limiting, ownership, the model
allow-list and provider configuration — is checked **before** the response
starts, because once `200 OK` and the SSE headers are on the wire there is no
way to send a 404 or a 429. Only failures that can occur mid-generation are
reported as in-band `error` events.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from app.ai.factory import get_provider
from app.ai.orchestrator import AIOrchestrator
from app.ai.errors import AIError
from app.api.cookies import enforce_csrf
from app.api.deps import (
    AIServiceDep,
    ConversationServiceDep,
    CurrentUser,
    DbSession,
    user_rate_limit,
)
from app.api.sse import HEARTBEAT, sse_event
from app.core.config import settings
from app.core.errors import ServiceUnavailableError
from app.core.logging import get_logger
from app.schemas.ai import AICapabilities, AIUsageSummary
from app.schemas.conversation import (
    ConversationRead,
    MessageCreate,
    MessageRead,
    StreamDelta,
    StreamDone,
    StreamError,
    StreamMeta,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/ai", tags=["AI"])

AUTH_RESPONSES = {401: {"description": "Authentication required"}}

# SSE response headers. `no-store` keeps a private answer out of any cache;
# `X-Accel-Buffering: no` stops an upstream nginx from buffering the stream into
# one delayed blob, which would defeat streaming entirely.
_SSE_HEADERS = {
    "Cache-Control": "no-store",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


@router.get(
    "/capabilities",
    response_model=AICapabilities,
    summary="AI provider capabilities for the current deployment",
    responses=AUTH_RESPONSES,
)
def capabilities(_: CurrentUser, service: AIServiceDep) -> AICapabilities:
    """Whether the model layer is configured, and which model is in use.

    Returns no credential and no base URL — only what the UI needs to decide
    between the streaming transport and the synchronous one.
    """
    return service.capabilities()


@router.get(
    "/usage",
    response_model=AIUsageSummary,
    summary="The caller's own AI usage",
    responses=AUTH_RESPONSES,
)
def my_usage(
    identity: CurrentUser,
    service: AIServiceDep,
    window_days: int | None = Query(
        default=30, ge=1, le=365, description="Rolling window in days; omit for all time."
    ),
) -> AIUsageSummary:
    """Aggregated model usage for the signed-in account only.

    Owner-scoped by construction: the user id comes from the session, so this
    can never report another account's usage.
    """
    return service.usage_summary(user_id=identity.id, window_days=window_days)


@router.post(
    "/conversations/{conversation_id}/messages/stream",
    summary="Post a turn and stream the assistant's reply (SSE)",
    responses={
        **AUTH_RESPONSES,
        404: {"description": "Conversation not found, or not owned by the caller"},
        429: {"description": "Rate limited"},
        503: {"description": "The AI provider is not configured or unavailable"},
    },
    response_class=StreamingResponse,
)
async def stream_message(
    conversation_id: str,
    payload: MessageCreate,
    request: Request,
    service: ConversationServiceDep,
    identity: CurrentUser,
) -> StreamingResponse:
    """Stream a real model response over Server-Sent Events.

    Frames: `meta` (once), `delta` (0..n), then exactly one of `done` or
    `error`. The `meta` frame carries the persisted user message and the
    assistant placeholder id so the UI can render optimistically without a
    second round trip.
    """
    enforce_csrf(request)
    # The AI budget, not the ordinary write budget: a runaway client must not be
    # able to spend model quota at the write rate.
    user_rate_limit(identity, scope="ai")

    # Ownership first, so a probe for another account's thread id gets the same
    # 404 as a genuinely missing one — before any stream starts.
    service.get_or_404(conversation_id, owner_id=identity.id)

    # Provider configuration and the model allow-list are validated up front.
    # A missing key or a disallowed model must be a clean status code, not an
    # error frame the UI has to parse out of a 200 response.
    if not settings.ai_configured:
        raise ServiceUnavailableError(
            "The AI service is not configured. Please contact an administrator.",
            code="configuration_error",
        )
    try:
        orchestrator = AIOrchestrator(get_provider())
        orchestrator.resolve_model(payload.model)
    except AIError as exc:
        logger.warning("AI request rejected before streaming: %s", exc.code)
        raise ServiceUnavailableError(exc.message, code=exc.code) from exc

    # The request-scoped session closes when this function returns, but the body
    # of a StreamingResponse is consumed afterwards — so the stream opens and
    # owns its own session rather than borrowing one that is already gone.
    owner_id = identity.id

    async def event_stream() -> AsyncIterator[str]:
        from app.db.session import SessionLocal
        from app.services.conversations import ConversationService

        with SessionLocal() as session:
            stream_service = ConversationService(session)
            try:
                async for frame in stream_service.stream_message(
                    conversation_id, payload, owner_id=owner_id
                ):
                    yield _encode(frame)
            except AIError as exc:
                # A provider failure that escaped the service (for example a
                # context-too-large raised before the first frame).
                logger.warning("AI stream aborted: %s", exc.code)
                yield sse_event(
                    "error",
                    StreamError(
                        code=exc.code, message=exc.message, retryable=exc.retryable
                    ).model_dump(by_alias=True),
                )
            except Exception:  # noqa: BLE001 - never leak internals mid-stream
                logger.exception("Unexpected failure during AI stream")
                yield sse_event(
                    "error",
                    StreamError(
                        code="provider_unavailable",
                        message="The assistant is temporarily unavailable. Please try again.",
                        retryable=True,
                    ).model_dump(by_alias=True),
                )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


def _encode(frame: dict) -> str:
    """Serialise one service frame into an SSE event."""
    event = frame["event"]
    if event == "meta":
        return sse_event(
            "meta",
            StreamMeta(
                conversation_id=frame["conversation"].id,
                user_message=MessageRead.model_validate(frame["user_message"]),
                assistant_message=MessageRead.model_validate(frame["assistant_message"]),
                model=frame["model"] or "",
                provider=frame["provider"] or "",
                replayed=frame["replayed"],
            ).model_dump(by_alias=True),
        )
    if event == "delta":
        return sse_event("delta", StreamDelta(text=frame["text"]).model_dump(by_alias=True))
    if event == "done":
        return sse_event(
            "done",
            StreamDone(
                assistant_message=MessageRead.model_validate(frame["assistant_message"]),
                conversation=ConversationRead.model_validate(frame["conversation"]),
            ).model_dump(by_alias=True),
        )
    # error
    assistant = frame.get("assistant_message")
    return sse_event(
        "error",
        StreamError(
            code=frame["code"],
            message=frame["message"],
            retryable=frame["retryable"],
            assistant_message=(
                MessageRead.model_validate(assistant) if assistant is not None else None
            ),
        ).model_dump(by_alias=True),
    )


__all__ = ["HEARTBEAT", "router"]
