"""The model-layer seam.

This is the single boundary between the API and "the model". STEP 6 keeps the
rich-turn `Engine` contract for the deterministic simulator (which produces the
block vocabulary the UI renders) and adds a streaming method so a real provider
can feed the chat UI incrementally.

Contract:
  * `generate` takes a prompt plus the active mode and returns a complete
    assistant turn (reasoning, tool traces, rich blocks, token count).
  * `stream` yields assistant text incrementally, for providers that generate
    token by token.
  * Implementations must be side-effect free with respect to the database —
    persistence is the service layer's job.

A real provider is registered as an `app.ai.AIProvider` and driven through
`app.ai.orchestrator.AIOrchestrator`; this module re-exports that registry so
`AI_PROVIDER` still resolves in one place.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from app.schemas.blocks import ContentBlock, ToolTraceSchema


@dataclass(slots=True)
class EngineTurn:
    reasoning: str
    traces: list[ToolTraceSchema]
    blocks: list[ContentBlock]
    mode_id: str
    tokens: int
    # Names the recipe that produced the turn, for observability.
    route: str = "default"
    follow_ups: list[str] = field(default_factory=list)


@dataclass(slots=True)
class EngineRequest:
    prompt: str
    mode_id: str
    voice: bool = False
    conversation_id: str | None = None
    history: list[str] = field(default_factory=list)


@runtime_checkable
class Engine(Protocol):
    """Structural contract every provider must satisfy."""

    name: str

    def generate(self, request: EngineRequest) -> EngineTurn:  # pragma: no cover
        ...


class StreamingEngine(Protocol):
    """Optional capability: incremental text generation.

    Separate from `Engine` because a deterministic rich-turn engine need not
    stream, and a token-by-token provider need not know about content blocks.
    """

    name: str

    def stream(self, request: EngineRequest) -> AsyncIterator[str]:  # pragma: no cover
        ...


class EngineError(Exception):
    """Raised when a provider cannot produce a turn."""
