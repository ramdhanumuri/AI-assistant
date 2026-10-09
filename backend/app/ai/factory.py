"""Provider selection.

`AI_PROVIDER` names a provider; this module resolves it to an implementation.
Registration is explicit rather than a dynamic import so a typo fails loudly
instead of resolving to `None` at the first user request, and the registry is
the single list the admin surface reads to report what is available.

Adding a provider is two lines here plus one adapter file. Nothing else in the
application changes — routes, services and schemas depend on `AIProvider`, not
on a vendor.
"""

from __future__ import annotations

from collections.abc import Callable

from app.ai.base import AIProvider
from app.ai.errors import ConfigurationError
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _build_simulator() -> AIProvider:
    # Imported lazily so the registry stays cheap to import and the engine
    # package (which pulls in the block vocabulary) is only loaded when the
    # simulator is actually selected.
    from app.ai.providers.simulator import SimulatorProvider

    return SimulatorProvider()


def _build_openai() -> AIProvider:
    from app.ai.providers.openai import OpenAIProvider

    return OpenAIProvider()


# Provider name → constructor. The names are the values accepted by
# `AI_PROVIDER`.
_REGISTRY: dict[str, Callable[[], AIProvider]] = {
    "simulator": _build_simulator,
    "local": _build_simulator,
    "openai": _build_openai,
}

# One instance per provider name. Providers are stateless with respect to the
# database and the client is safe to share, so rebuilding one per request would
# only recreate the HTTP client.
_instances: dict[str, AIProvider] = {}


def list_providers() -> list[str]:
    """The registered provider names, deduplicated and sorted."""
    return sorted(set(_REGISTRY))


def is_registered(name: str) -> bool:
    return name.strip().lower() in _REGISTRY


def get_provider(name: str | None = None) -> AIProvider:
    """Resolve a provider by name, or the configured one when omitted.

    Cached per name. Use `build_provider` when the caller needs an instance it
    can own (for example one bound to a private event loop).

    Raises `ConfigurationError` (never a bare `KeyError`) for an unknown name,
    so the API can answer with a safe configuration error rather than a 500.
    """
    key = (name or settings.AI_PROVIDER).strip().lower()
    if not is_registered(key):
        raise _unknown(key)
    if key not in _instances:
        _instances[key] = _REGISTRY[key]()
    return _instances[key]


def build_provider(name: str | None = None) -> AIProvider:
    """Construct a fresh, uncached provider instance.

    Needed where a provider owns loop-bound resources: a cached instance built
    on one event loop cannot be reused on another.
    """
    key = (name or settings.AI_PROVIDER).strip().lower()
    if not is_registered(key):
        raise _unknown(key)
    return _REGISTRY[key]()


def _unknown(key: str) -> ConfigurationError:
    return ConfigurationError(
        internal_detail=(
            f"AI provider '{key}' is not registered; "
            f"known providers: {', '.join(list_providers())}"
        )
    )


def reset_providers() -> None:
    """Drop cached instances. Used by tests that swap the configuration."""
    _instances.clear()


__all__ = [
    "build_provider",
    "get_provider",
    "is_registered",
    "list_providers",
    "reset_providers",
]
