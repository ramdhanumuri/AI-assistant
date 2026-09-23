"""Conversation and message schemas.

Shaped to match `src/types/index.ts` exactly: the UI reads `message.mode`,
`message.createdAt` (epoch ms) and `conversation.updatedAt` (epoch ms), and
renders `project` as an id string. Requests accept `modeId` as an alias so
either spelling works.

Note the deliberate asymmetry: reads echo the frontend's field names, while
writes accept a wider set. Only the client is frozen in Module 2; the database
and service layers keep clearer internal names.
"""

from pydantic import AliasChoices, Field, field_validator

from app.schemas.blocks import ContentBlock, ToolTraceSchema
from app.schemas.common import APIModel, EpochMillis, OptionalEpochMillis, ORMModel

MODE_IDS = frozenset(
    {"general", "research", "coding", "creative", "analysis", "vision", "voice"}
)

# Both spellings are accepted on the way in; `modeId` is what this API
# originally published, `mode` is what the frontend types use.
_MODE_ALIAS = AliasChoices("modeId", "mode")


class ConversationRead(ORMModel):
    id: str
    title: str
    preview: str
    mode: str = Field(validation_alias=AliasChoices("mode_id", "mode"))
    project: str | None = Field(
        default=None, validation_alias=AliasChoices("project_id", "project")
    )
    pinned: bool
    archived: bool
    message_count: int
    # Epoch millis: `Sidebar`/`LandingHero` pass this straight to
    # `formatRelative`, which does arithmetic on a number.
    updated_at: EpochMillis
    last_message_at: OptionalEpochMillis = Field(
        default=None, description="Epoch milliseconds, null until the first turn."
    )


class ConversationCreate(APIModel):
    title: str = Field(default="New conversation", min_length=1, max_length=255)
    mode: str = Field(default="general", validation_alias=_MODE_ALIAS)
    project: str | None = Field(default=None, validation_alias=AliasChoices("projectId", "project"))

    @field_validator("mode")
    @classmethod
    def _known_mode(cls, value: str) -> str:
        if value not in MODE_IDS:
            raise ValueError(f"unknown mode '{value}'")
        return value


class ConversationUpdate(APIModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    pinned: bool | None = None
    archived: bool | None = None
    project: str | None = Field(default=None, validation_alias=AliasChoices("projectId", "project"))
    mode: str | None = Field(default=None, validation_alias=_MODE_ALIAS)

    @field_validator("mode")
    @classmethod
    def _known_mode(cls, value: str | None) -> str | None:
        if value is not None and value not in MODE_IDS:
            raise ValueError(f"unknown mode '{value}'")
        return value


class MessageRead(ORMModel):
    id: str
    conversation_id: str
    position: int
    role: str
    mode: str = Field(validation_alias=AliasChoices("mode_id", "mode"))
    blocks: list[ContentBlock]
    reasoning: str | None = None
    traces: list[ToolTraceSchema] | None = None
    voice: bool
    tokens: int | None = None
    created_at: EpochMillis


class MessageCreate(APIModel):
    """A user turn. Assistant turns are produced by the engine, not posted."""

    body: str = Field(min_length=1, max_length=20_000)
    mode: str | None = Field(default=None, validation_alias=_MODE_ALIAS)
    voice: bool = False

    @field_validator("mode")
    @classmethod
    def _known_mode(cls, value: str | None) -> str | None:
        if value is not None and value not in MODE_IDS:
            raise ValueError(f"unknown mode '{value}'")
        return value


class TurnResult(APIModel):
    """Both halves of one exchange, in display order."""

    user_message: MessageRead
    assistant_message: MessageRead
    conversation: ConversationRead