"""Engine registry — resolves `AI_PROVIDER` to an implementation.

MODULE 6 adds a real provider module and registers it here; the only other
change is the environment variable. Route and service code depends on the
`Engine` protocol, never on a concrete class.
"""

from app.core.config import settings
from app.core.errors import ServiceUnavailableError
from app.services.engine.base import (
    Engine,
    EngineError,
    EngineRequest,
    EngineTurn,
)
from app.services.engine.simulator import SimulatorEngine, simulator_engine

__all__ = [
    "Engine",
    "EngineError",
    "EngineRequest",
    "EngineTurn",
    "SimulatorEngine",
    "get_engine",
    "list_providers",
]

# Provider name → factory. Kept explicit rather than dynamic imports so a typo
# fails at startup instead of on the first user request.
_PROVIDERS: dict[str, object] = {
    "simulator": lambda: simulator_engine,
}


def get_engine() -> Engine:
    """Return the configured engine, or fail loudly if it is unknown."""
    factory = _PROVIDERS.get(settings.AI_PROVIDER)
    if factory is None:
        raise ServiceUnavailableError(
            f"AI provider '{settings.AI_PROVIDER}' is not registered.",
            code="engine_not_configured",
        )
    return factory()  # type: ignore[operator, no-any-return]


def list_providers() -> list[str]:
    return sorted(_PROVIDERS)