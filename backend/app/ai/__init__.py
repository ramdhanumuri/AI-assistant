"""Provider-independent AI layer.

The application talks to `AIProvider` and to `AIOrchestrator`; it never imports
a vendor SDK, and no provider sees a database model or a FastAPI request. The
layout mirrors that boundary:

    types.py        value objects that cross the provider boundary
    errors.py       the closed error vocabulary (code + retryability)
    base.py         the AIProvider interface and the retry policy
    prompts.py      every system instruction, in one place
    context.py      context-window construction and the token budget
    usage.py        cost foundation (only from configured pricing)
    factory.py      AI_PROVIDER → implementation
    orchestrator.py context → model selection → provider → stream → usage
    providers/      one adapter per vendor

STEP 6 ships two implementations behind the interface: the deterministic
`simulator` (offline; tests and local development) and `openai` (the real,
provider-backed model).
"""

from app.ai.base import AIProvider, with_retries
from app.ai.errors import (
    AIError,
    ConfigurationError,
    ContextTooLargeError,
    InvalidProviderResponseError,
    ProviderAuthenticationError,
    ProviderRateLimitedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    StreamInterruptedError,
)
from app.ai.factory import get_provider, list_providers, reset_providers
from app.ai.orchestrator import AIOrchestrator, OrchestrationResult, StreamEvent
from app.ai.types import (
    ChatMessage,
    GenerationRequest,
    GenerationResult,
    GenerationStatus,
    StreamChunk,
    TokenUsage,
)

__all__ = [
    "AIError",
    "AIOrchestrator",
    "AIProvider",
    "ChatMessage",
    "ConfigurationError",
    "ContextTooLargeError",
    "GenerationRequest",
    "GenerationResult",
    "GenerationStatus",
    "InvalidProviderResponseError",
    "OrchestrationResult",
    "ProviderAuthenticationError",
    "ProviderRateLimitedError",
    "ProviderTimeoutError",
    "ProviderUnavailableError",
    "StreamChunk",
    "StreamEvent",
    "StreamInterruptedError",
    "TokenUsage",
    "get_provider",
    "list_providers",
    "reset_providers",
    "with_retries",
]
