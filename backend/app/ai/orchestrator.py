"""AI orchestration.

The single place that turns "a user sent a message in a conversation" into "a
provider was called, and here is what came back". Everything the STEP 6 flow
diagram puts between the API and the model lives here:

    context construction → model selection → parameter resolution →
    provider call → streaming → usage accounting → latency

Keeping it in one class means the route stays thin, the provider stays ignorant
of our database, and the two policies that must never be duplicated — the
context budget and the model allow-list — have exactly one implementation.

Model selection and generation parameters are resolved **server-side**. A
client may ask for a model, but only one on the allow-list is accepted; the
temperature, top-p and output budget come from configuration, never from the
request body.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal

from app.ai.base import AIProvider, with_retries
from app.ai.context import build_context
from app.ai.errors import AIError, ConfigurationError, StreamInterruptedError
from app.ai.factory import get_provider
from app.ai.prompts import build_system_message, title_system_prompt
from app.ai.types import (
    ChatMessage,
    GenerationRequest,
    GenerationStatus,
    StreamChunk,
    TokenUsage,
)
from app.core.config import settings
from app.core.logging import get_logger
from app.core.request_context import current_request_id

logger = get_logger(__name__)


@dataclass(slots=True)
class OrchestrationResult:
    """The outcome of one generation, ready to persist."""

    text: str
    model: str
    provider: str
    usage: TokenUsage
    latency_ms: int
    status: GenerationStatus
    error_code: str | None = None


@dataclass(slots=True)
class StreamEvent:
    """One event from `AIOrchestrator.stream`.

    `delta` carries incremental text; the terminal `done` or `error` event
    carries the result or the failure. Exactly one terminal event is always
    emitted, so a consumer that drives persistence from this stream cannot
    leave a message in `streaming` by accident.
    """

    type: Literal["delta", "done", "error"]
    text: str = ""
    result: OrchestrationResult | None = None
    error: AIError | None = None


class AIOrchestrator:
    def __init__(self, provider: AIProvider | None = None) -> None:
        self.provider = provider or get_provider()

    # ── Configuration resolution ─────────────────────────────────────

    def resolve_model(self, requested: str | None = None) -> str:
        """Pick the model, enforcing the server-side allow-list.

        A requested model that is not allowed is a configuration error rather
        than a silent fallback: quietly answering with a different model than
        the caller asked for would be a confusing, hard-to-debug behaviour.
        """
        allowed = settings.ai_allowed_models
        if requested:
            if requested not in allowed:
                raise ConfigurationError(
                    internal_detail=(
                        f"model '{requested}' is not on AI_ALLOWED_MODELS"
                    )
                )
            return requested

        resolved = settings.ai_model_resolved
        if not resolved:
            # A real provider needs a model name; the simulator does not.
            if self.provider.name in {"simulator", "local"} or self.provider.model:
                return self.provider.model or "simulator"
            raise ConfigurationError(
                internal_detail="no AI model configured (set AI_MODEL or AI_DEFAULT_MODEL)"
            )
        return resolved

    # ── Non-streaming ────────────────────────────────────────────────

    async def generate(
        self,
        *,
        history: list[ChatMessage],
        current_user_message: str,
        model: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        system_message: ChatMessage | None = None,
    ) -> OrchestrationResult:
        """Produce a complete response and time it."""
        resolved_model = self.resolve_model(model)
        messages = build_context(
            system_message=system_message or build_system_message(),
            history=history,
            current_user_message=current_user_message,
        )
        request = GenerationRequest(
            messages=messages,
            model=resolved_model,
            temperature=temperature if temperature is not None else settings.AI_TEMPERATURE,
            top_p=settings.AI_TOP_P,
            max_output_tokens=max_output_tokens or settings.AI_MAX_OUTPUT_TOKENS,
            stream=False,
            request_id=current_request_id(),
        )

        started = time.perf_counter()
        try:
            result = await with_retries(
                lambda: self.provider.generate(request), provider=self.provider.name
            )
        except AIError as exc:
            latency_ms = _elapsed_ms(started)
            logger.warning(
                "AI generate failed provider=%s model=%s code=%s latency_ms=%d detail=%s",
                self.provider.name,
                resolved_model,
                exc.code,
                latency_ms,
                exc.internal_detail or "",
            )
            raise

        return OrchestrationResult(
            text=result.text,
            model=result.model or resolved_model,
            provider=self.provider.name,
            usage=result.usage.normalised(),
            latency_ms=_elapsed_ms(started),
            status="completed",
        )

    # ── Streaming ────────────────────────────────────────────────────

    async def stream(
        self,
        *,
        history: list[ChatMessage],
        current_user_message: str,
        model: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        system_message: ChatMessage | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """Stream a response, emitting deltas and exactly one terminal event.

        Retries apply only to a failure that happens *before the first chunk*.
        Once text has reached the client, retrying would append a second answer
        to a partial first one, so a mid-stream failure is reported as
        `stream_interrupted` and the partial text is preserved for persistence.
        """
        resolved_model = self.resolve_model(model)
        messages = build_context(
            system_message=system_message or build_system_message(),
            history=history,
            current_user_message=current_user_message,
        )
        request = GenerationRequest(
            messages=messages,
            model=resolved_model,
            temperature=temperature if temperature is not None else settings.AI_TEMPERATURE,
            top_p=settings.AI_TOP_P,
            max_output_tokens=max_output_tokens or settings.AI_MAX_OUTPUT_TOKENS,
            stream=True,
            request_id=current_request_id(),
        )

        started = time.perf_counter()
        chunks: list[str] = []
        usage = TokenUsage()
        finish_reason: str | None = None

        try:
            async for chunk in self._stream_with_connect_retry(request):
                if chunk.text:
                    chunks.append(chunk.text)
                    yield StreamEvent(type="delta", text=chunk.text)
                if chunk.usage is not None:
                    usage = chunk.usage
                if chunk.finish_reason is not None:
                    finish_reason = chunk.finish_reason
        except AIError as exc:
            latency_ms = _elapsed_ms(started)
            logger.warning(
                "AI stream failed provider=%s model=%s code=%s latency_ms=%d detail=%s",
                self.provider.name,
                resolved_model,
                exc.code,
                latency_ms,
                exc.internal_detail or "",
            )
            yield StreamEvent(
                type="error",
                text="".join(chunks),
                result=OrchestrationResult(
                    text="".join(chunks),
                    model=resolved_model,
                    provider=self.provider.name,
                    usage=usage.normalised(),
                    latency_ms=latency_ms,
                    status="failed",
                    error_code=exc.code,
                ),
                error=exc,
            )
            return

        yield StreamEvent(
            type="done",
            result=OrchestrationResult(
                text="".join(chunks),
                model=resolved_model,
                provider=self.provider.name,
                usage=usage.normalised(),
                latency_ms=_elapsed_ms(started),
                status="completed",
                error_code=None,
            ),
        )
        _ = finish_reason  # retained for future finish-reason persistence

    async def _stream_with_connect_retry(
        self, request: GenerationRequest
    ) -> AsyncIterator[StreamChunk]:
        """Retry only while nothing has been emitted yet.

        Implemented by buffering the provider's first chunk: if obtaining it
        raises a retryable error we can safely try again, because the client
        has not seen any text. After that the iterator is passed straight
        through.
        """
        attempt = 0
        max_retries = settings.AI_MAX_RETRIES
        base = settings.AI_RETRY_BACKOFF_SECONDS

        while True:
            iterator = self.provider.stream(request).__aiter__()
            try:
                first = await iterator.__anext__()
            except StopAsyncIteration:
                return
            except AIError as exc:
                if not exc.retryable or attempt >= max_retries:
                    raise
                attempt += 1
                await self._backoff(base, attempt, exc.code)
                continue

            yield first
            try:
                async for chunk in iterator:
                    yield chunk
            except AIError as exc:
                # Mid-stream: never retried. Surfaced as an interruption.
                raise StreamInterruptedError(
                    internal_detail=(
                        f"provider failed after first chunk: {exc.code} "
                        f"({exc.internal_detail or 'no detail'})"
                    )
                ) from exc
            return

    async def _backoff(self, base: float, attempt: int, code: str) -> None:
        import asyncio
        import random

        delay = base * (2 ** (attempt - 1)) + random.uniform(0, base)
        logger.warning(
            "AI stream connect attempt %d/%d failed (%s); retrying in %.2fs",
            attempt,
            settings.AI_MAX_RETRIES,
            code,
            delay,
        )
        await asyncio.sleep(delay)

    # ── Optional title task ──────────────────────────────────────────

    async def generate_title(self, first_message: str) -> str | None:
        """Produce a short conversation title, or `None` on any failure.

        Deliberately swallow errors: a title is a convenience, and a title
        failure must never affect the answer the user actually asked for. It
        runs with its own small token budget and its own system prompt.
        """
        if not settings.AI_TITLE_GENERATION_ENABLED:
            return None
        snippet = " ".join(first_message.split())[:400]
        if not snippet:
            return None
        try:
            result = await self.generate(
                history=[],
                current_user_message=snippet,
                max_output_tokens=settings.AI_TITLE_MAX_TOKENS,
                temperature=0.2,
                system_message=ChatMessage(role="system", content=title_system_prompt()),
            )
        except AIError as exc:
            logger.info("Title generation skipped (%s)", exc.code)
            return None
        title = " ".join(result.text.strip().strip('"').split())
        if not title:
            return None
        return title[:80]


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


__all__ = ["AIOrchestrator", "OrchestrationResult", "StreamEvent"]
