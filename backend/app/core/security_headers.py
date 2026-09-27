"""Security response headers.

The API serves JSON and the interactive docs; the SPA is served by its own
static host, so the policy here never has to allow the bundler's runtime. That
lets the app policy be genuinely restrictive rather than the "CSP that cannot
break the UI" compromise MODULE 4 shipped.

Two things stay deliberately scoped:

* **`/docs` and `/redoc` get a looser policy.** Swagger UI and ReDoc load
  bundles from a CDN and evaluate their own templates, so they need
  `cdn.jsdelivr.net` and `'unsafe-inline'`. Scoped to those paths only.
* **HSTS only over HTTPS.** Sending `Strict-Transport-Security` over plain HTTP
  in development would pin the developer's browser to HTTPS for `localhost`.
  Outside development the header is always sent; the max-age is configurable.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings

# The API returns JSON. A tight policy costs nothing here and means a
# successful content-type confusion cannot turn an API response into a script
# execution. `frame-ancestors 'none'` supersedes X-Frame-Options for modern
# browsers; X-Frame-Options is sent too for older ones.
BASE_CSP = (
    "default-src 'none'; "
    "script-src 'none'; "
    "style-src 'none'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'none'; "
    "form-action 'none'; "
    "frame-ancestors 'none'"
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

# Auth responses set cookies; they must never land in a shared cache.
_NO_STORE_PREFIXES = ("/api/v1/auth",)


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
            "geolocation=(), microphone=(self), camera=(), payment=(), usb=()",
        )
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")

        if request.url.path.startswith(_DOCS_PATHS):
            response.headers.setdefault("Content-Security-Policy", DOCS_CSP)
        else:
            response.headers.setdefault("Content-Security-Policy", BASE_CSP)

        if request.url.path.startswith(_NO_STORE_PREFIXES):
            response.headers.setdefault("Cache-Control", "no-store")
            response.headers.setdefault("Pragma", "no-cache")

        if settings.is_cookie_secure:
            # Only over HTTPS; see the module docstring.
            response.headers.setdefault(
                "Strict-Transport-Security",
                f"max-age={settings.HSTS_MAX_AGE_SECONDS}; includeSubDomains",
            )

        return response


__all__ = ["BASE_CSP", "DOCS_CSP", "SecurityHeadersMiddleware"]
