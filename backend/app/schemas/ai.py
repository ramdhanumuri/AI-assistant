"""AI-layer wire models.

Two audiences:

* `AICapabilities` is what the chat UI reads to decide whether to use the
  streaming transport and which model to label a response with. It reports
  *whether* the provider is configured, never the credential or the base URL.
* `AIUsageSummary` is the usage/cost surface, for the signed-in user's own
  account and (aggregated) for administrators. It never carries message content.

Field names follow the same camelCase convention as the rest of the API.
"""

from __future__ import annotations

from pydantic import Field

from app.schemas.common import APIModel


class AIModelInfo(APIModel):
    id: str
    default: bool = False


class AICapabilities(APIModel):
    """What the AI layer can do for this deployment.

    `configured` is false when a real provider is selected but has no
    credentials. The UI uses it to disable sending with an honest explanation,
    instead of letting a request fail at the provider.
    """

    provider: str
    model: str
    streaming_enabled: bool
    configured: bool
    models: list[AIModelInfo] = Field(default_factory=list)


class AIUsageSummary(APIModel):
    """Aggregated model usage over a window.

    Token and cost totals are nullable: `None` means "no provider reported a
    value in this window", which is not the same as zero and must not be
    rendered as a spend of nothing.
    """

    total_requests: int
    completed_requests: int
    failed_requests: int
    cancelled_requests: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    average_latency_ms: int | None = None
    estimated_cost: float | None = None
    currency: str | None = None
    window_days: int | None = None


__all__ = ["AICapabilities", "AIModelInfo", "AIUsageSummary"]
