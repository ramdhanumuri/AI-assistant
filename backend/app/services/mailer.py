"""Outbound email seam.

There is no provider wired up in this module. Rather than pretending otherwise,
`send_password_reset` reports that it did not deliver, and the caller surfaces
that in the API response so an operator is never told an email went out when it
did not.

Wiring a provider means implementing one function and setting `MAIL_PROVIDER`;
nothing else in the reset flow changes.
"""

from __future__ import annotations

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Deliberately empty: a real integration sets this to e.g. "smtp" or "resend".
MAIL_PROVIDER = ""


def is_configured() -> bool:
    return bool(MAIL_PROVIDER)


def send_password_reset(*, to_email: str, reset_url: str, expires_minutes: int) -> bool:
    """Attempt to deliver a reset link. Returns whether delivery happened.

    The token and the URL are never logged — a reset link in a log file is a
    working credential for anyone who can read the log.
    """
    if not is_configured():
        logger.info(
            "Password reset requested but no mail provider is configured "
            "(provider=%s, env=%s); token recorded, nothing delivered.",
            MAIL_PROVIDER or "none",
            settings.APP_ENV,
        )
        return False

    # A provider implementation goes here. Left unimplemented on purpose so it
    # cannot silently succeed without a real transport behind it.
    logger.warning("MAIL_PROVIDER is set to %r but no sender is implemented.", MAIL_PROVIDER)
    return False


__all__ = ["MAIL_PROVIDER", "is_configured", "send_password_reset"]
