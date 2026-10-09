"""Engine registry — resolves `AI_PROVIDER` to an implementation.

STEP 6 unifies provider selection in `app.ai.factory`: the same `AI_PROVIDER`
value now resolves both the real streaming providers and the rich-turn engine
used by the synchronous chat write path. This module keeps the rich-turn
registry so `ConversationService` (which is synchronous and produces the UI's
block vocabulary) continues to work unchanged for every provider.

Route and service code depends on the `Engine` protocol, never on a concrete
class.
"""

from app.ai.factory import (
    build_provider,
    get_provider,
    is_registered,
    list_providers,
    reset_providers,
)
from app.core.config import settings
from app.core.errors import ServiceUnavailableError
from app.services.engine.ai_engine import AIEngine
from app.services.engine.base import (
    Engine,
    EngineError,
    EngineRequest,
    EngineTurn,
    StreamingEngine,
)
from app.services.engine.simulator import SimulatorEngine, simulator_engine

__all__ = [
    "AIEngine",
    "Engine",
    "EngineError",
    "EngineRequest",
    "EngineTurn",
    "SimulatorEngine",
    "StreamingEngine",
    "build_provider",
    "get_engine",
    "get_provider",
    "is_registered",
    "list_providers",
    "reset_providers",
]

# Provider name → rich-turn engine factory. `simulator` keeps its singleton
# (it is stateless and deterministic); a real provider is wrapped by `AIEngine`,
# which builds its own provider per call so the async client stays bound to the
# loop it was created on.
_ENGINES: dict[str, object] = {
    "simulator": lambda: simulator_engine,
    "local": lambda: simulator_engine,
    "openai": lambda: AIEngine("openai"),
}


def get_engine() -> Engine:
    """Return the configured rich-turn engine, or fail with a safe error."""
    key = settings.AI_PROVIDER.strip().lower()
    factory = _ENGINES.get(key)
    if factory is None:
        raise ServiceUnavailableError(
            f"AI provider '{settings.AI_PROVIDER}' is not registered.",
            code="engine_not_configured",
        )
    return factory()  # type: ignore[operator, no-any-return]