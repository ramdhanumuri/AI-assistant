"""Authentication endpoints.

Registration, login, logout, session refresh, the current-user endpoint, the
password lifecycle and the session list. Every response body is built from
`UserRead`, so a password hash has no path to the wire.

Cookie handling lives here rather than in the service because it is a transport
concern: the service deals in tokens, the route decides where they are put.
"""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Request, Response, status
from sqlalchemy import select

from app.api.cookies import (
    clear_auth_cookies,
    enforce_csrf,
    new_csrf_token,
    read_access_token,
    read_refresh_token,
    set_auth_cookies,
)
from app.api.deps import (
    AuthServiceDep,
    ClientContextDep,
    CurrentUser,
    rate_limit,
)
from app.core.config import settings
from app.core.errors import AuthenticationError
from app.core.logging import get_logger
from app.core.security import AccessTokenError, decode_access_token, hash_token
from app.db.base import utcnow
from app.models import EVENT_LOGOUT, AuthSession, User
from app.schemas.auth import (
    AuthSessionRead,
    AuthState,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    MessageResponse,
    PreferencesRead,
    PreferencesUpdate,
    ProfileUpdate,
    RegisterRequest,
    ResetPasswordRequest,
    UserRead,
)
from app.services import mailer
from app.services.auth import AuthService, ClientContext, IssuedSession

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Scope keys for the throttle, so login and reset have independent budgets.
SCOPE_REGISTER = "register"
SCOPE_LOGIN = "login"
SCOPE_RESET = "password-reset"

# Frontend route that receives a reset token. The token is placed in the URL
# *fragment* by the client, which is never sent to a server, and never logged
# by the API.
RESET_PATH = "/reset-password"


def _user_read(user: User) -> UserRead:
    return UserRead(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        avatar_url=user.avatar_url,
        email_verified=user.email_verified,
        created_at=user.created_at,
    )


def _attach_session(
    response: Response, issued: IssuedSession, *, refresh_expires_in_seconds: int
) -> AuthState:
    """Set the cookie trio and build the body the SPA reads.

    The CSRF token is fresh per session; the access cookie's `max_age` is the
    token's own TTL so the browser drops it exactly when the server stops
    honouring it.
    """
    access_ttl = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    csrf_token = new_csrf_token()
    set_auth_cookies(
        response,
        access_token=issued.access_token,
        access_max_age=access_ttl,
        refresh_token=issued.refresh_token,
        refresh_max_age=refresh_expires_in_seconds,
        csrf_token=csrf_token,
    )


@router.post(
    "/register",
    response_model=AuthState,
    status_code=status.HTTP_201_CREATED,
    summary="Create an account",
    responses={409: {"description": "Email already registered"}},
)
def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    auth: AuthServiceDep,
    context: ClientContextDep,
) -> AuthState:
    """Register and sign in immediately.

    Always creates `role = "user"`. There is no request field that can influence
    the role — `RegisterRequest` forbids extras, so sending one is a 422.
    """
    rate_limit(request, scope=SCOPE_REGISTER)

    issued = auth.register(payload, context=context)
    user = auth.get_user(issued.session.user_id)
    assert user is not None  # just created in this transaction

    preferences = auth.get_preferences(user)
    _attach_session(
        response,
        issued,
        refresh_expires_in_seconds=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86_400,
    )
    return AuthState(
        user=_user_read(user),
        preferences=PreferencesRead.model_validate(preferences),
        access_token_expires_at=issued.access_expires_at,
    )


@router.post(
    "/login",
    response_model=AuthState,
    summary="Exchange credentials for a session",
    responses={
        401: {"description": "Invalid credentials"},
        429: {"description": "Too many attempts"},
    },
)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    auth: AuthServiceDep,
    context: ClientContextDep,
) -> AuthState:
    """Authenticate and issue a session.

    Every failure — unknown address, wrong password, disabled account, active
    lockout short of the throttle — produces the same "Invalid email or
    password." so the endpoint cannot be used to enumerate accounts.
    """
    rate_limit(request, scope=SCOPE_LOGIN)

    user = auth.authenticate(payload.email, payload.password, context=context)
    issued = auth.issue_session(user, context=context)
    preferences = auth.get_preferences(user)
    _attach_session(
        response,
        issued,
        refresh_expires_in_seconds=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86_400,
    )
    return AuthState(
        user=_user_read(user),
        preferences=PreferencesRead.model_validate(preferences),
        access_token_expires_at=issued.access_expires_at,
    )


