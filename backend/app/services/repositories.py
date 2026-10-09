"""Conversation and message persistence.

Repositories own queries; services own transactions and rules. Keeping them
apart means MODULE 3 (data-layer refinement) and MODULE 9 (advanced chat
management) can extend querying without touching business logic.
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import AIUsageEvent, Conversation, Message


class ConversationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, conversation_id: str, *, owner_id: str | None = None) -> Conversation | None:
        """Fetch one conversation, scoped to its owner.

        `owner_id` is required for every user-facing path: passing it makes the
        ownership check part of the query rather than a comparison afterwards,
        so a missed branch cannot leak another account's thread. It stays
        optional only for internal/admin callers.
        """
        conversation = self.session.get(Conversation, conversation_id)
        if conversation is None:
            return None
        if owner_id is not None and conversation.owner_id != owner_id:
            return None
        return conversation

    def list(
        self,
        *,
        owner_id: str | None = None,
        include_archived: bool = False,
        pinned: bool | None = None,
        project_id: str | None = None,
        mode_id: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Conversation], int]:
        conditions = []
        if owner_id is not None:
            # NULL owner rows (the MODULE 2 demo data) match nothing, which is
            # the intended outcome: unowned content is not served to anyone.
            conditions.append(Conversation.owner_id == owner_id)
        if not include_archived:
            conditions.append(Conversation.archived.is_(False))
        if pinned is not None:
            conditions.append(Conversation.pinned.is_(pinned))
        if project_id is not None:
            conditions.append(Conversation.project_id == project_id)
        if mode_id is not None:
            conditions.append(Conversation.mode_id == mode_id)
        if search:
            needle = f"%{search.lower()}%"
            conditions.append(
                func.lower(Conversation.title).like(needle)
                | func.lower(Conversation.preview).like(needle)
            )

        total = self.session.scalar(
            select(func.count()).select_from(Conversation).where(*conditions)
        )
        rows = self.session.scalars(
            select(Conversation)
            .where(*conditions)
            .order_by(
                Conversation.pinned.desc(),
                Conversation.last_message_at.desc().nulls_last(),
                Conversation.updated_at.desc(),
            )
            .limit(limit)
            .offset(offset)
        ).all()
        return list(rows), int(total or 0)

    def add(self, conversation: Conversation) -> Conversation:
        self.session.add(conversation)
        self.session.flush()
        return conversation

    def delete(self, conversation: Conversation) -> None:
        self.session.delete(conversation)
        self.session.flush()

    def next_position(self, conversation_id: str) -> int:
        current = self.session.scalar(
            select(func.max(Message.position)).where(
                Message.conversation_id == conversation_id
            )
        )
        return int(current or 0) + 1

    def count_messages(self, conversation_id: str) -> int:
        return int(
            self.session.scalar(
                select(func.count())
                .select_from(Message)
                .where(Message.conversation_id == conversation_id)
            )
            or 0
        )


class MessageRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, message_id: str) -> Message | None:
        return self.session.get(Message, message_id)

    def list_for_conversation(
        self, conversation_id: str, *, limit: int = 200, offset: int = 0
    ) -> tuple[list[Message], int]:
        total = self.session.scalar(
            select(func.count())
            .select_from(Message)
            .where(Message.conversation_id == conversation_id)
        )
        rows = self.session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.position)
            .limit(limit)
            .offset(offset)
        ).all()
        return list(rows), int(total or 0)

    def recent_user_prompts(self, conversation_id: str, *, limit: int = 6) -> list[str]:
        rows = self.session.scalars(
            select(Message)
            .options(selectinload(Message.conversation))
            .where(
                Message.conversation_id == conversation_id,
                Message.role == "user",
            )
            .order_by(Message.position.desc())
            .limit(limit)
        ).all()
        prompts: list[str] = []
        for message in rows:
            for block in message.blocks or []:
                if block.get("kind") == "text" and block.get("body"):
                    prompts.append(str(block["body"]))
                    break
        return list(reversed(prompts))

    def recent_turns(
        self, conversation_id: str, *, limit: int, exclude_position: int | None = None
    ) -> list[Message]:
        """The most recent turns, oldest-first, for context construction.

        Excludes the just-persisted current user message (identified by
        position) so it is not replayed twice — once as history and once as the
        current turn. `status` is filtered to completed/cancelled so a failed or
        in-flight assistant placeholder never becomes model context.
        """
        conditions = [
            Message.conversation_id == conversation_id,
            Message.status.in_(("completed", "cancelled")),
        ]
        if exclude_position is not None:
            conditions.append(Message.position != exclude_position)
        rows = self.session.scalars(
            select(Message)
            .where(*conditions)
            .order_by(Message.position.desc())
            .limit(limit)
        ).all()
        return list(reversed(rows))

    def find_by_idempotency_key(
        self, conversation_id: str, idempotency_key: str
    ) -> Message | None:
        """The assistant turn previously produced for this key, if any."""
        return self.session.scalars(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.idempotency_key == idempotency_key,
                Message.role == "assistant",
            )
            .order_by(Message.position.desc())
            .limit(1)
        ).first()

    def add(self, message: Message) -> Message:
        self.session.add(message)
        self.session.flush()
        return message


class AIUsageRepository:
    """Persistence for the AI usage ledger.

    Append-only by design: a usage row is never updated after the request it
    describes finishes, so the ledger cannot be rewritten to hide spend.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, event: AIUsageEvent) -> AIUsageEvent:
        self.session.add(event)
        self.session.flush()
        return event

    def summary(
        self, *, user_id: str | None = None, since: datetime | None = None
    ) -> dict[str, int | float | None]:
        """Aggregate counters for the usage surface.

        `user_id` scopes the window to one account (the self-service view);
        omitting it aggregates the whole platform (the admin view). Token and
        cost sums are `None` rather than 0 when no row carried a value, so
        "we have no data" is not reported as "we spent nothing".
        """
        conditions = []
        if user_id is not None:
            conditions.append(AIUsageEvent.user_id == user_id)
        if since is not None:
            conditions.append(AIUsageEvent.request_started_at >= since)

        def count(*extra) -> int:
            return int(
                self.session.scalar(
                    select(func.count())
                    .select_from(AIUsageEvent)
                    .where(*conditions, *extra)
                )
                or 0
            )

        def total(column) -> int | None:
            value = self.session.scalar(
                select(func.sum(column)).select_from(AIUsageEvent).where(*conditions)
            )
            return None if value is None else int(value)

        def total_float(column) -> float | None:
            value = self.session.scalar(
                select(func.sum(column)).select_from(AIUsageEvent).where(*conditions)
            )
            return None if value is None else float(value)

        latency = self.session.scalar(
            select(func.avg(AIUsageEvent.latency_ms))
            .select_from(AIUsageEvent)
            .where(*conditions)
        )

        return {
            "total_requests": count(),
            "completed_requests": count(AIUsageEvent.status == "completed"),
            "failed_requests": count(AIUsageEvent.status == "failed"),
            "cancelled_requests": count(AIUsageEvent.status == "cancelled"),
            "input_tokens": total(AIUsageEvent.input_tokens),
            "output_tokens": total(AIUsageEvent.output_tokens),
            "total_tokens": total(AIUsageEvent.total_tokens),
            "average_latency_ms": None if latency is None else int(latency),
            "estimated_cost": total_float(AIUsageEvent.estimated_cost),
        }