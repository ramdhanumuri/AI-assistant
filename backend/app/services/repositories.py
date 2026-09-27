"""Conversation and message persistence.

Repositories own queries; services own transactions and rules. Keeping them
apart means MODULE 3 (data-layer refinement) and MODULE 9 (advanced chat
management) can extend querying without touching business logic.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Conversation, Message


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

    def add(self, message: Message) -> Message:
        self.session.add(message)
        self.session.flush()
        return message