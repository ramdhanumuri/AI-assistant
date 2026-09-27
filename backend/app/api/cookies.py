"""Cookie transport and CSRF defence.

Tokens live in HttpOnly cookies, so JavaScript cannot read them and an XSS bug
cannot exfiltrate a session. That choice creates the mirror-image risk: a
browser attaches cookies automatically, so a cross-site request would be
authenticated. The mitigation here is the standard double-submit pattern.

* `aurelis_session` / `aurelis_refresh` — HttpOnly, so unreadable from JS.
* `aurelis_csrf` — **readable** by design. The SPA echoes its value in the
  `X-CSRF-Token` header on state-changing requests. A cross-site form post can
  send the cookie but cannot set a custom header, so the two cannot match.

`SameSite=Lax` already blocks most cross-site writes; the double-submit is what
covers the deployments that need `SameSite=None`.
"""

from __future__ import annotations

import secrets

from fastapi import Request, Response

from app.core.config import settings
from app.core.errors import AuthorizationError
from app.core.logging import get_logger
from app.core.security_events import log_security_event
from app.models import EVENT_CSRF_FAILURE

logger = get_logger(__name__)

# Methods a browser can issue cross-site without a preflight, and that change
# state. GET/HEAD/OPTIONS are safe and stay exempt.
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

CSRF_TOKEN_BYTES = 32


def _cookie_common() -> dict[str, object]:
    common: dict[str, object] = {
        "secure": settings.is_cookie_secure,
        "samesite": settings.cookie_samesite,
        "path": "/",
    }
    if settings.COOKIE_DOMAIN:
        common["domain"] = settings.COOKIE_DOMAIN
    return common


def new_csrf_token() -> str:
    return secrets.token_urlsafe(CSRF_TOKEN_BYTES)


def set_auth_cookies(
    response: Response,
    *,
    access_token: str,
    access_max_age: int,
    refresh_token: str,
    refresh_max_age: int,
    csrf_token: str,
) -> None:
    """Attach the session, refresh and CSRF cookies to a response.

    `max_age` is passed in rather than derived from an expiry datetime: it
    should track the token's real lifetime exactly, so the browser drops the
    cookie at the same moment the server stops accepting it.
    """
    common = _cookie_common()

    response.set_cookie(
        settings.AUTH_COOKIE_NAME,
        access_token,
        max_age=max(0, access_max_age),
        httponly=True,
        **common,  # type: ignore[arg-type]
    )
    response.set_cookie(
        settings.REFRESH_COOKIE_NAME,
        refresh_token,
        max_age=max(0, refresh_max_age),
        httponly=True,
        **common,  # type: ignore[arg-type]
    )
    # Not HttpOnly: the SPA has to read it to echo it back as a header.
    response.set_cookie(
        settings.CSRF_COOKIE_NAME,
        csrf_token,
        max_age=max(0, refresh_max_age),
        httponly=False,
        **common,  # type: ignore[arg-type]
    )


def clear_auth_cookies(response: Response) -> None:
    """Expire all three cookies. Used on logout and on a failed refresh.

    `delete_cookie` sets `path` and `samesite` itself, so only the domain is
    forwarded here; passing `path` as well would be a duplicate keyword.
    """
    common: dict[str, object] = {"samesite": settings.cookie_samesite}
    if settings.COOKIE_DOMAIN:
        common["domain"] = settings.COOKIE_DOMAIN

    for name in (
        settings.AUTH_COOKIE_NAME,
        settings.REFRESH_COOKIE_NAME,
        settings.CSRF_COOKIE_NAME,
    ):
        response.delete_cookie(name, path="/", **common)  # type: ignore[arg-type]


def read_access_token(request: Request) -> str | None:
    """Prefer the cookie; fall back to a bearer header for API clients."""
    cookie = request.cookies.get(settings.AUTH_COOKIE_NAME)
    if cookie:
        return cookie

    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip() or None
    return None


def read_refresh_token(request: Request) -> str | None:
    return request.cookies.get(settings.REFRESH_COOKIE_NAME)


def read_csrf_cookie(request: Request) -> str | None:
    return request.cookies.get(settings.CSRF_COOKIE_NAME)


def read_csrf_header(request: Request) -> str | None:
    return request.headers.get(settings.CSRF_HEADER_NAME)


def enforce_csrf(request: Request) -> None:
    """Reject a state-changing request that did not prove it can read the cookie.

    Only applies when the request is cookie-authenticated. A bearer-token
    client (no cookies) is not vulnerable to CSRF at all, because nothing
    attaches its credential automatically.

    Failure is deliberately uniform: an absent token and a mismatched token
    produce the same 403 with the same message, so a cross-site attacker learns
    nothing about whether the session exists. The rejection never echoes the
    presented token.
    """
    if request.method not in UNSAFE_METHODS:
        return

    cookie_token = read_csrf_cookie(request)
    has_session_cookie = (
        request.cookies.get(settings.AUTH_COOKIE_NAME)
        or request.cookies.get(settings.REFRESH_COOKIE_NAME)
    )
    if not has_session_cookie:
        return

    header_token = read_csrf_header(request)
    if not cookie_token or not header_token:
        _reject(request, reason="missing_token")
    if not secrets.compare_digest(cookie_token, header_token):
        _reject(request, reason="token_mismatch")


def _reject(request: Request, *, reason: str) -> None:
    log_security_event(
        EVENT_CSRF_FAILURE,
        outcome="denied",
        detail=f"{reason} on {request.method} {request.url.path}",
    )
    raise AuthorizationError("Request could not be verified. Reload and try again.")


__all__ = [
    "UNSAFE_METHODS",
    "clear_auth_cookies",
    "enforce_csrf",
    "new_csrf_token",
    "read_access_token",
    "read_csrf_cookie",
    "read_csrf_header",
    "read_refresh_token",
    "set_auth_cookies",
]
