"""Security response headers.

The foundation the brief asks for, not the finished policy. Two deliberate
restrictions on scope:

* **A CSP that cannot break the UI.** The frontend is a Vite SPA that loads
  Google Fonts and injects styles at runtime, so a strict `script-src 'self'`
  policy would need per-build nonces to work. The policy below therefore
  restricts `frame-ancestors`, `object-src`, `base-uri` and `form-action` —
  the directives that matter for clickjacking and injection — and leaves
  `script-src`/`style-src` to Step 5, where a nonce can be threaded through
  the build. A CSP that breaks the app is worse than one that is incomplete.
* **No HSTS in development.** Sending `Strict-Transport-Security` over plain
  HTTP in dev would pin the developer's browser to HTTPS for `localhost`.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings

# Conservative baseline. `frame-ancestors 'none'` supersedes X-Frame-Options
# for modern browsers; X-Frame-Options is sent too for older ones.
BASE_CSP = (
    "default-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'; "
    "form-action 'self'; "
    "img-src 'self' data: blob: https:; "
    "font-src 'self' data: https://fonts.gstatic.com; "
    "connect-src 'self' https:; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "script-src 'self' 'unsafe-inline'"
)

# Swagger UI and ReDoc load their bundles from a CDN and eval their own
# templates, so the API docs need a looser policy than the app. Scoped to the
# docs paths only.
DOCS_CSP = (
    "default-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'; "
    "img-src 'self' data: https://fastapi.tiangolo.com; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "connect-src 'self'"
)

_DOCS_PATHS = ("/docs", "/redoc")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach the security headers to every response.

    Runs as pure response decoration: it never rejects a request, so it cannot
    be the reason a legitimate call fails.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)

        # Never let a browser guess a content type — that is how an uploaded
        # file becomes an executed script.
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(self), camera=(), payment=()",
        )
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")

        if request.url.path.startswith(_DOCS_PATHS):
            response.headers.setdefault("Content-Security-Policy", DOCS_CSP)
        else:
            response.headers.setdefault("Content-Security-Policy", BASE_CSP)

        if settings.is_cookie_secure:
            # Only over HTTPS; see the module docstring.
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )

        return response


__all__ = ["BASE_CSP", "DOCS_CSP", "SecurityHeadersMiddleware"]
