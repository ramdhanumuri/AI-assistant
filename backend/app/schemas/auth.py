"""Authentication and profile wire models.

`APIModel` is reused so these bodies follow the same conventions as the rest of
the API (camelCase on the wire, `extra="forbid"` so an unexpected field is a
400 rather than a silently ignored key). That last point is load-bearing for
security: a request carrying `"role": "admin"` is *rejected*, which is a
stronger guarantee than accepting it and ignoring it.

Emails are normalised in a validator rather than in the service so the same
rule applies whether the value arrives at registration, login or a reset
request.
"""

from __future__ import annotations

from pydantic import EmailStr, Field, field_validator, model_validator

from app.core.security import PASSWORD_MAX_LENGTH, validate_password_strength
from app.schemas.common import APIModel, EpochMillis, ORMModel

MAX_FULL_NAME = 120


def normalise_email(value: str) -> str:
    """Canonical form used for every lookup and every write.

    Lowercase the domain (which is case-insensitive by RFC 5321) and the local
    part too — technically the local part is case-sensitive, but no mainstream
    provider treats it that way, and treating `User@x.com` as a different
    account from `user@x.com` is a real impersonation vector. Whitespace and a
    stray `mailto:` are stripped because both arrive from copy-paste.
    """
    cleaned = value.strip().removeprefix("mailto:")
    return cleaned.lower()


def _check_password(value: str) -> str:
    problems = validate_password_strength(value)
    if problems:
        raise ValueError(" ".join(problems))
    return value


class RegisterRequest(APIModel):
    full_name: str = Field(min_length=1, max_length=MAX_FULL_NAME)
    email: EmailStr
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)
    # Optional in the body: the UI validates the confirmation client-side, but
    # the backend enforces it when supplied so the two can never disagree.
    confirm_password: str | None = None

    @field_validator("full_name")
    @classmethod
    def _clean_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Full name is required.")
        return cleaned

    @field_validator("email")
    @classmethod
    def _clean_email(cls, value: str) -> str:
        return normalise_email(str(value))

    @field_validator("password")
    @classmethod
    def _strong_password(cls, value: str) -> str:
        return _check_password(value)

    @model_validator(mode="after")
    def _confirmation_matches(self) -> "RegisterRequest":
        if self.confirm_password is not None and self.confirm_password != self.password:
            raise ValueError("Password confirmation does not match.")
        return self


class LoginRequest(APIModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)

    @field_validator("email")
    @classmethod
    def _clean_email(cls, value: str) -> str:
        return normalise_email(str(value))


class ForgotPasswordRequest(APIModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def _clean_email(cls, value: str) -> str:
        return normalise_email(str(value))


class ResetPasswordRequest(APIModel):
    token: str = Field(min_length=16, max_length=512)
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)
    confirm_password: str | None = None

    @field_validator("password")
    @classmethod
    def _strong_password(cls, value: str) -> str:
        return _check_password(value)

    @model_validator(mode="after")
    def _confirmation_matches(self) -> "ResetPasswordRequest":
        if self.confirm_password is not None and self.confirm_password != self.password:
            raise ValueError("Password confirmation does not match.")
        return self


class ChangePasswordRequest(APIModel):
    current_password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)
    new_password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)
    confirm_password: str | None = None

    @field_validator("new_password")
    @classmethod
    def _strong_password(cls, value: str) -> str:
        return _check_password(value)

    @model_validator(mode="after")
    def _confirmation_matches(self) -> "ChangePasswordRequest":
        if self.confirm_password is not None and self.confirm_password != self.new_password:
            raise ValueError("Password confirmation does not match.")
        if self.current_password == self.new_password:
            raise ValueError("New password must differ from the current password.")
        return self


class UserRead(ORMModel):
    """The only user shape that ever leaves the server.

    Assembled from explicit fields rather than `model_validate(user)` on
    purpose: `extra="forbid"` plus a declared field list means adding
    `password_hash` to the model can never accidentally start publishing it.
    """

    id: str
    full_name: str
    email: str
    role: str
    is_active: bool
    avatar_url: str | None = None
    email_verified: bool = False
    created_at: EpochMillis


class PreferencesRead(ORMModel):
    ambient_light: bool
    particles: bool
    reduce_motion: bool
    streaming: bool
    memory: bool
    citations: bool
    soundscape: bool
    density: str


class PreferencesUpdate(APIModel):
    ambient_light: bool | None = None
    particles: bool | None = None
    reduce_motion: bool | None = None
    streaming: bool | None = None
    memory: bool | None = None
    citations: bool | None = None
    soundscape: bool | None = None
    density: str | None = Field(default=None, pattern="^(comfortable|compact)$")


