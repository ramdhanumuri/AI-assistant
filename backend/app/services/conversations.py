"""Conversation orchestration.

Owns the write path for a chat turn: persist the user message, ask the engine
for a response, persist that too, and keep the conversation's denormalised
counters in step — all inside one transaction. Routes stay thin and the engine
stays free of persistence concerns.

MODULE 4 makes every method owner-scoped. `owner_id` is a required keyword on
each entry point and is pushed down into the query, so "not yours" and "does
not exist" are the same 404 — a caller cannot probe for another account's
thread ids by watching for 403s.
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ServiceUnavailableError
from app.core.logging import get_logger
from app.db.base import utcnow
from app.models import Conversation, Message
from app.schemas.blocks import TextBlock
from app.schemas.conversation import ConversationCreate, ConversationUpdate, MessageCreate
from app.services.engine import Engine, EngineError, EngineRequest, get_engine
from app.services.repositories import ConversationRepository, MessageRepository

logger = get_logger(__name__)

PREVIEW_LENGTH = 180


def _new_id(prefix: str) -> str:
    from uuid import uuid4

    return f"{prefix}-{uuid4().hex[:12]}"


def _not_found(conversation_id: str) -> NotFoundError:
    return NotFoundError(f"Conversation '{conversation_id}' not found.")


class ConversationService:
    def __init__(self, session: Session, engine: Engine | None = None) -> None:
        self.session = session
        self.conversations = ConversationRepository(session)
        self.messages = MessageRepository(session)
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

        history = self.messages.recent_user_prompts(conversation_id)
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
        )
        self.messages.add(user_message)

        # The engine is an external dependency (a real provider in MODULE 6).
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
        )
        self.messages.add(assistant_message)

        conversation.message_count = self.conversations.count_messages(conversation.id)
        conversation.preview = _preview(turn.blocks)
        conversation.last_message_at = utcnow()
        if conversation.title == "New conversation":
            conversation.title = _derive_title(payload.body)

        self._commit()
        self.session.refresh(conversation)
        return user_message, assistant_message, conversation

    # ── Internals ────────────────────────────────────────────────────

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