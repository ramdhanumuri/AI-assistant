"""Mode, project, knowledge, tool and memory schemas.

Field names and shapes mirror `src/types/index.ts`, because that file is the
frozen frontend contract: the UI reads `project.threads`, `tool.calls`,
`knowledge.items`/`updated`, `memory.learned` and `activity.at`. A validation
alias bridges each wire name to the ORM column it comes from, so the database
keeps descriptive names without the client needing a translation layer.
"""

from pydantic import AliasChoices, Field

from app.schemas.common import APIModel, ORMModel, OptionalRelativeLabel, RelativeLabel


class ModeRead(ORMModel):
    id: str
    label: str
    caption: str
    description: str
    aura: str
    glyph: str


class ProjectRead(ORMModel):
    id: str
    name: str
    brief: str
    progress: float
    accent: str
    # `threads` in the UI; computed from the conversations table.
    threads: int = Field(default=0, description="Conversations attached to this project.")


class ProjectCreate(APIModel):
    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    brief: str = ""
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    accent: str = "110 168 255"


class KnowledgeSourceRead(ORMModel):
    id: str
    name: str
    kind: str
    status: str
    items: int = Field(validation_alias=AliasChoices("item_count", "items"))
    updated: OptionalRelativeLabel = Field(
        default=None,
        description="Pre-formatted relative sync time; the UI prints it verbatim.",
        validation_alias=AliasChoices("last_synced_at", "updated"),
    )


class ToolIntegrationRead(ORMModel):
    id: str
    name: str
    category: str
    connected: bool
    permission: str
    calls: int = Field(validation_alias=AliasChoices("call_count", "calls"))


class ToolIntegrationUpdate(APIModel):
    connected: bool | None = None
    permission: str | None = Field(default=None, max_length=64)


class MemoryRecordRead(ORMModel):
    id: str
    statement: str
    scope: str
    confidence: float
    learned: RelativeLabel = Field(
        description="Pre-formatted relative time; the UI prints it verbatim.",
        validation_alias=AliasChoices("learned_at", "learned"),
    )


class MemoryRecordCreate(APIModel):
    statement: str = Field(min_length=1)
    scope: str = Field(default="General", max_length=64)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class ActivityEventRead(ORMModel):
    id: int
    label: str
    mode: str = Field(validation_alias=AliasChoices("mode_id", "mode"))
    at: RelativeLabel = Field(
        description="Pre-formatted relative time; the UI prints it verbatim.",
        validation_alias=AliasChoices("occurred_at", "at"),
    )


class UsagePointRead(ORMModel):
    label: str
    value: int
    secondary: int


class ConversationStats(APIModel):
    total_conversations: int
    total_messages: int
    active_modes: int
    pinned: int


class DashboardSummary(APIModel):
    stats: ConversationStats
    usage: list[UsagePointRead]
    activity: list[ActivityEventRead]
    knowledge: list[KnowledgeSourceRead]
    tools: list[ToolIntegrationRead]