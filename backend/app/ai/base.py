"""The provider interface and the shared retry policy.

Everything above this module talks to `AIProvider`, never to a vendor. The
interface is intentionally tiny — `generate`, `stream` and `healthy` — because
the smaller the contract, the less a new provider has to implement and the
less the rest of the application can accidentally couple to one vendor.

The retry policy lives here rather than in each provider so that "retry only
what is safe to retry" is written once. It consults `AIError.retryable`, adds
exponential backoff with jitter, and is bounded by `AI_MAX_RETRIES`. Errors
that are permanent by nature (a bad key, an oversized prompt, a malformed
response) are never retried — repeating them only wastes the user's time and
can trip a provider's abuse controls.
"""

from __future__ import annotations

import asyncio
import random
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.ai.errors import (
    AIError,
    ProviderRateLimitedError,
    ProviderUnavailableError,
)
from app.ai.types import GenerationRequest, GenerationResult, StreamChunk
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class AIProvider(ABC):
    """The contract every model provider implements."""

    #: Stable identifier used in config, logs and usage rows.
    name: str = "unknown"

    @property
    def model(self) -> str:
        """The model this instance is bound to."""
        return settings.ai_model_resolved

    @abstractmethod
    async def generate(self, request: GenerationRequest) -> GenerationResult:
        """Produce a complete response in one call."""
        raise NotImplementedError

    @abstractmethod
    def stream(self, request: GenerationRequest) -> AsyncIterator[StreamChunk]:
        """Yield the response incrementally.

        Declared as a plain method returning an async iterator rather than an
        `async def` generator: the caller must be able to obtain the iterator
        synchronously (before awaiting the first chunk) so a connection error
        surfaces as a normal exception rather than an `async for` traceback.
        """
        raise NotImplementedError

    async def healthy(self) -> bool:
        """Whether the provider is usable. Cheap by default.

        Overridden by real providers to check configuration without making a
        billable call.
        """
        return True


async def with_retries(operation, *, provider: str):
    """Run `operation()` with a bounded, jittered retry policy.

    `operation` is a zero-argument callable returning an awaitable. Only
    `AIError`s marked `retryable` are retried; anything else propagates
    immediately. Backoff is exponential with full jitter so a fleet of workers
    recovering from the same provider blip does not synchronise into a
    thundering herd.
    """
    max_retries = settings.AI_MAX_RETRIES
    base = settings.AI_RETRY_BACKOFF_SECONDS
    attempt = 0
    while True:
        try:
            return await operation()
        except AIError as exc:
            if not exc.retryable or attempt >= max_retries:
                raise
            attempt += 1
            # `retry_after` from the provider wins when present — honouring it
            # is both politer and more likely to succeed than our own guess.
            delay = base * (2 ** (attempt - 1))
            if isinstance(exc, ProviderRateLimitedError) and exc.retry_after_seconds:
                delay = max(delay, exc.retry_after_seconds)
            delay += random.uniform(0, base)  # full jitter
            logger.warning(
                "AI provider '%s' attempt %d/%d failed (%s); retrying in %.2fs",
                provider,
                attempt,
                max_retries,
                exc.code,
                delay,
            )
            await asyncio.sleep(delay)


def classify_http_status(status: int) -> AIError:
    """Map an upstream HTTP status to the standard error vocabulary.

    Kept in one place so every provider classifies the same way, and so the
    retry decision (via `retryable`) is consistent across vendors.
    """
    if status in (401, 403):
        from app.ai.errors import ProviderAuthenticationError

        return ProviderAuthenticationError(status_code=status)
    if status == 429:
        return ProviderRateLimitedError(status_code=status)
    if status == 408:
        from app.ai.errors import ProviderTimeoutError

        return ProviderTimeoutError(status_code=status)
    if 400 <= status < 500:
        # A 4xx that is not auth/rate/timeout is a malformed request from us;
        # retrying it would fail identically.
        from app.ai.errors import InvalidProviderResponseError

        return InvalidProviderResponseError(
            internal_detail=f"provider rejected the request with status {status}"
        )
    return ProviderUnavailableError(status_code=status)


__all__ = ["AIProvider", "classify_http_status", "with_retries"]
