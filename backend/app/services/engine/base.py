"""The model-layer seam.

This is the single boundary between the API and "the model". MODULE 6 replaces
`SimulatorEngine` with a real provider by registering a new implementation here
and flipping `AI_PROVIDER`; nothing in the routes, services or schemas changes.

Contract:
  * `generate` takes a prompt plus the active mode and returns a complete
    assistant turn (reasoning, tool traces, rich blocks, token count).
  * Implementations must be side-effect free with respect to the database —
    persistence is the service layer's job.
"""

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


class EngineError(Exception):
    """Raised when a provider cannot produce a turn."""