"""Provider-independent value types.

These are the only shapes that cross the provider boundary, so a provider
adapter never sees a SQLAlchemy model, a FastAPI request or a Pydantic schema.
Keeping the vocabulary small is what makes a second provider a new file rather
than a rewrite: nothing outside this module encodes a vendor's wire format.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Role = Literal["system", "user", "assistant"]

# Terminal state of one generation. Mirrors `Message.status` so persistence can
# store the enum verbatim rather than translating between vocabularies.
GenerationStatus = Literal["streaming", "completed", "failed", "cancelled"]


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """One turn as the model sees it: a role and plain text.

    `content` is a single string rather than a block list on purpose. The rich
    block vocabulary is a rendering concern; flattening it here means the
    provider prompt stays provider-independent and no vendor learns about our
    UI. Unicode (including Telugu) survives because the value is never
    re-encoded on this path.
    """

    role: Role
    content: str


@dataclass(slots=True)
class GenerationRequest:
    """A fully-constructed prompt plus the resolved generation parameters.

    Built by the orchestrator, never by a route, so the system prompt and the
    budgets are decided in one place and a client cannot inject either.
    """

    messages: list[ChatMessage]
    model: str
    temperature: float
    top_p: float
    max_output_tokens: int
    stream: bool = True
    # Correlates the provider call with the request log line without carrying
    # any message content.
    request_id: str | None = None


@dataclass(slots=True)
class TokenUsage:
    """Token accounting, when the provider reports it.

    Every field is optional: a provider that does not expose usage must yield
    `None`, which is stored as NULL. Inventing a count would corrupt the cost
    foundation the numbers feed.
    """

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None

    def normalised(self) -> "TokenUsage":
        """Fill in `total_tokens` when only the halves are known."""
        if self.total_tokens is None and (
            self.input_tokens is not None or self.output_tokens is not None
        ):
            total = (self.input_tokens or 0) + (self.output_tokens or 0)
            return TokenUsage(self.input_tokens, self.output_tokens, total)
        return self


@dataclass(slots=True)
class StreamChunk:
    """One increment of a streamed response.

    `text` is the delta, not the accumulated text: the client appends, and a
    dropped chunk therefore corrupts only its own span instead of silently
    rewriting everything already rendered.
    """

    text: str = ""
    # Set on the final chunk only, when the provider reports it.
    usage: TokenUsage | None = None
    finish_reason: str | None = None


@dataclass(slots=True)
class GenerationResult:
    """A complete (non-streamed) generation, or the rolled-up stream result."""

    text: str
    model: str
    usage: TokenUsage = field(default_factory=TokenUsage)
    finish_reason: str | None = None


__all__ = [
    "ChatMessage",
    "GenerationRequest",
    "GenerationResult",
    "GenerationStatus",
    "Role",
    "StreamChunk",
    "TokenUsage",
]
