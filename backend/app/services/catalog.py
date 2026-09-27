"""Catalog services: modes, projects, knowledge, tools, memory.

Thin read/update services over the reference data the UI renders. They exist
so routes never touch the ORM directly, and so MODULE 10's admin surface can
reuse the same rules.
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.db.base import utcnow
from app.models import (
    AIMode,
    ActivityEvent,
    Conversation,
    DailyUsage,
    KnowledgeSource,
    MemoryRecord,
    Project,
    ToolIntegration,
)
from app.schemas.catalog import (
    ActivityEventRead,
    ConversationStats,
    DashboardSummary,
    KnowledgeSourceRead,
    MemoryRecordCreate,
    MemoryRecordRead,
    ModeRead,
    ProjectCreate,
    ProjectRead,
    ToolIntegrationRead,
    ToolIntegrationUpdate,
    UsagePointRead,
)


class CatalogService:
    def __init__(self, session: Session) -> None:
        self.session = session

    # ── Modes ────────────────────────────────────────────────────────

    def list_modes(self) -> list[AIMode]:
        return list(
            self.session.scalars(select(AIMode).order_by(AIMode.sort_order, AIMode.id))
        )

    def get_mode_or_404(self, mode_id: str) -> AIMode:
        mode = self.session.get(AIMode, mode_id)
        if mode is None:
            raise NotFoundError(f"Mode '{mode_id}' not found.")
        return mode

    # ── Projects ─────────────────────────────────────────────────────

    def list_projects(self, *, owner_id: str) -> list[ProjectRead]:
        # Scoped to the caller: a global count would tell one user how many
        # threads another user has attached to a workstream.
        thread_counts = dict(
            self.session.execute(
                select(Conversation.project_id, func.count(Conversation.id))
                .where(
                    Conversation.project_id.is_not(None),
                    Conversation.owner_id == owner_id,
                )
                .group_by(Conversation.project_id)
            ).all()
        )
        projects = self.session.scalars(
            select(Project).order_by(Project.sort_order, Project.name)
        )
        return [
            ProjectRead.model_validate(
                {
                    "id": p.id,
                    "name": p.name,
                    "brief": p.brief,
                    "progress": p.progress,
                    "accent": p.accent,
                    "threads": int(thread_counts.get(p.id, 0)),
                }
            )
            for p in projects
        ]

    def create_project(self, payload: ProjectCreate) -> Project:
        project = Project(
            id=payload.id,
            name=payload.name,
            brief=payload.brief,
            progress=payload.progress,
            accent=payload.accent,
        )
        self.session.add(project)
        self.session.commit()
        return project

    # ── Knowledge ────────────────────────────────────────────────────

    def list_knowledge(self, *, kind: str | None = None, status: str | None = None) -> list[KnowledgeSource]:
        query = select(KnowledgeSource)
        if kind:
            query = query.where(KnowledgeSource.kind == kind)
        if status:
            query = query.where(KnowledgeSource.status == status)
        query = query.order_by(KnowledgeSource.sort_order, KnowledgeSource.name)
        return list(self.session.scalars(query))

    # ── Tools ────────────────────────────────────────────────────────

    def list_tools(self, *, connected: bool | None = None) -> list[ToolIntegration]:
        query = select(ToolIntegration)
        if connected is not None:
            query = query.where(ToolIntegration.connected.is_(connected))
        query = query.order_by(ToolIntegration.sort_order, ToolIntegration.name)
        return list(self.session.scalars(query))

    def update_tool(self, tool_id: str, payload: ToolIntegrationUpdate) -> ToolIntegration:
        tool = self.session.get(ToolIntegration, tool_id)
        if tool is None:
            raise NotFoundError(f"Tool '{tool_id}' not found.")
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(tool, field, value)
        self.session.commit()
        return tool

    # ── Memory ───────────────────────────────────────────────────────

    def list_memory(self, *, owner_id: str, scope: str | None = None) -> list[MemoryRecord]:
        query = select(MemoryRecord).where(MemoryRecord.owner_id == owner_id)
        if scope:
            query = query.where(MemoryRecord.scope == scope)
        query = query.order_by(MemoryRecord.confidence.desc(), MemoryRecord.id)
        return list(self.session.scalars(query))

    def create_memory(self, payload: MemoryRecordCreate, *, owner_id: str) -> MemoryRecord:
        record = MemoryRecord(
            id=f"mem-{uuid4().hex[:12]}",
            statement=payload.statement,
            scope=payload.scope,
            confidence=payload.confidence,
            learned_at=utcnow(),
            owner_id=owner_id,
        )
        self.session.add(record)
        self.session.commit()
        return record

    def delete_memory(self, memory_id: str, *, owner_id: str) -> None:
        record = self.session.get(MemoryRecord, memory_id)
        if record is None or record.owner_id != owner_id:
            # Someone else's record is reported as missing, not as forbidden.
            raise NotFoundError(f"Memory record '{memory_id}' not found.")
        self.session.delete(record)
        self.session.commit()

    # ── Dashboard ────────────────────────────────────────────────────

    def summary(self, *, owner_id: str) -> DashboardSummary:
        """Aggregates over the caller's own conversations only.

        Every count here is owner-scoped. The reference data (modes, knowledge,
        tools, usage series) is shared and non-sensitive, so it stays global.
        """
        total_conversations = int(
            self.session.scalar(
                select(func.count())
                .select_from(Conversation)
                .where(
                    Conversation.archived.is_(False),
                    Conversation.owner_id == owner_id,
                )
            )
            or 0
        )
        total_messages = int(
            self.session.scalar(
                select(func.coalesce(func.sum(Conversation.message_count), 0)).where(
                    Conversation.owner_id == owner_id
                )
            )
            or 0
        )
        active_modes = int(
            self.session.scalar(
                select(func.count(func.distinct(Conversation.mode_id))).where(
                    Conversation.archived.is_(False),
                    Conversation.owner_id == owner_id,
                )
            )
            or 0
        )
        pinned = int(
            self.session.scalar(
                select(func.count())
                .select_from(Conversation)
                .where(
                    Conversation.pinned.is_(True),
                    Conversation.owner_id == owner_id,
                )
            )
            or 0
        )

        usage = self.session.scalars(select(DailyUsage).order_by(DailyUsage.day))
        activity = self.session.scalars(
            select(ActivityEvent).order_by(ActivityEvent.occurred_at.desc()).limit(10)
        )

        return DashboardSummary(
            stats=ConversationStats(
                total_conversations=total_conversations,
                total_messages=total_messages,
                active_modes=active_modes,
                pinned=pinned,
            ),
            usage=[UsagePointRead.model_validate(u) for u in usage],
            activity=[ActivityEventRead.model_validate(a) for a in activity],
            knowledge=[KnowledgeSourceRead.model_validate(k) for k in self.list_knowledge()],
            tools=[ToolIntegrationRead.model_validate(t) for t in self.list_tools()],
        )

    # ── Re-exported read models for routes ───────────────────────────

    @staticmethod
    def mode_read(mode: AIMode) -> ModeRead:
        return ModeRead.model_validate(mode)

    @staticmethod
    def memory_read(record: MemoryRecord) -> MemoryRecordRead:
        return MemoryRecordRead.model_validate(record)