"""OpenAI provider adapter.

Speaks the OpenAI Chat Completions protocol over the official `openai` SDK.
Because that protocol is the de-facto interchange format, this adapter also
serves any OpenAI-compatible gateway (Azure OpenAI, vLLM, OpenRouter, Together,
…) via `AI_BASE_URL` — the vendor-specific detail stays inside this file, which
is the entire point of the provider abstraction.

Credentials are read from `AI_PROVIDER_API_KEY` only. They are never logged,
never returned and never placed in an error message; the client is constructed
with the key and then the key is not referenced again.

This adapter never raises a vendor exception. Every failure is translated into
the `app.ai.errors` vocabulary so the retry policy and the API contract are
identical regardless of which provider is configured.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from app.ai.base import AIProvider, classify_http_status
from app.ai.errors import (
    AIError,
    ConfigurationError,
    InvalidProviderResponseError,
    ProviderRateLimitedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.ai.types import (
    ChatMessage,
    GenerationRequest,
    GenerationResult,
    StreamChunk,
    TokenUsage,
)
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# The provider's official endpoint. Overridden by AI_BASE_URL for a gateway.
DEFAULT_BASE_URL = "https://api.openai.com/v1"


class OpenAIProvider(AIProvider):
    name = "openai"

    def __init__(self) -> None:
        self._client: object | None = None

    # ── Client lifecycle ─────────────────────────────────────────────

    def _require_api_key(self) -> str:
        key = settings.AI_PROVIDER_API_KEY.strip()
        if not key:
            # A missing key is a configuration error, not a runtime failure:
            # the API answers with a clear, safe 503 and the app does not crash.
            raise ConfigurationError(
                internal_detail="AI_PROVIDER_API_KEY is not set for the openai provider"
            )
        return key

    def _get_client(self):
        if self._client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError as exc:  # pragma: no cover - dependency guard
                raise ConfigurationError(
                    internal_detail="the 'openai' package is not installed"
                ) from exc

            self._client = AsyncOpenAI(
                api_key=self._require_api_key(),
                base_url=(settings.AI_BASE_URL.strip() or DEFAULT_BASE_URL),
                timeout=settings.AI_TIMEOUT_SECONDS,
                # The SDK's own retries are disabled; retrying is our policy,
                # applied in one place with our own backoff and error classes.
                max_retries=0,
            )
        return self._client

    async def healthy(self) -> bool:
        """Configured and importable, without spending a request."""
        try:
            self._require_api_key()
            self._get_client()
        except AIError:
            return False
        return True

    # ── Request assembly ─────────────────────────────────────────────

    @staticmethod
    def _payload(request: GenerationRequest) -> dict[str, object]:
        return {
            "model": request.model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in request.messages
            ],
            "temperature": request.temperature,
            "top_p": request.top_p,
            "max_tokens": request.max_output_tokens,
        }

    # ── Non-streaming ────────────────────────────────────────────────

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        client = self._get_client()
        try:
            response = await client.chat.completions.create(
                **self._payload(request), stream=False
            )
        except Exception as exc:  # noqa: BLE001 - translated below
            raise _translate(exc) from exc

        try:
            choice = response.choices[0]
            text = choice.message.content or ""
            usage = _usage_from(response)
            model = getattr(response, "model", None) or request.model
            finish_reason = getattr(choice, "finish_reason", None)
        except (AttributeError, IndexError, TypeError) as exc:
            raise InvalidProviderResponseError(
                internal_detail=f"unexpected completion shape: {exc}"
            ) from exc

        if not text.strip():
            raise InvalidProviderResponseError(
                internal_detail="provider returned an empty completion"
            )
        return GenerationResult(
            text=text, model=model, usage=usage, finish_reason=finish_reason
        )

    # ── Streaming ────────────────────────────────────────────────────

    def stream(self, request: GenerationRequest) -> AsyncIterator[StreamChunk]:
        """Return an async iterator over streamed chunks.

        The `async for` body is where vendor exceptions become our errors. The
        orchestrator decides whether a failure is retryable based on how much
        text has already been emitted.
        """
        return self._stream(request)

    async def _stream(self, request: GenerationRequest) -> AsyncIterator[StreamChunk]:
        client = self._get_client()
        try:
            stream = await client.chat.completions.create(
                **self._payload(request), stream=True, stream_options={"include_usage": True}
            )
        except Exception as exc:  # noqa: BLE001 - translated below
            raise _translate(exc) from exc

        try:
            async for event in stream:
                choices = getattr(event, "choices", None) or []
                if choices:
                    delta = getattr(choices[0].delta, "content", None)
                    if delta:
                        yield StreamChunk(text=delta)
                    finish_reason = getattr(choices[0], "finish_reason", None)
                    if finish_reason:
                        yield StreamChunk(finish_reason=finish_reason)
                # The usage-bearing final event has an empty `choices` list.
                usage = _usage_from(event)
                if usage.total_tokens is not None or usage.output_tokens is not None:
                    yield StreamChunk(usage=usage)
        except AIError:
            raise
        except Exception as exc:  # noqa: BLE001 - translated below
            raise _translate(exc) from exc


def _usage_from(response: object) -> TokenUsage:
    usage = getattr(response, "usage", None)
    if usage is None:
        return TokenUsage()
    return TokenUsage(
        input_tokens=getattr(usage, "prompt_tokens", None),
        output_tokens=getattr(usage, "completion_tokens", None),
        total_tokens=getattr(usage, "total_tokens", None),
    ).normalised()


def _translate(exc: Exception) -> AIError:
    """Map any SDK/transport exception onto the standard error vocabulary.

    The mapping is by exception class name and status code rather than by
    importing the SDK's exception classes, so this module does not hard-depend
    on the SDK being importable at the point the error is classified.
    """
    name = type(exc).__name__
    status = getattr(exc, "status_code", None)

    if name in {"APITimeoutError", "TimeoutError", "ConnectTimeout"}:
        return ProviderTimeoutError(internal_detail=name)
    if name in {"APIConnectionError", "ConnectError", "ReadError"}:
        return ProviderUnavailableError(internal_detail=name)

    if isinstance(status, int):
        error = classify_http_status(status)
        # Attach the provider's message, but only for the server log.
        detail = _safe_detail(exc)
        error.internal_detail = detail or error.internal_detail
        if isinstance(error, ProviderRateLimitedError):
            retry_after = _retry_after(exc)
            if retry_after is not None:
                error.retry_after_seconds = retry_after
        return error

    # Unknown transport/SDK failure: treat as transient, but keep the detail
    # server-side only.
    return ProviderUnavailableError(internal_detail=_safe_detail(exc) or name)


def _safe_detail(exc: Exception) -> str:
    """A short, non-sensitive description of a provider failure.

    Never includes the API key: the SDK does not put credentials in exception
    text, and this function additionally truncates so a large body cannot
    become a log-flooding vector.
    """
    message = str(exc)
    # Some SDKs render the request body into the error; keep only the head.
    return " ".join(message.split())[:300]


def _retry_after(exc: Exception) -> float | None:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if not headers:
        return None
    raw = headers.get("retry-after") if hasattr(headers, "get") else None
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _dumps(value: object) -> str:  # pragma: no cover - debug helper
    return json.dumps(value, ensure_ascii=False)


__all__ = ["DEFAULT_BASE_URL", "OpenAIProvider"]
