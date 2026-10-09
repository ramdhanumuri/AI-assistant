"""AI service — capabilities and usage reporting.

Two read-only concerns that sit beside `ConversationService`:

* capabilities, so the UI can decide whether to use the streaming transport and
  what to label a response with, and
* usage, which is per-account for the signed-in user and platform-wide for an
  administrator.

Neither ever touches message content, and neither returns a provider credential.
`configured` reports only *whether* the provider has what it needs.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from app.ai.factory import get_provider, list_providers
from app.core.config import settings
from app.core.logging import get_logger
from app.db.base import utcnow
from app.schemas.ai import AICapabilities, AIModelInfo, AIUsageSummary
from app.services.repositories import AIUsageRepository

logger = get_logger(__name__)


class AIService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.usage = AIUsageRepository(session)

    def capabilities(self) -> AICapabilities:
        """Describe what the AI layer can do, without revealing any secret.

        The provider's health is checked without a billable call, so this is
        cheap enough to serve on every chat open.
        """
        provider_name = settings.AI_PROVIDER.strip().lower()
        model = settings.ai_model_resolved or ("simulator" if provider_name in {"simulator", "local"} else "")
        allowed = settings.ai_allowed_models
        return AICapabilities(
            provider=provider_name,
            model=model,
            streaming_enabled=bool(settings.AI_STREAMING_ENABLED),
            configured=settings.ai_configured,
            models=[
                AIModelInfo(id=name, default=(name == model)) for name in allowed
            ],
        )

    def available_providers(self) -> list[str]:
        return list_providers()

    def usage_summary(self, *, user_id: str | None, window_days: int | None = None) -> AIUsageSummary:
        """Aggregate usage, scoped to a user when one is given.

        `window_days=None` means "all time". Passing a user id is what makes the
        self-service endpoint owner-scoped: an administrator calling it for
        their own account sees only their own spend.
        """
        since = None if window_days is None else utcnow() - timedelta(days=window_days)
        data = self.usage.summary(user_id=user_id, since=since)
        return AIUsageSummary(
            **data,
            currency=settings.AI_COST_CURRENCY if data.get("estimated_cost") is not None else None,
            window_days=window_days,
        )

    def provider_health(self) -> str:
        """A coarse, safe health string for the admin system-health view."""
        try:
            provider = get_provider()
        except Exception:  # noqa: BLE001 - reported, never raised to the caller
            return "misconfigured"
        return "configured" if settings.ai_configured else "unconfigured"


__all__ = ["AIService"]
