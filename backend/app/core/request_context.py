"""Per-request correlation and transport guards.

Two concerns that both have to happen before routing but must not reject a
legitimate request:

* **Request ids.** Every response carries an `X-Request-ID` so a client-side
  error report can be matched to a server log line. A client may *suggest* an
  id (that is what distributed tracing does) but a suggested value is
  untrusted, so it is only echoed when it is short and matches a conservative
  charset. Otherwise a server-generated id is used. The id is stored in a
  `ContextVar` so the exception handlers — which run outside the middleware's
  own frame — can include it in the log line for the same request.
* **Body size.** A `Content-Length` over the ceiling is refused before the body
  is read, so a huge or dishonest payload cannot be buffered into memory. A
  chunked request with no `Content-Length` is re-checked as it streams.

The id travels in a header, never a URL, so it cannot end up in a Referer or an
access log's path field the way a query parameter would.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings

REQUEST_ID_HEADER = "X-Request-ID"

# A client-supplied id is echoed only inside these bounds. Anything longer is
# a log-injection / memory vector; anything with other characters might forge a
# structured-log field.
_MAX_CLIENT_REQUEST_ID = 128
_ALLOWED_REQUEST_ID_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_."
)

_current_request_id: ContextVar[str | None] = ContextVar(
    "aurelis_request_id", default=None
)

_BODY_TOO_LARGE_BODY = {
    "error": {
        "code": "payload_too_large",
        "message": "The request payload is too large.",
    }
}


def _body_too_large(request_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=413,
        content=_BODY_TOO_LARGE_BODY,
        headers={REQUEST_ID_HEADER: request_id},
    )


def current_request_id() -> str | None:
    """The id of the request being handled, if it is still in scope."""
    return _current_request_id.get()


def _sanitise_client_id(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    if not value or len(value) > _MAX_CLIENT_REQUEST_ID:
        return None
    if not set(value) <= _ALLOWED_REQUEST_ID_CHARS:
        return None
    return value


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = _sanitise_client_id(request.headers.get(REQUEST_ID_HEADER))
        if request_id is None:
            request_id = uuid.uuid4().hex

        # Also exposed on `request.state` for handlers that build their own log
        # lines (e.g. the security-event recorder).
        request.state.request_id = request_id
        token = _current_request_id.set(request_id)
        try:
            too_large = self._declared_content_length_too_large(request)
            if too_large:
                return _body_too_large(request_id)

            response = await call_next(request)
            if self._streamed_body_too_large(request):
                return _body_too_large(request_id)
            response.headers.setdefault(REQUEST_ID_HEADER, request_id)
            return response
        finally:
            _current_request_id.reset(token)

    @staticmethod
    def _declared_content_length_too_large(request: Request) -> bool:
        raw = request.headers.get("content-length")
        if not raw:
            return False
        try:
            length = int(raw)
        except ValueError:
            return False
        return length > settings.MAX_REQUEST_BODY_BYTES

    @staticmethod
    def _streamed_body_too_large(request: Request) -> bool:
        """Catch a chunked upload that declared no length.

        Completed requests expose the buffered body; an oversized one would
        already have been read by the time we get here, so this is a belt-and-
        braces check for the case where a length was absent but the framework
        still buffered the body (Starlette caches `request._body`).
        """
        body = getattr(request, "_body", None)
        return isinstance(body, (bytes, bytearray)) and len(body) > settings.MAX_REQUEST_BODY_BYTES


__all__ = [
    "REQUEST_ID_HEADER",
    "RequestContextMiddleware",
    "current_request_id",
]
