"""Deterministic local provider.

Implements `AIProvider` on top of the rich-turn simulator engine, so the
streaming transport, context budget, persistence and usage accounting can all
be exercised end to end without provider credentials. This is what makes the
STEP 6 test suite hermetic: no network, no API key, no flakiness, and the same
transport the real provider uses.

It is a real provider in the architectural sense — it satisfies the interface
and is selected by `AI_PROVIDER=simulator` — but it is *not* a language model.
It must never be the production default for a real deployment, and it says so
in the health check.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from app.ai.base import AIProvider
from app.ai.types import (
    GenerationRequest,
    GenerationResult,
    StreamChunk,
    TokenUsage,
)
from app.services.engine.base import EngineRequest

# The simulator's recipes are keyed on the latest user turn.
_DEFAULT_MODE = "general"


class SimulatorProvider(AIProvider):
    name = "simulator"

    @property
    def model(self) -> str:
        return "simulator"

    def _engine_request(self, request: GenerationRequest) -> EngineRequest:
        # The last non-system message is the current user turn; earlier user
        # turns become the history the recipe can reference.
        user_messages = [m.content for m in request.messages if m.role == "user"]
        current = user_messages[-1] if user_messages else ""
        return EngineRequest(
            prompt=current,
            mode_id=_DEFAULT_MODE,
            voice=False,
            history=user_messages[:-1],
        )

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        from app.services.engine.simulator import simulator_engine

        turn = simulator_engine.generate(self._engine_request(request))
        text = "\n\n".join(
            block.body
            for block in turn.blocks
            if getattr(block, "kind", None) == "text" and getattr(block, "body", None)
        )
        return GenerationResult(
            text=text,
            model="simulator",
            usage=TokenUsage(total_tokens=turn.tokens).normalised(),
            finish_reason="stop",
        )

    async def _stream(self, request: GenerationRequest) -> AsyncIterator[StreamChunk]:
        from app.services.engine.simulator import simulator_engine

        turn = simulator_engine.generate(self._engine_request(request))
        total = 0
        for block in turn.blocks:
            body = getattr(block, "body", None)
            if isinstance(body, str) and body:
                total += len(body)
                yield StreamChunk(text=body)
        yield StreamChunk(
            finish_reason="stop",
            usage=TokenUsage(total_tokens=turn.tokens).normalised(),
        )

    def stream(self, request: GenerationRequest) -> AsyncIterator[StreamChunk]:
        return self._stream(request)

    async def healthy(self) -> bool:
        return True


__all__ = ["SimulatorProvider"]
