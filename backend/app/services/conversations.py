"""Conversation orchestration.

Owns the write path for a chat turn: persist the user message, ask the model
for a response, persist that too, and keep the conversation's denormalised
counters in step. Routes stay thin and the model layer stays free of
persistence concerns.

MODULE 4 makes every method owner-scoped. `owner_id` is a required keyword on
each entry point and is pushed down into the query, so "not yours" and "does
not exist" are the same 404 — a caller cannot probe for another account's
thread ids by watching for 403s.

STEP 6 adds two write paths over the same tables:

* `post_message` — the original synchronous turn. It keeps working unchanged
  (and keeps the deterministic simulator as the default provider), so nothing
  built on it regresses.
* `stream_message` — the real AI path. It persists the user message and an
  assistant placeholder, streams the provider's output, then finalises the
  assistant row with its terminal status. A failure or a client disconnect is
  recorded as `failed`/`cancelled` with the partial text preserved, never as a
  successful empty answer.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai.errors import AIError
from app.ai.orchestrator import AIOrchestrator
from app.ai.types import ChatMessage
from app.core.config import settings
from app.core.errors import ConflictError, NotFoundError, ServiceUnavailableError
from app.core.logging import get_logger
from app.db.base import utcnow
from app.models import AIUsageEvent, Conversation, Message
from app.schemas.blocks import TextBlock
from app.schemas.conversation import ConversationCreate, ConversationUpdate, MessageCreate
from app.services.engine import Engine, EngineError, EngineRequest, get_engine
from app.services.repositories import (
    AIUsageRepository,
    ConversationRepository,
    MessageRepository,
)

logger = get_logger(__name__)

PREVIEW_LENGTH = 180

# Terminal statuses a generated turn can end in. Mirrors the vocabulary in
# `app.ai.types.GenerationStatus`.
STATUS_STREAMING = "streaming"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"


def _new_id(prefix: str) -> str:
    from uuid import uuid4

    return f"{prefix}-{uuid4().hex[:12]}"


def _not_found(conversation_id: str) -> NotFoundError:
    return NotFoundError(f"Conversation '{conversation_id}' not found.")


def message_text(message: Message) -> str:
    """Flatten a stored message's text blocks into plain text.

    The provider only ever sees plain text, so the rich block vocabulary never
    leaks into a prompt and a code/table block contributes its textual content.
    """
    parts: list[str] = []
    for block in message.blocks or []:
        body = block.get("body") if isinstance(block, dict) else None
        if isinstance(body, str) and body:
            parts.append(body)
    return "\n\n".join(parts)


class ConversationService:
    def __init__(self, session: Session, engine: Engine | None = None) -> None:
        self.session = session
        self.conversations = ConversationRepository(session)
        self.messages = MessageRepository(session)
        self.usage = AIUsageRepository(session)
        self.engine = engine or get_engine()

    # ── Reads ────────────────────────────────────────────────────────

    def get_or_404(self, conversation_id: str, *, owner_id: str) -> Conversation:
        conversation = self.conversations.get(conversation_id, owner_id=owner_id)
        if conversation is None:
            raise _not_found(conversation_id)
        return conversation

    def list_conversations(
        self, *, owner_id: str, **filters: object
    ) -> tuple[list[Conversation], int]:
        return self.conversations.list(owner_id=owner_id, **filters)  # type: ignore[arg-type]

    def list_messages(
        self, conversation_id: str, *, owner_id: str, limit: int, offset: int
    ) -> tuple[list[Message], int]:
        self.get_or_404(conversation_id, owner_id=owner_id)
        return self.messages.list_for_conversation(
            conversation_id, limit=limit, offset=offset
        )

    # ── Writes ───────────────────────────────────────────────────────

    def create(self, payload: ConversationCreate, *, owner_id: str) -> Conversation:
        conversation = Conversation(
            id=_new_id("conv"),
            title=payload.title,
            preview="",
            mode_id=payload.mode,
            project_id=payload.project,
            owner_id=owner_id,
            pinned=False,
            archived=False,
            message_count=0,
            last_message_at=None,
        )
        self.conversations.add(conversation)
        self._commit()
        return conversation

    def update(
        self, conversation_id: str, payload: ConversationUpdate, *, owner_id: str
    ) -> Conversation:
        conversation = self.get_or_404(conversation_id, owner_id=owner_id)
        # Schema fields are named for the wire (`mode`, `project`); the ORM
        # columns keep their `_id` suffix, so the two are mapped explicitly
        # rather than relying on a name match.
        column_for = {"mode": "mode_id", "project": "project_id"}
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(conversation, column_for.get(field, field), value)
        self._commit()
        return conversation

    def delete(self, conversation_id: str, *, owner_id: str) -> None:
        conversation = self.get_or_404(conversation_id, owner_id=owner_id)
        self.conversations.delete(conversation)
        self._commit()

    def post_message(
        self, conversation_id: str, payload: MessageCreate, *, owner_id: str
    ) -> tuple[Message, Message, Conversation]:
        """Append a user turn and the engine's reply as one atomic exchange."""
        conversation = self.get_or_404(conversation_id, owner_id=owner_id)

        # A retried request carrying the same idempotency key returns the turn
        # that was already produced instead of generating a second answer.
        if payload.idempotency_key:
            existing = self.messages.find_by_idempotency_key(
                conversation.id, payload.idempotency_key
            )
            if existing is not None:
                user = self._user_message_for(conversation.id, existing)
                if user is not None:
                    return user, existing, conversation

        history = self.messages.recent_user_prompts(conversation.id)
        mode_id = payload.mode or conversation.mode_id

        user_message = Message(
            id=_new_id("msg"),
            conversation_id=conversation.id,
            position=self.conversations.next_position(conversation.id),
            role="user",
            mode_id=mode_id,
            blocks=[TextBlock(body=payload.body).model_dump(by_alias=True, exclude_none=True)],
            reasoning=None,
            traces=None,
            voice=payload.voice,
            tokens=None,
            status=STATUS_COMPLETED,
        )
        self.messages.add(user_message)

        # The engine is an external dependency (a real provider in STEP 6).
        # A provider failure must not surface as a 500 with the user's turn half
        # written: roll back the user message and answer with a safe 503, so a
        # timeout upstream does not leave an orphaned turn in the transcript.
        try:
            turn = self.engine.generate(
                EngineRequest(
                    prompt=payload.body,
                    mode_id=mode_id,
                    voice=payload.voice,
                    conversation_id=conversation.id,
                    history=history,
                )
            )
        except EngineError as exc:
            self.session.rollback()
            logger.warning("Engine failed to produce a turn: %s", exc)
            raise ServiceUnavailableError(
                "The assistant is temporarily unavailable. Please try again.",
                code="engine_unavailable",
            ) from exc

        assistant_message = Message(
            id=_new_id("msg"),
            conversation_id=conversation.id,
            position=user_message.position + 1,
            role="assistant",
            mode_id=turn.mode_id,
            blocks=[block.model_dump(by_alias=True, exclude_none=True) for block in turn.blocks],
            reasoning=turn.reasoning,
            traces=[trace.model_dump(by_alias=True, exclude_none=True) for trace in turn.traces],
            voice=payload.voice,
            tokens=turn.tokens,
            status=STATUS_COMPLETED,
            provider=self.engine.name,
            model=self._model_label(),
            total_tokens=turn.tokens or None,
            idempotency_key=payload.idempotency_key,
        )
        self.messages.add(assistant_message)

        self._touch_conversation(conversation, turn.blocks, payload.body)
        self._commit()
        self.session.refresh(conversation)
        return user_message, assistant_message, conversation

    # ── Streaming (STEP 6) ───────────────────────────────────────────

    async def stream_message(
        self, conversation_id: str, payload: MessageCreate, *, owner_id: str
    ) -> AsyncIterator[dict[str, Any]]:
        """Generate a turn incrementally, persisting as it goes.

        Yields provider-independent frames (`meta`, `delta`, `done`, `error`)
        which the route serialises as Server-Sent Events. The method owns the
        full lifecycle so persistence cannot be skipped by a caller:

        1. verify ownership and replay an existing turn for a repeated
           idempotency key,
        2. persist the user message and a `streaming` assistant placeholder,
        3. stream provider output, forwarding deltas,
        4. finalise the assistant row as completed/failed/cancelled.

        A client disconnect (the generator being closed) is caught and recorded
        as `cancelled` with the partial text, so the transcript never shows an
        empty successful answer.
        """
        conversation = self.get_or_404(conversation_id, owner_id=owner_id)
        mode_id = payload.mode or conversation.mode_id

        if payload.idempotency_key:
            existing = self.messages.find_by_idempotency_key(
                conversation.id, payload.idempotency_key
            )
            if existing is not None:
                user = self._user_message_for(conversation.id, existing)
                if user is not None:
                    yield {"event": "meta", "replayed": True, "user_message": user,
                           "assistant_message": existing, "conversation": conversation,
                           "model": existing.model or self._model_label(),
                           "provider": existing.provider or self.engine.name}
                    yield {"event": "done", "assistant_message": existing,
                           "conversation": conversation}
                    return

        # Context is loaded *before* the current message is persisted, so the
        # current turn is never replayed to the model as history.
        history = self._load_history(conversation.id)

        user_message = Message(
            id=_new_id("msg"),
            conversation_id=conversation.id,
            position=self.conversations.next_position(conversation.id),
            role="user",
            mode_id=mode_id,
            blocks=[TextBlock(body=payload.body).model_dump(by_alias=True, exclude_none=True)],
            voice=payload.voice,
            status=STATUS_COMPLETED,
        )
        self.messages.add(user_message)

        assistant_message = Message(
            id=_new_id("msg"),
            conversation_id=conversation.id,
            position=user_message.position + 1,
            role="assistant",
            mode_id=mode_id,
            blocks=[],
            voice=payload.voice,
            status=STATUS_STREAMING,
            provider=self.engine.name,
            model=self._model_label(),
            idempotency_key=payload.idempotency_key,
        )
        self.messages.add(assistant_message)

        self._touch_conversation(conversation, [TextBlock(body=payload.body)], payload.body)
        # Persist the user turn and the placeholder before generation starts, so
        # an interrupted stream still leaves a coherent transcript behind.
        self._commit()

        yield {
            "event": "meta",
            "replayed": False,
            "user_message": user_message,
            "assistant_message": assistant_message,
            "conversation": conversation,
            "model": assistant_message.model,
            "provider": assistant_message.provider,
        }

        started = time.perf_counter()
        first_token_ms: int | None = None
        buffer: list[str] = []
        result = None
        error: AIError | None = None

        orchestrator = AIOrchestrator()
        try:
            async for event in orchestrator.stream(
                history=history,
                current_user_message=payload.body,
                model=payload.model,
            ):
                if event.type == "delta":
                    if first_token_ms is None:
                        first_token_ms = int((time.perf_counter() - started) * 1000)
                    buffer.append(event.text)
                    yield {"event": "delta", "text": event.text}
                elif event.type == "done":
                    result = event.result
                elif event.type == "error":
                    result = event.result
                    error = event.error
        except asyncio.CancelledError:
            # The client went away (or the server is shutting down). Persist
            # what was produced and mark it cancelled, then propagate so the
            # framework can unwind the request.
            self._finalise(
                conversation, assistant_message, "".join(buffer), STATUS_CANCELLED,
                error_code="stream_interrupted", model=None, usage=None,
                latency_ms=int((time.perf_counter() - started) * 1000),
                first_token_ms=first_token_ms, owner_id=owner_id,
            )
            raise

        text = "".join(buffer)
        if error is not None:
            status = STATUS_FAILED
            code = error.code
            message = error.message
            retryable = error.retryable
        else:
            status = STATUS_COMPLETED
            code = None
            message = ""
            retryable = False

        self._finalise(
            conversation, assistant_message, text, status,
            error_code=code, model=(result.model if result else None),
            usage=(result.usage if result else None),
            latency_ms=(result.latency_ms if result else None),
            first_token_ms=first_token_ms, owner_id=owner_id,
        )

        if status == STATUS_COMPLETED:
            yield {"event": "done", "assistant_message": assistant_message,
                   "conversation": conversation}
        else:
            yield {"event": "error", "code": code, "message": message,
                   "retryable": retryable, "assistant_message": assistant_message}

    # ── Internals ────────────────────────────────────────────────────

    def _load_history(self, conversation_id: str) -> list[ChatMessage]:
        """Recent completed turns, oldest-first, as provider-ready messages."""
        turns = self.messages.recent_turns(
            conversation_id, limit=settings.AI_MAX_CONTEXT_MESSAGES
        )
        history: list[ChatMessage] = []
        for turn in turns:
            text = message_text(turn)
            if not text:
                continue
            role = "assistant" if turn.role == "assistant" else "user"
            history.append(ChatMessage(role=role, content=text))
        return history

    def _model_label(self) -> str | None:
        """The model name to record, or `None` for the offline simulator."""
        if self.engine.name in {"simulator", "local"}:
            return None
        return settings.ai_model_resolved or None

    def _finalise(
        self,
        conversation: Conversation,
        assistant_message: Message,
        text: str,
        status: str,
        *,
        error_code: str | None,
        model: str | None,
        usage: Any,
        latency_ms: int | None,
        first_token_ms: int | None,
        owner_id: str,
    ) -> None:
        """Write the terminal state of a streamed turn and its usage row."""
        assistant_message.status = status
        assistant_message.error_code = error_code
        assistant_message.latency_ms = latency_ms
        if model:
            assistant_message.model = model
        if text:
            assistant_message.blocks = [
                TextBlock(body=text).model_dump(by_alias=True, exclude_none=True)
            ]
        if usage is not None:
            assistant_message.input_tokens = usage.input_tokens
            assistant_message.output_tokens = usage.output_tokens
            assistant_message.total_tokens = usage.total_tokens
            assistant_message.tokens = usage.total_tokens
        elif text:
            # No provider token report: leave the counts NULL rather than
            # inventing them. `tokens` stays NULL for the same reason.
            pass

        self._record_usage(
            conversation, assistant_message, status, error_code,
            usage, latency_ms, first_token_ms, owner_id,
        )
        # A failed turn with no text should not become the conversation preview.
        if text:
            conversation.preview = text[:PREVIEW_LENGTH]
        conversation.message_count = self.conversations.count_messages(conversation.id)
        conversation.last_message_at = utcnow()
        self._commit()

    def _record_usage(
        self,
        conversation: Conversation,
        assistant_message: Message,
        status: str,
        error_code: str | None,
        usage: Any,
        latency_ms: int | None,
        first_token_ms: int | None,
        owner_id: str,
    ) -> None:
        """Append one usage row. Never stores content, keys or credentials."""
        from app.ai.usage import cost_currency, estimate_cost, pricing_version
        from app.ai.types import TokenUsage

        tokens = usage if usage is not None else TokenUsage()
        cost = estimate_cost(tokens)
        self.usage.add(
            AIUsageEvent(
                user_id=owner_id,
                conversation_id=conversation.id,
                message_id=assistant_message.id,
                provider=assistant_message.provider or self.engine.name,
                model=assistant_message.model or "simulator",
                status=status,
                error_code=error_code,
                input_tokens=tokens.input_tokens,
                output_tokens=tokens.output_tokens,
                total_tokens=tokens.total_tokens,
                latency_ms=latency_ms,
                time_to_first_token_ms=first_token_ms,
                estimated_cost=cost,
                currency=cost_currency() if cost is not None else None,
                pricing_version=pricing_version() if cost is not None else None,
                request_started_at=utcnow(),
                request_completed_at=utcnow(),
            )
        )

    def _user_message_for(
        self, conversation_id: str, assistant_message: Message
    ) -> Message | None:
        """The user turn immediately preceding an assistant message."""
        rows = self.session.query(Message).filter(
            Message.conversation_id == conversation_id,
            Message.position == assistant_message.position - 1,
            Message.role == "user",
        ).all()
        return rows[0] if rows else None

    def _touch_conversation(
        self, conversation: Conversation, blocks: list[Any], prompt: str
    ) -> None:
        conversation.message_count = self.conversations.count_messages(conversation.id)
        conversation.preview = _preview(blocks)
        conversation.last_message_at = utcnow()
        if conversation.title == "New conversation":
            conversation.title = _derive_title(prompt)

    def _commit(self) -> None:
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            logger.warning("Integrity error on commit: %s", exc)
            raise ConflictError("The request conflicts with existing data.") from exc


def _preview(blocks: list[object]) -> str:
    for block in blocks:
        body = getattr(block, "body", None)
        if isinstance(body, str) and body:
            return body[:PREVIEW_LENGTH]
    return ""


def _derive_title(prompt: str) -> str:
    cleaned = " ".join(prompt.split())
    if len(cleaned) <= 60:
        return cleaned or "New conversation"
    return cleaned[:57].rstrip() + "…"