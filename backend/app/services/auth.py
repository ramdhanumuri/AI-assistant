"""Authentication orchestration.

Owns the whole credential lifecycle: registration, login, session issue and
rotation, logout, password change and reset. Routes stay thin; dependencies
only read identity.

Design decisions worth knowing before editing:

* **Login is constant-work.** An unknown email still runs a full Argon2 verify
  against a dummy hash. Without that, the response time alone reveals whether
  an address is registered.
* **Session ids, not just signatures.** Every access token carries the id of an
  `auth_sessions` row, so revoking a session (logout, password change, account
  deactivation) invalidates tokens that are otherwise still cryptographically
  valid. A pure stateless JWT could not do this without a denylist.
* **Refresh rotates.** Presenting a refresh token consumes it and issues a new
  one. A replayed token therefore hits an already-rotated row, which is treated
  as theft: every session for that user is revoked.
* **Roles are never read from a request.** `role` is only ever written by
  `set_role`, which is reachable solely from the admin dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import (
    AccountInactiveError,
    AuthenticationError,
    ConflictError,
    EmailAlreadyRegisteredError,
    InvalidRequestError,
    RateLimitedError,
)
from app.core.logging import get_logger
from app.core.ratelimit import check_rate_limit
from app.core.security import (
    create_access_token,
    generate_opaque_token,
    hash_identifier,
    hash_password,
    hash_token,
    needs_rehash,
    tokens_equal,
    verify_password,
)
from app.db.base import utcnow
from app.models import (
    EVENT_ACCOUNT_DEACTIVATED,
    EVENT_ACCOUNT_REACTIVATED,
    EVENT_LOGIN_FAILURE,
    EVENT_LOGIN_LOCKED,
    EVENT_LOGIN_SUCCESS,
    EVENT_LOGOUT,
    EVENT_PASSWORD_CHANGED,
    EVENT_PASSWORD_RESET_COMPLETED,
    EVENT_PASSWORD_RESET_REQUESTED,
    EVENT_PROFILE_UPDATED,
    EVENT_REGISTERED,
    EVENT_ROLE_CHANGED,
    EVENT_SESSION_REVOKED,
    EVENT_SUSPICIOUS_ACTIVITY,
    EVENT_TOKEN_REFRESHED,
    EVENT_TOKEN_REUSE_DETECTED,
    ROLE_ADMIN,
    ROLE_USER,
    ROLES,
    AuthEvent,
    AuthSession,
    PasswordResetToken,
    User,
    UserPreferences,
)
from app.schemas.auth import (
    ChangePasswordRequest,
    PreferencesUpdate,
    ProfileUpdate,
    RegisterRequest,
)

logger = get_logger(__name__)

# Same shape as a real Argon2id digest, so a verify against it costs the same
# as a verify against a stored password. Generated once at import.
_DUMMY_PASSWORD_HASH = hash_password("aurelis-dummy-password-for-timing-parity")

# Error text used for every failed credential check. Identical for an unknown
# address, a wrong password and an inactive account so none of the three can be
# distinguished from the response.
GENERIC_CREDENTIAL_ERROR = "Invalid email or password."
INACTIVE_ERROR = "This account has been disabled."


@dataclass(frozen=True)
class IssuedSession:
    """A freshly minted session. `refresh_token` exists only in this object.

    It is returned to the caller once so it can be set as a cookie; only its
    digest is persisted.
    """

    session: AuthSession
    refresh_token: str
    access_token: str
    access_expires_at: datetime


@dataclass(frozen=True)
class ClientContext:
    """Non-identifying request metadata recorded alongside a session/event."""

    user_agent: str | None = None
    ip_address: str | None = None

    @property
    def ip_hash(self) -> str | None:
        return hash_identifier(self.ip_address) if self.ip_address else None

    @property
    def truncated_user_agent(self) -> str | None:
        if not self.user_agent:
            return None
        return self.user_agent[:400]


def _as_utc(value: datetime) -> datetime:
    """SQLite drops tzinfo on round-trip; treat a naive value as UTC."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class AuthService:
    def __init__(self, session: Session) -> None:
        self.session = session

    # ── Audit ────────────────────────────────────────────────────────

    def record_event(
        self,
        event_type: str,
        *,
        user: User | None = None,
        email: str | None = None,
        context: ClientContext | None = None,
        outcome: str = "success",
        detail: str | None = None,
        commit: bool = False,
    ) -> AuthEvent:
        """Append to the audit trail.

        `detail` is short, non-sensitive context only. Passwords, tokens and
        reset links must never reach this call.
        """
        event = AuthEvent(
            user_id=user.id if user else None,
            event_type=event_type,
            outcome=outcome,
            email_hash=hash_identifier(email) if email else None,
            ip_hash=context.ip_hash if context else None,
            user_agent=context.truncated_user_agent if context else None,
            detail=detail,
            occurred_at=utcnow(),
        )
        self.session.add(event)
        if commit:
            self.session.commit()
        return event

    # ── Lookup ───────────────────────────────────────────────────────

    def get_user_by_email(self, email: str) -> User | None:
        return self.session.scalar(select(User).where(User.email == email))

    def get_user(self, user_id: str) -> User | None:
        return self.session.get(User, user_id)

    # ── Registration ─────────────────────────────────────────────────

    def register(
        self, payload: RegisterRequest, *, context: ClientContext | None = None
    ) -> IssuedSession:
        email = payload.email
        if self.get_user_by_email(email) is not None:
            self.record_event(
                EVENT_REGISTERED,
                email=email,
                context=context,
                outcome="failure",
                detail="email already registered",
                commit=True,
            )
            raise EmailAlreadyRegisteredError(
                "An account with that email address already exists."
            )

        user = User(
            full_name=payload.full_name,
            email=email,
            password_hash=hash_password(payload.password),
            # Hard-coded, never derived from the request. Public registration
            # cannot mint an administrator.
            role=ROLE_USER,
            is_active=True,
            email_verified=False,
        )
        self.session.add(user)
        self.session.flush()

        # Preferences are created with the account so no read path has to cope
        # with a missing row.
        self.session.add(UserPreferences(user_id=user.id))

        self.record_event(EVENT_REGISTERED, user=user, email=email, context=context)

        try:
            self.session.commit()
        except IntegrityError as exc:
            # The unique index on `users.email` is the real guard; a concurrent
            # registration lands here rather than passing the check above.
            self.session.rollback()
            logger.info("Concurrent registration for an existing email")
            raise EmailAlreadyRegisteredError(
                "An account with that email address already exists."
            ) from exc

        self.session.refresh(user)
        return self.issue_session(user, context=context)

    # ── Login ────────────────────────────────────────────────────────

    def authenticate(
        self, email: str, password: str, *, context: ClientContext | None = None
    ) -> User:
        # Per-(address, account) throttle, independent of the per-address budget
        # the route already applies. The route's budget stops one host spraying
        # many accounts; this stops a distributed set of hosts all targeting one
        # account, which the address-only limit cannot see.
        email_hash = hash_identifier(email)
        ip_hash = context.ip_hash if context else None
        pair_key = f"{ip_hash or 'unknown'}:{email_hash}"
        pair_result = check_rate_limit("login", pair_key)
        if not pair_result.allowed:
            self.record_event(
                EVENT_LOGIN_FAILURE,
                email=email,
                context=context,
                outcome="denied",
                detail="login throttle active",
                commit=True,
            )
            raise RateLimitedError(
                "Too many attempts. Try again shortly.",
                retry_after_seconds=pair_result.retry_after_seconds,
            )

        user = self.get_user_by_email(email)

        if user is None:
            # Spend the same time as a real verification so response latency
            # does not disclose whether the address exists.
            verify_password(password, _DUMMY_PASSWORD_HASH)
            self.record_event(
                EVENT_LOGIN_FAILURE,
                email=email,
                context=context,
                outcome="failure",
                detail="unknown email",
                commit=True,
            )
            raise AuthenticationError(GENERIC_CREDENTIAL_ERROR)

        if not user.is_active:
            # Reported as a credential failure: telling an unauthenticated
            # caller "this account is disabled" confirms the account exists.
            self.record_event(
                EVENT_LOGIN_FAILURE,
                user=user,
                email=email,
                context=context,
                outcome="failure",
                detail="inactive account",
                commit=True,
            )
            raise AuthenticationError(GENERIC_CREDENTIAL_ERROR)

        locked_until = _as_utc(user.locked_until) if user.locked_until else None
        if locked_until and locked_until > utcnow():
            retry_after = int((locked_until - utcnow()).total_seconds())
            user.failed_login_count = (user.failed_login_count or 0) + 1
            # A client that keeps hitting an active lock is not a confused user;
            # escalate it so the audit trail shows a sustained attempt rather
            # than a wall of identical lockout rows.
            if user.failed_login_count % settings.AUTH_MAX_FAILED_LOGINS == 0:
                self.record_event(
                    EVENT_SUSPICIOUS_ACTIVITY,
                    user=user,
                    email=email,
                    context=context,
                    outcome="denied",
                    detail=f"repeated attempts against a locked account ({user.failed_login_count})",
                    commit=True,
                )
            self.record_event(
                EVENT_LOGIN_LOCKED,
                user=user,
                email=email,
                context=context,
                outcome="denied",
                detail="temporary lockout active",
                commit=True,
            )
            # Generic: identical text to the throttle response, so an attacker
            # cannot tell "you are rate limited" from "this account is locked".
            raise RateLimitedError(
                "Too many attempts. Try again shortly.",
                retry_after_seconds=retry_after,
            )

        if not verify_password(password, user.password_hash):
            self._register_failed_attempt(user, email=email, context=context)
            raise AuthenticationError(GENERIC_CREDENTIAL_ERROR)

        if needs_rehash(user.password_hash):
            # Transparent upgrade: the plaintext is only available here, at the
            # one moment it is verified.
            user.password_hash = hash_password(password)

        user.failed_login_count = 0
        user.locked_until = None
        user.last_login_at = utcnow()
        self.record_event(EVENT_LOGIN_SUCCESS, user=user, email=email, context=context)
        self.session.commit()
        self.session.refresh(user)
        return user

    def _register_failed_attempt(
        self, user: User, *, email: str, context: ClientContext | None
    ) -> None:
        """Count a bad password and lock the account past a threshold.

        The counter is cleared on success and the lock expires on its own, so a
        legitimate user cannot be locked out permanently.
        """
        user.failed_login_count = (user.failed_login_count or 0) + 1
        detail = "invalid password"

        if user.failed_login_count >= settings.AUTH_MAX_FAILED_LOGINS:
            user.locked_until = utcnow() + timedelta(seconds=settings.AUTH_LOCKOUT_SECONDS)
            detail = f"lockout after {user.failed_login_count} failures"

        self.record_event(
            EVENT_LOGIN_FAILURE,
            user=user,
            email=email,
            context=context,
            outcome="failure",
            detail=detail,
        )
        self.session.commit()

    # ── Sessions ─────────────────────────────────────────────────────

    def issue_session(
        self, user: User, *, context: ClientContext | None = None
    ) -> IssuedSession:
        now = utcnow()
        refresh_token = generate_opaque_token()
        auth_session = AuthSession(
            user_id=user.id,
            token_hash=hash_token(refresh_token),
            expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            last_used_at=now,
            user_agent=context.truncated_user_agent if context else None,
            ip_hash=context.ip_hash if context else None,
        )
        self.session.add(auth_session)
        self.session.commit()
        self.session.refresh(auth_session)

        access_token, expires_at = create_access_token(
            user_id=user.id, session_id=auth_session.id, now=now
        )
        return IssuedSession(
            session=auth_session,
            refresh_token=refresh_token,
            access_token=access_token,
            access_expires_at=expires_at,
        )

    def get_session(self, session_id: str) -> AuthSession | None:
        return self.session.get(AuthSession, session_id)

    def rotate_session(
        self, refresh_token: str, *, context: ClientContext | None = None
    ) -> IssuedSession:
        """Exchange a refresh token for a new session, consuming the old one."""
        digest = hash_token(refresh_token)
        auth_session = self.session.scalar(
            select(AuthSession).where(AuthSession.token_hash == digest)
        )

        if auth_session is None:
            # Not a token this server ever issued. Nothing to revoke, and no
            # user to attribute it to.
            self.record_event(
                EVENT_TOKEN_REFRESHED,
                context=context,
                outcome="failure",
                detail="unknown refresh token",
                commit=True,
            )
            raise AuthenticationError("Your session is no longer valid.")

        user = self.session.get(User, auth_session.user_id)
        now = utcnow()

        if auth_session.revoked_at is not None:
            # The token was already rotated or explicitly revoked and has now
            # been presented again. That is the signature of a stolen token, so
            # assume the worst and end every session for the account.
            self._revoke_all_sessions(user.id if user else auth_session.user_id)
            self.record_event(
                EVENT_TOKEN_REUSE_DETECTED,
                user=user,
                context=context,
                outcome="denied",
                detail="replayed rotated refresh token",
                commit=True,
            )
            raise AuthenticationError("Your session is no longer valid.")

        if _as_utc(auth_session.expires_at) <= now:
            self.record_event(
                EVENT_TOKEN_REFRESHED,
                user=user,
                context=context,
                outcome="failure",
                detail="expired refresh token",
                commit=True,
            )
            raise AuthenticationError("Your session has expired.")

        if user is None or not user.is_active:
            auth_session.revoked_at = now
            self.record_event(
                EVENT_TOKEN_REFRESHED,
                user=user,
                context=context,
                outcome="denied",
                detail="inactive or missing account",
                commit=True,
            )
            raise AccountInactiveError(INACTIVE_ERROR)

        # Consume the presented token, then issue a fresh one.
        auth_session.revoked_at = now
        auth_session.last_used_at = now
        self.session.flush()
        self.record_event(EVENT_TOKEN_REFRESHED, user=user, context=context)
        return self.issue_session(user, context=context)

    def revoke_session(self, session_id: str) -> bool:
        auth_session = self.session.get(AuthSession, session_id)
        if auth_session is None or auth_session.revoked_at is not None:
            return False
        auth_session.revoked_at = utcnow()
        self.session.commit()
        return True

    def revoke_session_by_token(self, refresh_token: str) -> bool:
        digest = hash_token(refresh_token)
        auth_session = self.session.scalar(
            select(AuthSession).where(AuthSession.token_hash == digest)
        )
        if auth_session is None or auth_session.revoked_at is not None:
            return False
        auth_session.revoked_at = utcnow()
        self.session.commit()
        return True

    def _revoke_all_sessions(self, user_id: str) -> int:
        result = self.session.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=utcnow())
        )
        self.session.commit()
        return int(result.rowcount or 0)

    def revoke_all_sessions(self, user_id: str) -> int:
        """Public entry point for "sign out everywhere"."""
        return self._revoke_all_sessions(user_id)

    def list_sessions(self, user_id: str) -> list[AuthSession]:
        now = utcnow()
        return list(
            self.session.scalars(
                select(AuthSession)
                .where(
                    AuthSession.user_id == user_id,
                    AuthSession.revoked_at.is_(None),
                    AuthSession.expires_at > now,
                )
                .order_by(AuthSession.created_at.desc())
            )
        )

    def count_active_sessions(self, user_id: str) -> int:
        now = utcnow()
        return int(
            self.session.scalar(
                select(func.count())
                .select_from(AuthSession)
                .where(
                    AuthSession.user_id == user_id,
                    AuthSession.revoked_at.is_(None),
                    AuthSession.expires_at > now,
                )
            )
            or 0
        )

    # ── Logout ───────────────────────────────────────────────────────

    def logout(
        self,
        user: User,
        *,
        session_id: str | None,
        refresh_token: str | None = None,
        context: ClientContext | None = None,
    ) -> None:
        """End the session identified by the access token (or refresh cookie).

        Both are revoked when both are present, so a client that lost its
        access token can still invalidate its refresh token.
        """
        revoked = False
        if session_id:
            revoked = self.revoke_session(session_id) or revoked
        if refresh_token:
            revoked = self.revoke_session_by_token(refresh_token) or revoked

        self.record_event(
            EVENT_LOGOUT,
            user=user,
            context=context,
            detail="session revoked" if revoked else "no active session found",
            commit=True,
        )

    # ── Passwords ────────────────────────────────────────────────────

    def change_password(
        self,
        user: User,
        payload: ChangePasswordRequest,
        *,
        keep_session_id: str | None = None,
        context: ClientContext | None = None,
    ) -> None:
        if not verify_password(payload.current_password, user.password_hash):
            self.record_event(
                EVENT_PASSWORD_CHANGED,
                user=user,
                context=context,
                outcome="failure",
                detail="current password incorrect",
                commit=True,
            )
            raise AuthenticationError("Your current password is incorrect.")

        user.password_hash = hash_password(payload.new_password)
        user.failed_login_count = 0
        user.locked_until = None
        self.session.flush()

        # Every other session dies; the caller keeps the one it is using so the
        # user is not signed out of the tab they just changed the password in.
        self.session.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=utcnow())
        )
        self.record_event(
            EVENT_PASSWORD_CHANGED,
            user=user,
            context=context,
            detail="all other sessions revoked",
        )
        self.session.commit()

        if keep_session_id:
            kept = self.session.get(AuthSession, keep_session_id)
            if kept is not None:
                # Restore the session the request arrived on.
                kept.revoked_at = None
                self.session.commit()

    def request_password_reset(
        self, email: str, *, context: ClientContext | None = None
    ) -> tuple[str | None, User | None]:
        """Create a single-use reset token. Returns (raw_token, user).

        The raw token is returned to the caller and never persisted. Returns
        `(None, None)` for an unknown address — the route answers identically
        either way so the response cannot be used to enumerate accounts.
        """
        user = self.get_user_by_email(email)
        if user is None or not user.is_active:
            self.record_event(
                EVENT_PASSWORD_RESET_REQUESTED,
                email=email,
                context=context,
                outcome="failure",
                detail="no active account for address",
                commit=True,
            )
            return None, None

        # Supersede any outstanding token: only the newest link works.
        self.session.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used_at.is_(None),
            )
            .values(used_at=utcnow())
        )

        raw_token = generate_opaque_token()
        self.session.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=hash_token(raw_token),
                expires_at=utcnow()
                + timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES),
            )
        )
        self.record_event(
            EVENT_PASSWORD_RESET_REQUESTED,
            user=user,
            email=email,
            context=context,
            detail="token issued",
        )
        self.session.commit()
        return raw_token, user

    def reset_password(
        self,
        raw_token: str,
        new_password: str,
        *,
        context: ClientContext | None = None,
    ) -> User:
        digest = hash_token(raw_token)
        token = self.session.scalar(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == digest)
        )
        now = utcnow()

        if (
            token is None
            or token.used_at is not None
            or _as_utc(token.expires_at) <= now
        ):
            self.record_event(
                EVENT_PASSWORD_RESET_COMPLETED,
                context=context,
                outcome="failure",
                detail="invalid, used or expired reset token",
                commit=True,
            )
            raise InvalidRequestError(
                "This password reset link is invalid or has expired."
            )

        user = self.session.get(User, token.user_id)
        if user is None or not user.is_active:
            token.used_at = now
            self.session.commit()
            raise InvalidRequestError(
                "This password reset link is invalid or has expired."
            )

        user.password_hash = hash_password(new_password)
        user.failed_login_count = 0
        user.locked_until = None
        token.used_at = now

        # A reset implies the old credentials may be compromised.
        self.session.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        self.record_event(
            EVENT_PASSWORD_RESET_COMPLETED,
            user=user,
            context=context,
            detail="password reset and sessions revoked",
        )
        self.session.commit()
        self.session.refresh(user)
        return user

    # ── Profile ──────────────────────────────────────────────────────

    def update_profile(
        self,
        user: User,
        payload: ProfileUpdate,
        *,
        context: ClientContext | None = None,
    ) -> User:
        """Apply the mutable profile fields.

        Only `full_name` and `avatar_url` are reachable — the schema forbids
        anything else, so there is no filtering logic here that could be
        bypassed by a future field addition.
        """
        changes = payload.model_dump(exclude_unset=True)
        for field, value in changes.items():
            setattr(user, field, value)
        if changes:
            self.record_event(
                EVENT_PROFILE_UPDATED,
                user=user,
                context=context,
                detail=", ".join(sorted(changes)),
            )
        self.session.commit()
        self.session.refresh(user)
        return user

    def get_preferences(self, user: User) -> UserPreferences:
        """Return the user's preferences, creating the row if it is missing."""
        preferences = self.session.scalar(
            select(UserPreferences).where(UserPreferences.user_id == user.id)
        )
        if preferences is None:
            preferences = UserPreferences(user_id=user.id)
            self.session.add(preferences)
            self.session.commit()
            self.session.refresh(preferences)
        return preferences

    def update_preferences(
        self, user: User, payload: PreferencesUpdate
    ) -> UserPreferences:
        preferences = self.get_preferences(user)
        for field, value in payload.model_dump(exclude_unset=True).items():
            if value is not None:
                setattr(preferences, field, value)
        self.session.commit()
        self.session.refresh(preferences)
        return preferences

    # ── Administration ───────────────────────────────────────────────

    def set_role(
        self, actor: User, target: User, role: str, *, context: ClientContext | None = None
    ) -> User:
        """Change a user's role. Admin-only, and refuses self-demotion.

        Blocking self-demotion avoids the lockout where the last administrator
        removes their own access and no one can restore it.
        """
        if role not in ROLES:
            raise InvalidRequestError(f"Unknown role '{role}'.")
        if actor.id == target.id and role != ROLE_ADMIN:
            raise InvalidRequestError("You cannot remove your own administrator role.")

        previous = target.role
        target.role = role
        self.session.flush()

        if role != ROLE_ADMIN:
            # A demoted account must not keep an admin-privileged session.
            self._revoke_all_sessions(target.id)

        self.record_event(
            EVENT_ROLE_CHANGED,
            user=target,
            context=context,
            detail=f"{previous} -> {role}",
        )
        self.session.commit()
        self.session.refresh(target)
        return target

    def set_active(
        self,
        actor: User,
        target: User,
        is_active: bool,
        *,
        context: ClientContext | None = None,
    ) -> User:
        """Enable or disable an account, invalidating sessions on disable."""
        if actor.id == target.id and not is_active:
            raise InvalidRequestError("You cannot deactivate your own account.")

        target.is_active = is_active
        self.session.flush()

        if not is_active:
            self._revoke_all_sessions(target.id)
            self.record_event(
                EVENT_ACCOUNT_DEACTIVATED,
                user=target,
                context=context,
                outcome="denied",
                detail="sessions revoked",
            )
        else:
            target.failed_login_count = 0
            target.locked_until = None
            self.record_event(EVENT_ACCOUNT_REACTIVATED, user=target, context=context)

        self.session.commit()
        self.session.refresh(target)
        return target
