"""Transport-agnostic application errors and their HTTP handlers.

Domain and service layers raise these instead of `HTTPException` so the
business layer stays independent of the web framework. MODULE 5 extends the
handler with security-event logging rather than rewriting the services.
"""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)


class AppError(Exception):
    """Base class for expected, client-facing failures."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "app_error"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        self.headers = headers or {}


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


class InvalidRequestError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "validation_error"


class ServiceUnavailableError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "service_unavailable"


# ── Authentication and authorization (MODULE 4) ───────────────────────
#
# Kept distinct on purpose. `AuthenticationError` answers "who are you?" and
# carries a `WWW-Authenticate` challenge; `AuthorizationError` answers "you are
# known, but not allowed" and must never be used where the real problem is a
# missing credential — collapsing the two would tell a prober whether a token
# was absent or merely insufficient.


class AuthenticationError(AppError):
    """No valid credential was presented (or it has expired)."""

    status_code = status.HTTP_401_UNAUTHORIZED
    code = "authentication_error"

    def __init__(
        self,
        message: str = "Authentication required.",
        *,
        code: str | None = None,
        scheme: str = "Bearer",
        reason: str = "invalid_token",
    ) -> None:
        super().__init__(
            message,
            code=code,
            headers={"WWW-Authenticate": f'{scheme} error="{reason}"'},
        )
        self.reason = reason


class ExpiredAuthenticationError(AuthenticationError):
    """The credential was valid but its lifetime has ended.

    A distinct code lets the SPA attempt exactly one silent refresh before
    falling back to the login screen.
    """

    code = "session_expired"

    def __init__(self, message: str = "Your session has expired.") -> None:
        super().__init__(message, scheme="Bearer", reason="token_expired")


class AuthorizationError(AppError):
    """Authenticated, but not permitted to perform this action."""

    status_code = status.HTTP_403_FORBIDDEN
    code = "authorization_error"


class AccountInactiveError(AppError):
    """The account exists but is disabled; it must not hold a session."""

    status_code = status.HTTP_403_FORBIDDEN
    code = "account_inactive"


class EmailAlreadyRegisteredError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "email_already_registered"


class RateLimitedError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limited"

    def __init__(self, message: str, *, retry_after_seconds: int) -> None:
        super().__init__(
            message,
            headers={"Retry-After": str(max(1, retry_after_seconds))},
        )
        self.retry_after_seconds = retry_after_seconds


def _payload(code: str, message: str) -> dict[str, object]:
    return {"error": {"code": code, "message": message}}


def _serialisable_errors(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Strip non-JSON values from validation errors.

    Pydantic puts the original exception object in `ctx`, which the JSON
    encoder cannot handle — stringify just that field and pass the rest through.
    """
    cleaned: list[dict[str, Any]] = []
    for error in errors:
        item = {key: value for key, value in error.items() if key != "ctx"}
        ctx = error.get("ctx")
        if ctx:
            item["ctx"] = {key: str(value) for key, value in ctx.items()}
        cleaned.append(item)
    return cleaned


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_payload(exc.code, exc.message),
            headers=exc.headers or None,
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Request payload failed validation.",
                    "details": _serialisable_errors(exc.errors()),
                }
            },
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        # Never leak internals to the client; log the detail server-side.
        logger.exception("Unhandled error: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_payload("internal_error", "An unexpected error occurred."),
        )
