"""Structured security-event logging.

Not every security event has a database session available — a CSRF failure or a
throttled request is rejected in middleware/dependency land, before a service
exists. Those still need to be visible, so they are emitted as a single
structured log line. Events that *do* run inside a service are additionally
persisted by `AuthService.record_event`, which is what the admin feed reads.

Both paths share one vocabulary (`app.models.user.EVENT_TYPES`) and one rule:
the fields here are the safe, non-identifying shape the future Admin Security
Dashboard will consume — `event_type`, `outcome`, a keyed `subject` digest,
request id and coarse client metadata. Passwords, raw tokens, reset links, IP
addresses and request bodies never appear.
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.core.request_context import current_request_id

logger = get_logger("security")

# Characters allowed in a free-text detail before it is logged. Anything else
# is dropped so a crafted detail cannot forge a newline + structured field
# (log injection) or smuggle a token into the line.
_MAX_DETAIL_LENGTH = 200


def _safe_detail(detail: str | None) -> str | None:
    if not detail:
        return None
    cleaned = " ".join(str(detail).split())
    return cleaned[:_MAX_DETAIL_LENGTH] or None


def log_security_event(
    event_type: str,
    *,
    outcome: str = "success",
    subject: str | None = None,
    detail: str | None = None,
    ip_hash: str | None = None,
) -> None:
    """Emit one structured security event.

    `subject` is expected to be an already-hashed identifier (see
    `app.core.security.hash_identifier`), never an email or an address.
    """
    parts = [f"security_event={event_type}", f"outcome={outcome}"]
    if subject:
        parts.append(f"subject={subject}")
    if ip_hash:
        parts.append(f"ip_hash={ip_hash}")
    request_id = current_request_id()
    if request_id:
        parts.append(f"request_id={request_id}")
    safe_detail = _safe_detail(detail)
    if safe_detail:
        parts.append(f"detail={safe_detail}")

    line = " | ".join(parts)
    if outcome == "success":
        logger.info(line)
    else:
        logger.warning(line)


__all__ = ["log_security_event"]
