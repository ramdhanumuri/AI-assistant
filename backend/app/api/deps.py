"""Shared route dependencies and response helpers.

MODULE 4 adds the identity seam: `CurrentUser` is what every protected route
depends on, and `AdminUser` layers authorization on top of it. Both resolve the
account from the database on every request, so a role change, a disabled
account or a revoked session takes effect on the next call rather than whenever
a token happens to expire.
"""

from dataclasses import dataclass
from typing import Annotated, TypeVar

from fastapi import Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.errors import (
    AccountInactiveError,
    AuthenticationError,
    AuthorizationError,
    ExpiredAuthenticationError,
    RateLimitedError,
)
from app.core.logging import get_logger
from app.core.ratelimit import get_limiter
from app.core.security import AccessTokenError, decode_access_token
from app.db.session import get_db
from app.models import ROLE_ADMIN, User
from app.api.cookies import read_access_token
from app.services.auth import AuthService, ClientContext
from app.services.catalog import CatalogService
from app.services.conversations import ConversationService

logger = get_logger(__name__)

DbSession = Annotated[Session, Depends(get_db)]

T = TypeVar("T")


class LimitOffset:
    """Reusable pagination query parameters."""

    def __init__(
        self,
        limit: Annotated[int, Query(ge=1, le=200, description="Page size.")] = 50,
        offset: Annotated[int, Query(ge=0, description="Rows to skip.")] = 0,
    ) -> None:
        self.limit = limit
        self.offset = offset


Pagination = Annotated[LimitOffset, Depends()]


def get_conversation_service(db: DbSession) -> ConversationService:
    return ConversationService(db)


def get_catalog_service(db: DbSession) -> CatalogService:
    return CatalogService(db)


def get_auth_service(db: DbSession) -> AuthService:
    return AuthService(db)


ConversationServiceDep = Annotated[ConversationService, Depends(get_conversation_service)]
CatalogServiceDep = Annotated[CatalogService, Depends(get_catalog_service)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


@dataclass(frozen=True)
class Identity:
    """The authenticated principal for one request.

    Carries the ORM user plus the session id the access token was minted for,
    so logout and password change can act on exactly that session.
    """

    user: User
    session_id: str

    @property
    def id(self) -> str:
        return self.user.id

    @property
    def role(self) -> str:
        return self.user.role

    @property
    def is_admin(self) -> bool:
        return self.user.role == ROLE_ADMIN


def client_context(request: Request) -> ClientContext:
    """Non-identifying request metadata, for the audit trail and sessions.

    The address comes from `request.client` rather than `X-Forwarded-For`: a
    client-supplied header is trivially spoofed, and trusting it would let an
    attacker forge the address recorded against their own failed logins. Behind
    a proxy, configure the proxy to set `request.client` (uvicorn's
    `--proxy-headers`) rather than reading the header here.
    """
    address = request.client.host if request.client else None
    return ClientContext(
        user_agent=request.headers.get("user-agent"),
        ip_address=address,
    )


ClientContextDep = Annotated[ClientContext, Depends(client_context)]


def rate_limit(request: Request, *, scope: str) -> None:
    """Apply the authentication throttle to the caller's address.

    Raises `RateLimitedError` (429 + `Retry-After`) when the window is full.
    """
    context = client_context(request)
    key = f"{scope}:{context.ip_hash or 'unknown'}"
    result = get_limiter().check(key)
    if not result.allowed:
        logger.warning("Authentication rate limit hit for scope=%s", scope)
        raise RateLimitedError(
            "Too many attempts. Please wait and try again.",
            retry_after_seconds=result.retry_after_seconds,
        )


def require_authenticated_user(
    request: Request,
    db: DbSession,
    auth: AuthServiceDep,
) -> Identity:
    """Resolve the caller, or raise 401.

    Four things are checked, in order, because each failure means something
    different to the client:

    1. a token was presented at all,
    2. it is signed by us and unexpired,
    3. the session it names still exists and is not revoked,
    4. the account behind it still exists and is active.
    """
    token = read_access_token(request)
    if not token:
        raise AuthenticationError("Authentication required.")

    try:
        claims = decode_access_token(token)
    except AccessTokenError as exc:
        if exc.expired:
            raise ExpiredAuthenticationError() from exc
        raise AuthenticationError("Your session is no longer valid.") from exc

    user_id = str(claims["sub"])
    session_id = str(claims["sid"])

    auth_session = auth.get_session(session_id)
    if auth_session is None or auth_session.revoked_at is not None:
        # Signed and unexpired, but the session was ended — logout, password
        # change or "sign out everywhere". This is why the session id is in the
        # token: a stateless JWT alone could not be revoked.
        raise AuthenticationError("Your session is no longer valid.")

    if auth_session.user_id != user_id:
        raise AuthenticationError("Your session is no longer valid.")

    user = auth.get_user(user_id)
    if user is None:
        raise AuthenticationError("Your session is no longer valid.")
    if not user.is_active:
        raise AccountInactiveError("This account has been disabled.")

    return Identity(user=user, session_id=session_id)


CurrentUser = Annotated[Identity, Depends(require_authenticated_user)]


def require_admin(identity: CurrentUser) -> Identity:
    """Authorization on top of authentication.

    The role is read from the stored row resolved by
    `require_authenticated_user` — never from the token, a header, or the
    request body. A client cannot assert its way into this dependency.
    """
    if not identity.is_admin:
        logger.warning("Admin authorization denied for user=%s", identity.user.id)
        raise AuthorizationError("You do not have permission to access this resource.")
    return identity


AdminUser = Annotated[Identity, Depends(require_admin)]


def page(items: list[T], total: int, pagination: LimitOffset) -> dict[str, object]:
    return {
        "items": items,
        "total": total,
        "limit": pagination.limit,
        "offset": pagination.offset,
    }


__all__ = [
    "AdminUser",
    "AuthServiceDep",
    "CatalogServiceDep",
    "ClientContext",
    "ClientContextDep",
    "ConversationServiceDep",
    "CurrentUser",
    "DbSession",
    "Identity",
    "LimitOffset",
    "Pagination",
    "client_context",
    "page",
    "rate_limit",
    "require_admin",
    "require_authenticated_user",
]