@router.post(
    "/refresh",
    response_model=AuthState,
    summary="Rotate the refresh token and issue a new access token",
    responses={401: {"description": "Refresh token missing, expired or revoked"}},
)
def refresh(
    request: Request,
    response: Response,
    auth: AuthServiceDep,
    context: ClientContextDep,
) -> AuthState:
    """Consume the refresh cookie and mint a new session.

    Rotation means the presented token is dead after this call. A replayed
    token revokes every session for the account (see `AuthService.rotate_session`).
    """
    enforce_csrf(request)

    refresh_token = read_refresh_token(request)
    if not refresh_token:
        clear_auth_cookies(response)
        raise AuthenticationError("Your session is no longer valid.")

    issued = auth.rotate_session(refresh_token, context=context)
    user = auth.get_user(issued.session.user_id)
    if user is None:
        clear_auth_cookies(response)
        raise AuthenticationError("Your session is no longer valid.")

    preferences = auth.get_preferences(user)
    _attach_session(
        response,
        issued,
        refresh_expires_in_seconds=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86_400,
    )
    return AuthState(
        user=_user_read(user),
        preferences=PreferencesRead.model_validate(preferences),
        access_token_expires_at=issued.access_expires_at,
    )


@router.post("/logout", response_model=MessageResponse, summary="End the current session")
def logout(
    request: Request,
    response: Response,
    auth: AuthServiceDep,
    context: ClientContextDep,
) -> MessageResponse:
    """Revoke the session and clear the cookies.

    Succeeds even with an expired access token: a client that cannot
    authenticate must still be able to throw its refresh token away, otherwise
    it would be stuck holding a usable credential it cannot revoke.
    """
    enforce_csrf(request)

    session_id: str | None = None
    user: User | None = None

    token = read_access_token(request)
    if token:
        try:
            claims = decode_access_token(token)
        except AccessTokenError:
            # Expired or malformed access token: fall back to the refresh
            # cookie, which is enough to identify and revoke the session.
            claims = None
        if claims:
            session_id = str(claims["sid"])
            user = auth.get_user(str(claims["sub"]))

    refresh_token = read_refresh_token(request)
    if user is None and refresh_token:
        # Identify the account from the refresh token so the logout is still
        # attributed in the audit trail.
        row = auth.session.scalar(
            select(AuthSession).where(AuthSession.token_hash == hash_token(refresh_token))
        )
        if row is not None:
            user = auth.get_user(row.user_id)

    if user is not None:
        auth.logout(
            user,
            session_id=session_id,
            refresh_token=refresh_token,
            context=context,
        )
    else:
        # Nothing to revoke, but the cookies must still go.
        logger.info("Logout with no resolvable session; clearing cookies only")

    clear_auth_cookies(response)
    return MessageResponse(message="Signed out.")


@router.get("/me", response_model=AuthState, summary="Current authenticated user")
def me(auth: AuthServiceDep, identity: CurrentUser) -> AuthState:
    """Return the caller's identity, role and preferences.

    This is what the SPA calls on boot to decide between the login screen and
    the app shell. The role it returns is informational — every authorization
    decision is re-made server-side on the request that needs it.
    """
    preferences = auth.get_preferences(identity.user)
    expires_at = utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return AuthState(
        user=_user_read(identity.user),
        preferences=PreferencesRead.model_validate(preferences),
        access_token_expires_at=expires_at,
    )


