"""Standardised AI-layer errors.

A provider adapter raises one of these; nothing above the AI layer ever sees a
vendor exception, a raw HTTP status or a stack trace. Each error carries:

* a stable `code` from a closed vocabulary, which is what the API returns and
  what the usage row records, and
* a `retryable` flag, which is the single source of truth for whether the
  retry policy may try again. Putting that decision on the error rather than
  at the call site is deliberate: "should this be retried?" is a property of
  the failure, and a caller that has to remember the rule will eventually get
  it wrong.

The messages here are safe to show a user. The provider's own text is kept in
`internal_detail` for the server log and is never serialised into a response.
"""

from __future__ import annotations

# The complete vocabulary. Exported so a test can assert nothing raises a code
# outside it — a typo would otherwise create an error the client cannot handle.
ERROR_CODES = frozenset(
    {
        "provider_unavailable",
        "provider_timeout",
        "invalid_provider_response",
        "authentication_error",
        "rate_limited",
        "context_too_large",
        "configuration_error",
        "stream_interrupted",
    }
)


class AIError(Exception):
    """Base class for every AI-layer failure."""

    code: str = "provider_unavailable"
    # Conservative default: an unrecognised failure is not retried. Retrying
    # something that is actually permanent is how a retry storm starts.
    retryable: bool = False
    user_message: str = "The assistant is temporarily unavailable. Please try again."

    def __init__(
        self,
        message: str | None = None,
        *,
        internal_detail: str | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message or self.user_message)
        self.message = message or self.user_message
        # Provider-authored text. Logged server-side, never returned.
        self.internal_detail = internal_detail
        # The upstream HTTP status, when there was one. Used by the retry
        # policy and recorded in the log; never returned to the client.
        self.status_code = status_code


class ConfigurationError(AIError):
    """The provider is not usable as configured (e.g. a missing API key).

    Permanent by definition: no number of retries fixes a missing credential.
    """

    code = "configuration_error"
    retryable = False
    user_message = (
        "The AI service is not configured. Please contact an administrator."
    )


class ProviderAuthenticationError(AIError):
    """The provider rejected our credentials.

    Distinct from a *user* authentication failure. Retrying is pointless and
    can itself trigger an account lockout at the provider, so it is never
    retried.
    """

    code = "authentication_error"
    retryable = False
    user_message = (
        "The AI service could not be authenticated. Please contact an administrator."
    )


class ProviderRateLimitedError(AIError):
    """The provider throttled us. Transient — worth one bounded retry."""

    code = "rate_limited"
    retryable = True
    user_message = "The AI service is busy. Please try again in a moment."

    def __init__(
        self,
        message: str | None = None,
        *,
        internal_detail: str | None = None,
        retry_after_seconds: float | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(
            message, internal_detail=internal_detail, status_code=status_code or 429
        )
        self.retry_after_seconds = retry_after_seconds


class ProviderTimeoutError(AIError):
    """The provider did not answer inside `AI_TIMEOUT_SECONDS`."""

    code = "provider_timeout"
    retryable = True
    user_message = "The AI service took too long to respond. Please try again."


class ProviderUnavailableError(AIError):
    """A transport failure or a provider 5xx. Transient."""

    code = "provider_unavailable"
    retryable = True
    user_message = "The assistant is temporarily unavailable. Please try again."


class InvalidProviderResponseError(AIError):
    """The provider answered, but not in a shape we can use.

    Not retried: a malformed response usually means a protocol or model
    mismatch, and repeating the request would produce the same malformed
    answer.
    """

    code = "invalid_provider_response"
    retryable = False
    user_message = "The assistant returned an unusable response. Please try again."


class ContextTooLargeError(AIError):
    """The assembled prompt exceeds `AI_MAX_INPUT_TOKENS`.

    Not retried — the same conversation would exceed the budget again.
    """

    code = "context_too_large"
    retryable = False
    user_message = (
        "This conversation has grown too large to send. Start a new thread "
        "or remove some earlier messages."
    )


class StreamInterruptedError(AIError):
    """The stream ended before the provider signalled completion."""

    code = "stream_interrupted"
    retryable = False
    user_message = "The response was interrupted before it finished."


__all__ = [
    "AIError",
    "ConfigurationError",
    "ContextTooLargeError",
    "ERROR_CODES",
    "InvalidProviderResponseError",
    "ProviderAuthenticationError",
    "ProviderRateLimitedError",
    "ProviderTimeoutError",
    "ProviderUnavailableError",
    "StreamInterruptedError",
]