class ProfileUpdate(APIModel):
    """Mutable profile fields — and only these.

    `role`, `is_active`, `password_hash`, `id` and `email` are absent by design.
    `extra="forbid"` turns an attempt to send any of them into a 422, so a
    privilege-escalation attempt is refused at the edge instead of relying on a
    service-layer filter remembering to drop the field.
    """

    full_name: str | None = Field(default=None, min_length=1, max_length=MAX_FULL_NAME)
    avatar_url: str | None = Field(default=None, max_length=512)

    @field_validator("full_name")
    @classmethod
    def _clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Full name cannot be blank.")
        return cleaned

    @field_validator("avatar_url")
    @classmethod
    def _safe_avatar(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        # Only http(s) — blocks `javascript:` and `data:` URLs, which would
        # otherwise be stored and rendered by the client.
        if not cleaned.startswith(("https://", "http://")):
            raise ValueError("Avatar URL must be an http(s) address.")
        return cleaned


class AuthSessionRead(APIModel):
    id: str
    created_at: EpochMillis
    expires_at: EpochMillis
    last_used_at: EpochMillis | None = None
    user_agent: str | None = None
    current: bool = False


class AuthState(APIModel):
    """What the SPA needs to render an authenticated shell.

    Carries no token: the tokens are HttpOnly cookies set by the response, so
    they are deliberately unreadable from JavaScript.
    """

    user: UserRead
    preferences: PreferencesRead
    # Epoch millis of the access token's expiry, so the client can refresh
    # proactively instead of waiting for a 401.
    access_token_expires_at: EpochMillis


class ForgotPasswordResponse(APIModel):
    """Identical for a known and an unknown address — no account enumeration."""

    status: str = "accepted"
    message: str = (
        "If an account exists for that address, a reset link has been sent."
    )
    # True only when no mail provider is wired up, so the operator knows the
    # token was recorded but not delivered.
    delivery: str = "unconfigured"


class MessageResponse(APIModel):
    status: str = "ok"
    message: str


# ── Admin surface ─────────────────────────────────────────────────────


class AdminUserRead(UserRead):
    last_login_at: EpochMillis | None = None
    failed_login_count: int = 0
    locked_until: EpochMillis | None = None
    active_sessions: int = 0
    conversation_count: int = 0


class AdminUserUpdate(APIModel):
    """Administrator-only mutations.

    `role` is the whole point of this schema, and it is reachable *only* behind
    `require_admin`. There is no path from a normal profile update to a role
    change.
    """

    role: str | None = Field(default=None, pattern="^(user|admin)$")
    is_active: bool | None = None


class AuthEventRead(ORMModel):
    id: int
    event_type: str
    outcome: str
    user_id: str | None = None
    email_hash: str | None = None
    ip_hash: str | None = None
    detail: str | None = None
    occurred_at: EpochMillis


class UsageBucket(APIModel):
    label: str
    value: int
    secondary: int = 0


class AdminUsage(APIModel):
    total_users: int
    active_users: int
    admin_users: int
    new_users_7d: int
    total_conversations: int
    total_messages: int
    active_sessions: int
    sessions_created_24h: int
    auth_events_24h: int
    failed_logins_24h: int
    usage: list[UsageBucket]


class AdminEventFeed(APIModel):
    items: list[AuthEventRead]
    total: int
    limit: int
    offset: int
    counts_by_type: dict[str, int]


class AdminSystemHealth(APIModel):
    status: str
    environment: str
    version: str
    database: str
    database_dialect: str
    supabase: str
    ai_provider: str
    auth_secret_configured: bool
    cookie_secure: bool
    cookie_samesite: str
    access_token_minutes: int
    refresh_token_days: int
    password_hashing: str
    mail_configured: bool
    checked_at: EpochMillis


__all__ = [
    "AdminEventFeed",
    "AdminSystemHealth",
    "AdminUsage",
    "AdminUserRead",
    "AdminUserUpdate",
    "AuthEventRead",
    "AuthSessionRead",
    "AuthState",
    "ChangePasswordRequest",
    "ForgotPasswordRequest",
    "ForgotPasswordResponse",
    "LoginRequest",
    "MessageResponse",
    "PreferencesRead",
    "PreferencesUpdate",
    "ProfileUpdate",
    "RegisterRequest",
    "ResetPasswordRequest",
    "UsageBucket",
    "UserRead",
    "normalise_email",
]