@router.post(
    "/change-password",
    response_model=MessageResponse,
    summary="Change the current password",
    responses={401: {"description": "Current password incorrect"}},
)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    auth: AuthServiceDep,
    identity: CurrentUser,
    context: ClientContextDep,
) -> MessageResponse:
    """Verify the current password, then replace it.

    Every other session is revoked; the session this request arrived on is kept
    so the user is not signed out of the tab they are using.
    """
    enforce_csrf(request)
    auth.change_password(
        identity.user,
        payload,
        keep_session_id=identity.session_id,
        context=context,
    )
    return MessageResponse(message="Password updated. Other devices were signed out.")


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    summary="Request a password reset link",
)
def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    auth: AuthServiceDep,
    context: ClientContextDep,
) -> ForgotPasswordResponse:
    """Issue a single-use reset token.

    The response is identical whether or not the address is registered, so this
    cannot be used to enumerate accounts. The token is never returned in the
    body — only handed to the mailer.
    """
    rate_limit(request, scope=SCOPE_RESET)

    raw_token, user = auth.request_password_reset(payload.email, context=context)

    delivered = False
    if raw_token is not None and user is not None:
        reset_url = f"{RESET_PATH}#token={raw_token}"
        delivered = mailer.send_password_reset(
            to_email=user.email,
            reset_url=reset_url,
            expires_minutes=settings.RESET_TOKEN_EXPIRE_MINUTES,
        )

    return ForgotPasswordResponse(
        delivery="sent" if delivered else "unconfigured",
    )


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Complete a password reset",
    responses={422: {"description": "Reset token invalid, used or expired"}},
)
def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    auth: AuthServiceDep,
    context: ClientContextDep,
) -> MessageResponse:
    """Consume a reset token and set a new password.

    The token is single-use and expires; using it revokes every existing
    session for the account.
    """
    rate_limit(request, scope=SCOPE_RESET)
    auth.reset_password(payload.token, payload.password, context=context)
    return MessageResponse(message="Password reset. Sign in with your new password.")


@router.get(
    "/sessions",
    response_model=list[AuthSessionRead],
    summary="List active sessions for the current user",
)
def list_sessions(auth: AuthServiceDep, identity: CurrentUser) -> list[AuthSessionRead]:
    rows = auth.list_sessions(identity.user.id)
    return [
        AuthSessionRead(
            id=row.id,
            created_at=row.created_at,
            expires_at=row.expires_at,
            last_used_at=row.last_used_at,
            user_agent=row.user_agent,
            current=row.id == identity.session_id,
        )
        for row in rows
    ]


@router.delete(
    "/sessions",
    response_model=MessageResponse,
    summary="Sign out of every session",
)
def revoke_all_sessions(
    request: Request,
    auth: AuthServiceDep,
    identity: CurrentUser,
    context: ClientContextDep,
) -> MessageResponse:
    enforce_csrf(request)
    revoked = auth.revoke_all_sessions(identity.user.id)
    auth.record_event(
        EVENT_LOGOUT,
        user=identity.user,
        context=context,
        detail=f"revoked {revoked} session(s)",
        commit=True,
    )
    return MessageResponse(message="Signed out of all sessions.")


@router.patch(
    "/profile",
    response_model=UserRead,
    summary="Update the current user's profile",
)
def update_profile(
    payload: ProfileUpdate,
    request: Request,
    auth: AuthServiceDep,
    identity: CurrentUser,
    context: ClientContextDep,
) -> UserRead:
    """Update name and avatar only.

    `role`, `is_active` and `password_hash` are not fields on `ProfileUpdate`,
    and the schema forbids extras — so an attempt to set any of them is a 422,
    not a silently ignored key.
    """
    enforce_csrf(request)
    user = auth.update_profile(identity.user, payload, context=context)
    return _user_read(user)


@router.patch(
    "/preferences",
    response_model=PreferencesRead,
    summary="Update the current user's preferences",
)
def update_preferences(
    payload: PreferencesUpdate,
    request: Request,
    auth: AuthServiceDep,
    identity: CurrentUser,
) -> PreferencesRead:
    enforce_csrf(request)
    preferences = auth.update_preferences(identity.user, payload)
    return PreferencesRead.model_validate(preferences)


__all__ = ["router"]
