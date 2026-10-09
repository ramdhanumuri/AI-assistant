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
    # ── AI provenance (STEP 6) ────────────────────────────────────────
    # `status` is what lets the UI distinguish a completed answer from one that
    # failed or was cancelled mid-stream. The token/latency fields are nullable
    # because a provider may not report them; the UI renders nothing rather
    # than a misleading zero.
    status: str = "completed"
    model: str | None = None
    provider: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    latency_ms: int | None = None
    error_code: str | None = None


class MessageCreate(APIModel):
    """A user turn. Assistant turns are produced by the engine, not posted."""

    body: str = Field(min_length=1, max_length=20_000)
    mode: str | None = Field(default=None, validation_alias=_MODE_ALIAS)
    voice: bool = False
    # Optional server-validated model selection. A value outside the allow-list
    # is rejected rather than silently replaced.
    model: str | None = Field(default=None, max_length=128)
    # Optional idempotency key so a client retry after an ambiguous network
    # failure does not generate a second, duplicate answer.
    idempotency_key: str | None = Field(
        default=None, min_length=8, max_length=80, pattern=r"^[A-Za-z0-9._:-]+$"
    )

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


# ── STEP 6 streaming (SSE) payloads ───────────────────────────────────
# These are the frames emitted on `POST /conversations/{id}/messages/stream`.
# They are provider-independent: the browser never learns which vendor answered
# beyond the model name the server chooses to report.


class StreamMeta(APIModel):
    """First frame: what the server is about to do."""

    conversation_id: str
    user_message: MessageRead
    # The persisted assistant placeholder. The UI swaps its optimistic ids for
    # these, so a later reload and the live session refer to the same rows.
    assistant_message: MessageRead
    model: str
    provider: str
    # True when this key matched an existing turn and no generation was run.
    replayed: bool = False


class StreamDelta(APIModel):
    """Incremental assistant text. `text` is a delta, never accumulated."""

    text: str


class StreamDone(APIModel):
    """Terminal success frame, carrying the persisted assistant message."""

    assistant_message: MessageRead
    conversation: ConversationRead


class StreamError(APIModel):
    """Terminal failure frame.

    `code` is from the closed AI error vocabulary; `message` is safe to render.
    The partial assistant message (if any) is included so the UI can show what
    was produced before the failure rather than discarding it.
    """

    code: str
    message: str
    retryable: bool
    assistant_message: MessageRead | None = None