"""STEP 6 — real AI integration.

Covers the provider abstraction, the context manager, the orchestrator's
retry/streaming policy, the SSE transport, persistence and usage accounting,
and the security invariants that must survive the integration.

Everything runs against the deterministic `simulator` provider: a real
`AIProvider` implementation selected by configuration, so no test needs a
production API key and the suite stays hermetic. The OpenAI adapter is
exercised through a fake SDK object, which is the only way to test vendor error
translation without making a billable network call.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from app.ai import context as ai_context
from app.ai.base import AIProvider, classify_http_status, with_retries
from app.ai.errors import (
    AIError,
    ConfigurationError,
    ContextTooLargeError,
    ERROR_CODES,
    InvalidProviderResponseError,
    ProviderAuthenticationError,
    ProviderRateLimitedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    StreamInterruptedError,
)
from app.ai.factory import (
    build_provider,
    get_provider,
    is_registered,
    list_providers,
    reset_providers,
)
from app.ai.orchestrator import AIOrchestrator
from app.ai.prompts import build_system_message, system_prompt
from app.ai.providers.openai import OpenAIProvider
from app.ai.types import ChatMessage, GenerationRequest, StreamChunk, TokenUsage
from app.core.config import settings

from tests.conftest import TEST_PASSWORD, add_second_user


# ── Test doubles ──────────────────────────────────────────────────────
# A provider whose behaviour is scripted per test. It is a real AIProvider
# subclass, so it flows through the same orchestrator, retry policy and
# persistence path as any vendor — only the I/O is replaced.


class ScriptedProvider(AIProvider):
    """Yields a fixed script of chunks, or raises a scripted error."""

    name = "scripted"

    @property
    def model(self) -> str:
        return "scripted-model"

    def __init__(
        self,
        *,
        chunks: list[str] | None = None,
        error: AIError | None = None,
        error_after: int | None = None,
        fail_times: int = 0,
    ) -> None:
        self.chunks = chunks if chunks is not None else ["Hello", " ", "world"]
        self.error = error
        self.error_after = error_after
        self.fail_times = fail_times
        self.calls = 0

    def _should_fail_now(self) -> bool:
        """Whether the current attempt fails before any text is emitted.

        `error_after` models a mid-stream failure, so it never counts as a
        pre-stream failure. Otherwise `fail_times` fails the first N attempts
        (0 = always fail).
        """
        if self.error is None or self.error_after is not None:
            return False
        return self.fail_times == 0 or self.calls <= self.fail_times

    async def generate(self, request: GenerationRequest):
        from app.ai.types import GenerationResult

        self.calls += 1
        if self._should_fail_now():
            raise self.error
        text = "".join(self.chunks)
        return GenerationResult(text=text, model=request.model, usage=TokenUsage(total_tokens=7))

    async def _stream(self, request: GenerationRequest):
        self.calls += 1
        if self._should_fail_now():
            raise self.error
        for index, chunk in enumerate(self.chunks):
            if self.error is not None and self.error_after == index:
                raise self.error
            yield StreamChunk(text=chunk)
        yield StreamChunk(finish_reason="stop", usage=TokenUsage(total_tokens=7))

    def stream(self, request: GenerationRequest):
        return self._stream(request)

    async def healthy(self) -> bool:
        return self.error is None


def _collect(agen) -> list:
    async def run():
        return [item async for item in agen]

    return asyncio.run(run())


# ── Provider abstraction ─────────────────────────────────────────────


class TestProviderRegistry:
    def test_simulator_and_openai_are_registered(self) -> None:
        providers = list_providers()
        assert "simulator" in providers
        assert "openai" in providers

    def test_registry_lookup_is_case_insensitive(self) -> None:
        assert is_registered("OpenAI")
        assert is_registered("  simulator  ")

    def test_unknown_provider_raises_configuration_error(self) -> None:
        with pytest.raises(ConfigurationError):
            get_provider("does-not-exist")

    def test_build_provider_returns_interface_implementation(self) -> None:
        provider = build_provider("simulator")
        assert isinstance(provider, AIProvider)
        assert provider.name == "simulator"

    def test_build_provider_returns_fresh_instances(self) -> None:
        assert build_provider("simulator") is not build_provider("simulator")

    def test_get_provider_caches_instances(self, monkeypatch) -> None:
        reset_providers()
        try:
            assert get_provider("simulator") is get_provider("simulator")
        finally:
            reset_providers()


class TestSimulatorProvider:
    def test_generate_produces_text(self) -> None:
        provider = get_provider("simulator")
        result = asyncio.run(
            provider.generate(
                GenerationRequest(
                    messages=[ChatMessage(role="user", content="Explain DBMS")],
                    model="simulator",
                    temperature=0.7,
                    top_p=1.0,
                    max_output_tokens=256,
                    stream=False,
                )
            )
        )
        assert result.text.strip()
        assert result.usage.total_tokens is not None

    def test_stream_yields_chunks_then_finishes(self) -> None:
        provider = get_provider("simulator")
        request = GenerationRequest(
            messages=[ChatMessage(role="user", content="AI అంటే ఏమిటి?")],
            model="simulator",
            temperature=0.7,
            top_p=1.0,
            max_output_tokens=256,
        )
        chunks = _collect(provider.stream(request))
        assert any(chunk.text for chunk in chunks)
        assert chunks[-1].finish_reason == "stop"

    def test_unicode_prompt_is_preserved(self) -> None:
        provider = get_provider("simulator")
        result = asyncio.run(
            provider.generate(
                GenerationRequest(
                    messages=[ChatMessage(role="user", content="AI అంటే ఏమిటి? 🚀")],
                    model="simulator",
                    temperature=0.7,
                    top_p=1.0,
                    max_output_tokens=64,
                    stream=False,
                )
            )
        )
        assert result.text.strip()


class TestOpenAIProviderConfiguration:
    def test_missing_api_key_is_a_configuration_error(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "AI_PROVIDER_API_KEY", "")
        provider = OpenAIProvider()
        with pytest.raises(ConfigurationError):
            asyncio.run(
                provider.generate(
                    GenerationRequest(
                        messages=[ChatMessage(role="user", content="hi")],
                        model="gpt-4o-mini",
                        temperature=0.7,
                        top_p=1.0,
                        max_output_tokens=16,
                        stream=False,
                    )
                )
            )

    def test_health_is_false_without_a_key(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "AI_PROVIDER_API_KEY", "")
        assert asyncio.run(OpenAIProvider().healthy()) is False

    def test_health_is_true_with_a_key(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "AI_PROVIDER_API_KEY", "sk-test-not-real")
        monkeypatch.setattr(settings, "AI_BASE_URL", "https://example.invalid/v1")
        assert asyncio.run(OpenAIProvider().healthy()) is True


class TestOpenAIProviderErrorTranslation:
    """The adapter must never surface a vendor exception or leak the key."""

    def _request(self) -> GenerationRequest:
        return GenerationRequest(
            messages=[ChatMessage(role="user", content="hi")],
            model="gpt-4o-mini",
            temperature=0.7,
            top_p=1.0,
            max_output_tokens=16,
            stream=False,
        )

    def test_http_429_becomes_rate_limited(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "AI_PROVIDER_API_KEY", "sk-test-not-real")

        class RateLimit(Exception):
            status_code = 429

        provider = OpenAIProvider()

        class Client:
            class chat:  # noqa: N801 - mirrors the SDK's attribute path
                class completions:
                    @staticmethod
                    async def create(**_):
                        raise RateLimit("slow down")

        provider._client = Client()
        with pytest.raises(ProviderRateLimitedError):
            asyncio.run(provider.generate(self._request()))

    def test_http_500_becomes_unavailable(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "AI_PROVIDER_API_KEY", "sk-test-not-real")

        class ServerError(Exception):
            status_code = 500

        provider = OpenAIProvider()

        class Client:
            class chat:  # noqa: N801
                class completions:
                    @staticmethod
                    async def create(**_):
                        raise ServerError("boom")

        provider._client = Client()
        with pytest.raises(ProviderUnavailableError):
            asyncio.run(provider.generate(self._request()))

    def test_http_401_becomes_authentication_error(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "AI_PROVIDER_API_KEY", "sk-test-not-real")

        class Unauthorized(Exception):
            status_code = 401

        provider = OpenAIProvider()

        class Client:
            class chat:  # noqa: N801
                class completions:
                    @staticmethod
                    async def create(**_):
                        raise Unauthorized("bad key")

        provider._client = Client()
        with pytest.raises(ProviderAuthenticationError):
            asyncio.run(provider.generate(self._request()))

    def test_empty_completion_is_an_invalid_response(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "AI_PROVIDER_API_KEY", "sk-test-not-real")
        provider = OpenAIProvider()

        class Message:
            content = ""

        class Choice:
            message = Message()
            finish_reason = "stop"

        class Response:
            choices = [Choice()]
            model = "gpt-4o-mini"
            usage = None

        class Client:
            class chat:  # noqa: N801
                class completions:
                    @staticmethod
                    async def create(**_):
                        return Response()

        provider._client = Client()
        with pytest.raises(InvalidProviderResponseError):
            asyncio.run(provider.generate(self._request()))

    def test_error_detail_never_contains_the_api_key(self, monkeypatch) -> None:
        secret = "sk-super-secret-value-123"
        monkeypatch.setattr(settings, "AI_PROVIDER_API_KEY", secret)

        class ServerError(Exception):
            status_code = 503

        provider = OpenAIProvider()

        class Client:
            class chat:  # noqa: N801
                class completions:
                    @staticmethod
                    async def create(**_):
                        raise ServerError("upstream refused")

        provider._client = Client()
        with pytest.raises(AIError) as excinfo:
            asyncio.run(provider.generate(self._request()))
        assert secret not in (excinfo.value.internal_detail or "")
        assert secret not in excinfo.value.message


class TestErrorVocabulary:
    def test_status_classification(self) -> None:
        assert isinstance(classify_http_status(401), ProviderAuthenticationError)
        assert isinstance(classify_http_status(403), ProviderAuthenticationError)
        assert isinstance(classify_http_status(429), ProviderRateLimitedError)
        assert isinstance(classify_http_status(500), ProviderUnavailableError)
        assert isinstance(classify_http_status(503), ProviderUnavailableError)
        assert isinstance(classify_http_status(400), InvalidProviderResponseError)

    def test_every_error_code_is_in_the_vocabulary(self) -> None:
        for error in (
            ConfigurationError(),
            ProviderAuthenticationError(),
            ProviderRateLimitedError(),
            ProviderTimeoutError(),
            ProviderUnavailableError(),
            InvalidProviderResponseError(),
            ContextTooLargeError(),
            StreamInterruptedError(),
        ):
            assert error.code in ERROR_CODES

    def test_retryable_flags_are_conservative(self) -> None:
        assert ProviderUnavailableError().retryable is True
        assert ProviderTimeoutError().retryable is True
        assert ProviderRateLimitedError().retryable is True
        assert ConfigurationError().retryable is False
        assert ProviderAuthenticationError().retryable is False
        assert ContextTooLargeError().retryable is False
        assert InvalidProviderResponseError().retryable is False


class TestRetryPolicy:
    def test_retryable_error_is_retried_then_succeeds(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "AI_MAX_RETRIES", 3)
        monkeypatch.setattr(settings, "AI_RETRY_BACKOFF_SECONDS", 0.0)
        provider = ScriptedProvider(
            chunks=["ok"], error=ProviderUnavailableError(), fail_times=2
        )
        result = asyncio.run(
            with_retries(
                lambda: provider.generate(
                    GenerationRequest(
                        messages=[ChatMessage(role="user", content="hi")],
                        model="simulator",
                        temperature=0.7,
                        top_p=1.0,
                        max_output_tokens=16,
                    )
                ),
                provider="scripted",
            )
        )
        assert result.text == "ok"
        assert provider.calls == 3

    def test_permanent_error_is_not_retried(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "AI_MAX_RETRIES", 3)
        monkeypatch.setattr(settings, "AI_RETRY_BACKOFF_SECONDS", 0.0)
        provider = ScriptedProvider(error=ConfigurationError(), fail_times=99)
        with pytest.raises(ConfigurationError):
            asyncio.run(
                with_retries(
                    lambda: provider.generate(
                        GenerationRequest(
                            messages=[ChatMessage(role="user", content="hi")],
                            model="simulator",
                            temperature=0.7,
                            top_p=1.0,
                            max_output_tokens=16,
                        )
                    ),
                    provider="scripted",
                )
            )
        assert provider.calls == 1

    def test_retries_are_bounded(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "AI_MAX_RETRIES", 2)
        monkeypatch.setattr(settings, "AI_RETRY_BACKOFF_SECONDS", 0.0)
        provider = ScriptedProvider(error=ProviderUnavailableError(), fail_times=99)
        with pytest.raises(ProviderUnavailableError):
            asyncio.run(
                with_retries(
                    lambda: provider.generate(
                        GenerationRequest(
                            messages=[ChatMessage(role="user", content="hi")],
                            model="simulator",
                            temperature=0.7,
                            top_p=1.0,
                            max_output_tokens=16,
                        )
                    ),
                    provider="scripted",
                )
            )
        # One initial attempt plus two retries.
        assert provider.calls == 3


# ── Context management ───────────────────────────────────────────────


class TestContextManager:
    def _system(self) -> ChatMessage:
        return build_system_message()

    def test_empty_conversation_is_system_plus_current(self) -> None:
        messages = ai_context.build_context(
            system_message=self._system(), history=[], current_user_message="hi"
        )
        assert messages[0].role == "system"
        assert messages[-1].content == "hi"
        assert len(messages) == 2

    def test_history_is_preserved_in_order(self) -> None:
        history = [
            ChatMessage(role="user", content="first"),
            ChatMessage(role="assistant", content="reply"),
        ]
        messages = ai_context.build_context(
            system_message=self._system(), history=history, current_user_message="second"
        )
        assert messages[0].role == "system"
        assert [m.content for m in messages[1:]] == ["first", "reply", "second"]

    def test_message_limit_drops_the_oldest(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "AI_MAX_CONTEXT_MESSAGES", 2)
        history = [ChatMessage(role="user", content=f"m{i}") for i in range(10)]
        messages = ai_context.build_context(
            system_message=self._system(), history=history, current_user_message="now"
        )
        # Only the two most recent history turns survive.
        assert [m.content for m in messages[1:-1]] == ["m8", "m9"]
        assert messages[-1].content == "now"

    def test_token_budget_drops_older_turns(self, monkeypatch) -> None:
        # The system prompt alone costs ~200 tokens, so the budget must clear it
        # plus the current turn before any history can be admitted.
        monkeypatch.setattr(settings, "AI_MAX_CONTEXT_MESSAGES", 50)
        monkeypatch.setattr(settings, "AI_MAX_INPUT_TOKENS", 400)
        history = [ChatMessage(role="user", content="x" * 400) for _ in range(5)]
        messages = ai_context.build_context(
            system_message=self._system(), history=history, current_user_message="now"
        )
        # The current turn is never dropped, and oversized history is trimmed.
        assert messages[-1].content == "now"
        assert len(messages) < len(history) + 2

    def test_current_message_is_never_truncated(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "AI_MAX_INPUT_TOKENS", 500)
        long_current = "y" * 120
        messages = ai_context.build_context(
            system_message=self._system(), history=[], current_user_message=long_current
        )
        assert messages[-1].content == long_current

    def test_oversized_prompt_raises_context_too_large(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "AI_MAX_INPUT_TOKENS", 10)
        with pytest.raises(ContextTooLargeError):
            ai_context.build_context(
                system_message=self._system(),
                history=[],
                current_user_message="z" * 500,
            )

    def test_token_estimate_charges_non_ascii_more(self) -> None:
        ascii_cost = ai_context.estimate_tokens("abcdefgh")
        telugu_cost = ai_context.estimate_tokens("అఆఇఈఉఊఋఌ")
        assert telugu_cost > ascii_cost

    def test_unicode_survives_context_construction(self) -> None:
        messages = ai_context.build_context(
            system_message=self._system(),
            history=[ChatMessage(role="user", content="DBMS ante enti?")],
            current_user_message="DBMS అంటే ఏమిటి? Explain in simple English.",
        )
        assert messages[-1].content.endswith("Explain in simple English.")
        assert "అంటే" in messages[-1].content


class TestSystemPrompt:
    def test_system_prompt_is_not_empty_and_is_server_owned(self) -> None:
        assert system_prompt().strip()
        assert build_system_message().role == "system"

    def test_operator_override_replaces_the_prompt(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "AI_SYSTEM_PROMPT", "CUSTOM INSTRUCTION")
        assert system_prompt() == "CUSTOM INSTRUCTION"


# ── Orchestrator ─────────────────────────────────────────────────────


class TestOrchestratorModelSelection:
    def test_allow_list_rejects_an_arbitrary_model(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "AI_ALLOWED_MODELS", ["gpt-4o-mini"])
        monkeypatch.setattr(settings, "AI_MODEL", "gpt-4o-mini")
        orchestrator = AIOrchestrator(ScriptedProvider())
        with pytest.raises(ConfigurationError):
            orchestrator.resolve_model("gpt-4o-evil-unlisted")

    def test_allow_list_accepts_a_listed_model(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "AI_ALLOWED_MODELS", ["gpt-4o-mini"])
        monkeypatch.setattr(settings, "AI_MODEL", "gpt-4o-mini")
        orchestrator = AIOrchestrator(ScriptedProvider())
        assert orchestrator.resolve_model("gpt-4o-mini") == "gpt-4o-mini"

    def test_default_model_is_used_when_none_requested(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "AI_MODEL", "gpt-4o-mini")
        monkeypatch.setattr(settings, "AI_DEFAULT_MODEL", "")
        monkeypatch.setattr(settings, "AI_ALLOWED_MODELS", ["gpt-4o-mini"])
        orchestrator = AIOrchestrator(ScriptedProvider())
        assert orchestrator.resolve_model(None) == "gpt-4o-mini"


class TestOrchestratorStreaming:
    def test_stream_emits_deltas_then_done(self) -> None:
        orchestrator = AIOrchestrator(ScriptedProvider(chunks=["a", "b", "c"]))
        events = _collect(
            orchestrator.stream(history=[], current_user_message="hi")
        )
        deltas = [e.text for e in events if e.type == "delta"]
        assert deltas == ["a", "b", "c"]
        assert events[-1].type == "done"
        assert events[-1].result.status == "completed"
        assert events[-1].result.text == "abc"

    def test_connect_failure_is_retried_before_any_text(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "AI_MAX_RETRIES", 2)
        monkeypatch.setattr(settings, "AI_RETRY_BACKOFF_SECONDS", 0.0)
        provider = ScriptedProvider(
            chunks=["ok"], error=ProviderUnavailableError(), fail_times=1
        )
        orchestrator = AIOrchestrator(provider)
        events = _collect(orchestrator.stream(history=[], current_user_message="hi"))
        assert events[-1].type == "done"
        assert provider.calls == 2

    def test_mid_stream_failure_is_reported_not_retried(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "AI_MAX_RETRIES", 3)
        monkeypatch.setattr(settings, "AI_RETRY_BACKOFF_SECONDS", 0.0)
        provider = ScriptedProvider(
            chunks=["a", "b", "c"],
            error=ProviderUnavailableError(),
            error_after=1,
        )
        orchestrator = AIOrchestrator(provider)
        events = _collect(orchestrator.stream(history=[], current_user_message="hi"))
        assert events[-1].type == "error"
        assert events[-1].result.status == "failed"
        assert events[-1].result.error_code == "stream_interrupted"
        # The partial text produced before the failure is preserved.
        assert events[-1].result.text == "a"
        assert provider.calls == 1

    def test_context_too_large_raises_before_streaming(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "AI_MAX_INPUT_TOKENS", 10)
        orchestrator = AIOrchestrator(ScriptedProvider())
        with pytest.raises(ContextTooLargeError):
            _collect(
                orchestrator.stream(history=[], current_user_message="x" * 500)
            )

    def test_exactly_one_terminal_event(self) -> None:
        orchestrator = AIOrchestrator(ScriptedProvider())
        events = _collect(orchestrator.stream(history=[], current_user_message="hi"))
        terminal = [e for e in events if e.type in {"done", "error"}]
        assert len(terminal) == 1


class TestTitleGeneration:
    def test_title_generation_can_be_disabled(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "AI_TITLE_GENERATION_ENABLED", False)
        orchestrator = AIOrchestrator(ScriptedProvider(chunks=["A Title"]))
        assert asyncio.run(orchestrator.generate_title("hello")) is None

    def test_title_failure_is_swallowed(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "AI_TITLE_GENERATION_ENABLED", True)
        orchestrator = AIOrchestrator(ScriptedProvider(error=ProviderUnavailableError()))
        # A title failure must never propagate to the caller.
        assert asyncio.run(orchestrator.generate_title("hello")) is None

    def test_title_is_trimmed(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "AI_TITLE_GENERATION_ENABLED", True)
        orchestrator = AIOrchestrator(ScriptedProvider(chunks=['"Python Basics"']))
        assert asyncio.run(orchestrator.generate_title("hello")) == "Python Basics"


# ── SSE transport ────────────────────────────────────────────────────


def _parse_sse(text: str) -> list[tuple[str, dict]]:
    """Parse an SSE body into (event, data) pairs."""
    events: list[tuple[str, dict]] = []
    for block in text.strip().split("\n\n"):
        event_name = None
        data = None
        for line in block.splitlines():
            if line.startswith("event:"):
                event_name = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data = json.loads(line[len("data:") :].strip())
        if event_name is not None:
            events.append((event_name, data or {}))
    return events


class TestSSEHelper:
    def test_event_is_json_encoded(self) -> None:
        from app.api.sse import sse_event

        frame = sse_event("delta", {"text": "a\nb"})
        assert frame.startswith("event: delta\n")
        # A raw newline inside data would break framing; JSON escapes it.
        assert "\n\n" in frame
        assert json.loads(frame.split("data: ", 1)[1].strip())["text"] == "a\nb"

    def test_unicode_is_not_ascii_escaped(self) -> None:
        from app.api.sse import sse_event

        frame = sse_event("delta", {"text": "AI అంటే ఏమిటి?"})
        assert "అంటే" in frame


# ── HTTP: capabilities and usage ─────────────────────────────────────


class TestCapabilitiesEndpoint:
    def test_requires_authentication(self, anon_client: TestClient) -> None:
        assert anon_client.get("/api/v1/ai/capabilities").status_code == 401

    def test_reports_provider_without_credentials(self, client: TestClient) -> None:
        body = client.get("/api/v1/ai/capabilities").json()
        assert body["provider"] == "simulator"
        assert body["configured"] is True
        # No credential or base URL may appear anywhere in the payload.
        serialised = json.dumps(body).lower()
        assert "api_key" not in serialised
        assert "base_url" not in serialised


class TestUsageEndpoint:
    def test_requires_authentication(self, anon_client: TestClient) -> None:
        assert anon_client.get("/api/v1/ai/usage").status_code == 401

    def test_usage_starts_at_zero(self, client: TestClient) -> None:
        body = client.get("/api/v1/ai/usage").json()
        assert body["totalRequests"] == 0


# ── HTTP: streaming chat ─────────────────────────────────────────────


def _create_conversation(client: TestClient, **payload) -> str:
    response = client.post("/api/v1/conversations", json=payload or {"mode": "general"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _stream(client: TestClient, conversation_id: str, body: str, **extra):
    return client.post(
        f"/api/v1/ai/conversations/{conversation_id}/messages/stream",
        json={"body": body, **extra},
    )


class TestStreamingEndpoint:
    def test_requires_authentication(self, anon_client: TestClient) -> None:
        response = anon_client.post(
            "/api/v1/ai/conversations/c-anything/messages/stream",
            json={"body": "hi"},
        )
        assert response.status_code == 401

    def test_streams_meta_delta_and_done(self, client: TestClient) -> None:
        conversation_id = _create_conversation(client)
        response = _stream(client, conversation_id, "Explain machine learning simply.")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

        events = _parse_sse(response.text)
        names = [name for name, _ in events]
        assert names[0] == "meta"
        assert names[-1] == "done"
        assert "delta" in names

        meta = events[0][1]
        assert meta["conversationId"] == conversation_id
        assert meta["userMessage"]["role"] == "user"
        assert meta["assistantMessage"]["role"] == "assistant"
        assert meta["provider"] == "simulator"

        assembled = "".join(data["text"] for name, data in events if name == "delta")
        assert assembled.strip()

    def test_unicode_turn_round_trips(self, client: TestClient) -> None:
        conversation_id = _create_conversation(client)
        prompt = "AI అంటే ఏమిటి? Explain in simple English. 🚀"
        response = _stream(client, conversation_id, prompt)
        assert response.status_code == 200
        events = _parse_sse(response.text)
        meta = events[0][1]
        assert meta["userMessage"]["blocks"][0]["body"] == prompt

        # And it is stored verbatim.
        transcript = client.get(
            f"/api/v1/conversations/{conversation_id}/messages"
        ).json()
        assert transcript["items"][0]["blocks"][0]["body"] == prompt

    def test_cross_user_conversation_is_404(self, client: TestClient) -> None:
        conversation_id = _create_conversation(client)
        other = add_second_user(client, email="intruder@aurelis.dev")
        response = other.post(
            f"/api/v1/ai/conversations/{conversation_id}/messages/stream",
            json={"body": "hi"},
        )
        assert response.status_code == 404

    def test_unknown_conversation_is_404(self, client: TestClient) -> None:
        assert _stream(client, "c-does-not-exist", "hi").status_code == 404

    def test_arbitrary_model_is_rejected_before_streaming(self, client: TestClient) -> None:
        conversation_id = _create_conversation(client)
        response = _stream(
            client, conversation_id, "hi", model="some-unlisted-model"
        )
        # Rejected up front as a status code, not an in-band error frame.
        assert response.status_code == 503

    def test_unconfigured_provider_is_a_clean_503(self, client: TestClient, monkeypatch) -> None:
        monkeypatch.setattr(settings, "AI_PROVIDER", "openai")
        monkeypatch.setattr(settings, "AI_PROVIDER_API_KEY", "")
        conversation_id = _create_conversation(client)
        response = _stream(client, conversation_id, "hi")
        assert response.status_code == 503

    def test_rate_limit_is_enforced(self, client: TestClient, monkeypatch) -> None:
        from app.core import ratelimit

        monkeypatch.setitem(ratelimit._GENERAL_SCOPES, "ai", (1, 60))
        conversation_id = _create_conversation(client)
        assert _stream(client, conversation_id, "one").status_code == 200
        assert _stream(client, conversation_id, "two").status_code == 429

    def test_idempotent_retry_does_not_generate_twice(self, client: TestClient) -> None:
        conversation_id = _create_conversation(client)
        key = "idem-key-0001"
        first = _stream(client, conversation_id, "hello", idempotencyKey=key)
        second = _stream(client, conversation_id, "hello", idempotencyKey=key)

        first_meta = _parse_sse(first.text)[0][1]
        second_meta = _parse_sse(second.text)[0][1]
        assert second_meta["replayed"] is True
        assert second_meta["assistantMessage"]["id"] == first_meta["assistantMessage"]["id"]

        # Exactly one user and one assistant row were persisted.
        transcript = client.get(
            f"/api/v1/conversations/{conversation_id}/messages"
        ).json()
        assert transcript["total"] == 2


class TestStreamingPersistence:
    def test_user_and_assistant_messages_are_persisted(self, client: TestClient) -> None:
        conversation_id = _create_conversation(client)
        response = _stream(client, conversation_id, "Persist me")
        assert response.status_code == 200

        transcript = client.get(
            f"/api/v1/conversations/{conversation_id}/messages"
        ).json()
        roles = [item["role"] for item in transcript["items"]]
        assert roles == ["user", "assistant"]

        assistant = transcript["items"][1]
        assert assistant["status"] == "completed"
        assert assistant["provider"] == "simulator"

    def test_completed_message_carries_token_usage(self, client: TestClient) -> None:
        conversation_id = _create_conversation(client)
        _stream(client, conversation_id, "Token me")
        transcript = client.get(
            f"/api/v1/conversations/{conversation_id}/messages"
        ).json()
        assistant = transcript["items"][1]
        assert assistant["totalTokens"] is not None
        assert assistant["latencyMs"] is not None

    def test_failed_generation_is_not_stored_as_success(self, client: TestClient, monkeypatch) -> None:
        from app.ai.errors import ProviderUnavailableError as Unavailable

        def _boom(self, request):
            async def gen():
                raise Unavailable(internal_detail="scripted failure")
                yield  # pragma: no cover

            return gen()

        monkeypatch.setattr("app.ai.providers.simulator.SimulatorProvider.stream", _boom)
        conversation_id = _create_conversation(client)
        response = _stream(client, conversation_id, "Fail me")
        events = _parse_sse(response.text)
        names = [name for name, _ in events]
        assert "error" in names
        assert "done" not in names

        transcript = client.get(
            f"/api/v1/conversations/{conversation_id}/messages"
        ).json()
        assistant = transcript["items"][1]
        assert assistant["status"] == "failed"
        assert assistant["errorCode"] is not None

    def test_usage_row_is_recorded(self, client: TestClient) -> None:
        conversation_id = _create_conversation(client)
        _stream(client, conversation_id, "Usage please")
        usage = client.get("/api/v1/ai/usage").json()
        assert usage["totalRequests"] >= 1
        assert usage["completedRequests"] >= 1


# ── Security regressions ─────────────────────────────────────────────


class TestSecurityRegression:
    def test_provider_key_is_never_exposed_by_auth_me(
        self, client: TestClient, monkeypatch
    ) -> None:
        monkeypatch.setattr(settings, "AI_PROVIDER_API_KEY", "sk-should-never-leak")
        body = client.get("/api/v1/auth/me").json()
        assert "sk-should-never-leak" not in json.dumps(body)

    def test_capabilities_never_returns_the_key(self, client: TestClient, monkeypatch) -> None:
        monkeypatch.setattr(settings, "AI_PROVIDER_API_KEY", "sk-should-never-leak")
        body = client.get("/api/v1/ai/capabilities").text
        assert "sk-should-never-leak" not in body

    def test_stream_requires_csrf(self, db) -> None:
        # A fresh client with cookies but no CSRF header must be refused.
        with TestClient(__import__("app.main", fromlist=["app"]).app) as fresh:
            from tests.conftest import register_user

            register_user(fresh, email="csrf@aurelis.dev")
            fresh.headers.pop("X-CSRF-Token", None)
            response = fresh.post(
                "/api/v1/ai/conversations/c-anything/messages/stream",
                json={"body": "hi"},
            )
            assert response.status_code in (401, 403)

    def test_admin_cannot_read_a_private_conversation(self, client: TestClient, admin_client: TestClient) -> None:
        conversation_id = _create_conversation(client)
        # Admin access is not a blanket grant over another user's private thread.
        assert (
            admin_client.get(f"/api/v1/conversations/{conversation_id}").status_code
            == 404
        )


# ── Types sanity ─────────────────────────────────────────────────────


class TestOpenAICompatibleGateway:
    """The OpenAI protocol doubles as the interchange format for gateways."""

    def _request(self) -> GenerationRequest:
        return GenerationRequest(
            messages=[
                ChatMessage(role="system", content="sys"),
                ChatMessage(role="user", content="hi"),
            ],
            model="gateway-model",
            temperature=0.4,
            top_p=0.9,
            max_output_tokens=32,
            stream=False,
        )

    def test_payload_carries_roles_and_parameters(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "AI_PROVIDER_API_KEY", "sk-test-not-real")
        provider = OpenAIProvider()
        payload = provider._payload(self._request())
        # The system instruction stays a distinct role — never folded into the
        # user turn, which is what keeps a user message from acting as a system
        # instruction.
        assert [m["role"] for m in payload["messages"]] == ["system", "user"]
        assert payload["model"] == "gateway-model"
        assert payload["temperature"] == 0.4
        assert payload["top_p"] == 0.9
        assert payload["max_tokens"] == 32

    def test_base_url_override_is_used(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "AI_PROVIDER_API_KEY", "sk-test-not-real")
        monkeypatch.setattr(settings, "AI_BASE_URL", "https://example.invalid/v1")
        provider = OpenAIProvider()
        client = provider._get_client()
        assert str(client.base_url).startswith("https://example.invalid/v1")

    def test_compatible_gateway_response_is_parsed(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "AI_PROVIDER_API_KEY", "sk-test-not-real")
        provider = OpenAIProvider()

        class Message:
            content = "hello from the gateway"

        class Choice:
            message = Message()
            finish_reason = "stop"

        class Usage:
            prompt_tokens = 5
            completion_tokens = 7
            total_tokens = 12

        class Response:
            choices = [Choice()]
            model = "gateway-model"
            usage = Usage()

        class Client:
            class chat:  # noqa: N801 - mirrors the SDK's attribute path
                class completions:
                    @staticmethod
                    async def create(**_):
                        return Response()

        provider._client = Client()
        result = asyncio.run(provider.generate(self._request()))
        assert result.text == "hello from the gateway"
        assert result.usage.total_tokens == 12
        assert result.usage.input_tokens == 5

    def test_timeout_is_translated(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "AI_PROVIDER_API_KEY", "sk-test-not-real")

        class APITimeoutError(Exception):
            pass

        provider = OpenAIProvider()

        class Client:
            class chat:  # noqa: N801
                class completions:
                    @staticmethod
                    async def create(**_):
                        raise APITimeoutError("timed out")

        provider._client = Client()
        with pytest.raises(ProviderTimeoutError):
            asyncio.run(provider.generate(self._request()))

    def test_connection_error_is_translated(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "AI_PROVIDER_API_KEY", "sk-test-not-real")

        class APIConnectionError(Exception):
            pass

        provider = OpenAIProvider()

        class Client:
            class chat:  # noqa: N801
                class completions:
                    @staticmethod
                    async def create(**_):
                        raise APIConnectionError("no route to host")

        provider._client = Client()
        with pytest.raises(ProviderUnavailableError):
            asyncio.run(provider.generate(self._request()))


class TestClientDisconnect:
    """A dropped client must be recorded as cancelled, never as a success."""

    def test_disconnect_marks_the_turn_cancelled(self, client: TestClient, db: None) -> None:
        from sqlalchemy import select

        from app.ai.providers.simulator import SimulatorProvider
        from app.ai.types import StreamChunk
        from app.db.session import SessionLocal
        from app.models import Message, User
        from app.schemas.conversation import MessageCreate
        from app.services.conversations import ConversationService

        conversation_id = _create_conversation(client)

        with SessionLocal() as lookup:
            owner = lookup.scalar(
                select(User).where(User.email == "operator@aurelis.dev")
            )
            assert owner is not None
            owner_id = owner.id

        # A provider that emits one chunk and then stalls forever, so the
        # consumer is suspended inside the generator when we cancel it.
        def stalled_stream(self, request):
            async def gen():
                yield StreamChunk(text="partial ")
                await asyncio.sleep(3600)
                yield StreamChunk(finish_reason="stop")

            return gen()

        original = SimulatorProvider.stream
        SimulatorProvider.stream = stalled_stream
        try:

            async def scenario():
                with SessionLocal() as session:
                    service = ConversationService(session)

                    async def consume():
                        async for _frame in service.stream_message(
                            conversation_id,
                            MessageCreate(body="a long answer please"),
                            owner_id=owner_id,
                        ):
                            pass

                    task = asyncio.create_task(consume())
                    # Let the meta frame and first delta land, then simulate the
                    # browser going away — Starlette cancels the task on a
                    # disconnect, which is exactly what this reproduces.
                    await asyncio.sleep(0.1)
                    task.cancel()
                    with pytest.raises(asyncio.CancelledError):
                        await task

            asyncio.run(scenario())
        finally:
            SimulatorProvider.stream = original

        with SessionLocal() as verify:
            assistant = verify.scalar(
                select(Message)
                .where(
                    Message.conversation_id == conversation_id,
                    Message.role == "assistant",
                )
            )
            assert assistant is not None
            assert assistant.status == "cancelled"
            assert assistant.error_code == "stream_interrupted"
            # The partial text is preserved rather than discarded.
            assert assistant.blocks[0]["body"] == "partial "


class TestConfigEnvParsing:
    """List-valued settings arrive from the environment comma-separated.

    `pydantic-settings` JSON-decodes `list[str]` fields before validators run,
    so without `NoDecode` a documented `a,b` value fails at boot. These drive
    the real `EnvSettingsSource` rather than the init-kwarg shortcut.
    """

    def test_comma_separated_lists_parse(self, monkeypatch) -> None:
        from app.core.config import Settings

        monkeypatch.setenv("CORS_ORIGINS", "https://a.example, https://b.example")
        monkeypatch.setenv("AI_ALLOWED_MODELS", "gpt-4o-mini, gpt-4o")
        s = Settings()
        assert s.CORS_ORIGINS == ["https://a.example", "https://b.example"]
        assert s.AI_ALLOWED_MODELS == ["gpt-4o-mini", "gpt-4o"]

    def test_empty_allow_list_falls_back_to_default(self, monkeypatch) -> None:
        from app.core.config import Settings

        monkeypatch.setenv("AI_ALLOWED_MODELS", "")
        monkeypatch.setenv("AI_PROVIDER", "openai")
        monkeypatch.setenv("AI_PROVIDER_API_KEY", "sk-test-not-real")
        monkeypatch.setenv("AI_MODEL", "gpt-4o-mini")
        s = Settings()
        assert s.AI_ALLOWED_MODELS == []
        assert s.ai_allowed_models == ["gpt-4o-mini"]


class TestTokenUsageNormalisation:
    def test_total_is_filled_from_halves(self) -> None:
        usage = TokenUsage(input_tokens=3, output_tokens=4).normalised()
        assert usage.total_tokens == 7

    def test_absent_usage_stays_none(self) -> None:
        usage = TokenUsage().normalised()
        assert usage.total_tokens is None
        assert usage.input_tokens is None

    def test_password_constant_is_available(self) -> None:
        # Guard against the conftest import drifting.
        assert TEST_PASSWORD
