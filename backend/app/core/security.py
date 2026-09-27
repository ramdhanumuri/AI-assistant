"""Cryptographic primitives for authentication (MODULE 4).

Everything security-critical lives here so there is exactly one place to
review: password hashing, access-token signing, opaque-token generation and
the hashing of secrets at rest.

Two rules the rest of the codebase relies on:

* **Passwords are hashed with Argon2id** (RFC 9106's recommended password
  hashing function, winner of the Password Hashing Competition). Argon2 embeds
  a per-hash random salt and its own cost parameters in the encoded digest, so
  no salt column is needed and raising the work factor later does not
  invalidate existing hashes.
* **Long-lived secrets are never stored in the clear.** Refresh tokens and
  password-reset tokens are 256 bits of CSPRNG output, so a plain SHA-256
  digest is the right at-rest representation — there is no low-entropy
  dictionary to brute-force, and unlike a password hash a digest keeps the
  lookup indexable.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import (
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Password hashing ──────────────────────────────────────────────────

# Constructed once per process: `PasswordHasher` is thread-safe and rebuilding
# it per call would re-derive nothing useful but does allocate.
_hasher = PasswordHasher(
    time_cost=settings.PASSWORD_HASH_TIME_COST,
    memory_cost=settings.PASSWORD_HASH_MEMORY_KIB,
    parallelism=settings.PASSWORD_HASH_PARALLELISM,
    hash_len=32,
    salt_len=16,
)

# Length ceilings exist to bound work, not to enforce policy. 128 characters is
# far beyond any real passphrase and stops a megabyte body being fed to Argon2.
PASSWORD_MIN_LENGTH = 10
PASSWORD_MAX_LENGTH = 128

# A small deny-list of the passwords that dominate credential-stuffing corpora.
# Checked case-insensitively as a substring so "Password123!" is still refused.
# A production deployment should back this with a real breached-password
# service (see the Step 5 limitations in the README).
_COMMON_PASSWORDS = frozenset(
    {
        "password",
        "passw0rd",
        "qwerty",
        "qwertyuiop",
        "letmein",
        "welcome",
        "admin",
        "administrator",
        "iloveyou",
        "monkey",
        "dragon",
        "sunshine",
        "princess",
        "football",
        "baseball",
        "superman",
        "trustno1",
        "master",
        "shadow",
        "michael",
        "changeme",
        "secret",
        "aurelis",
        "1q2w3e4r",
        "zaq12wsx",
        "abc123",
        "123456",
        "1234567890",
    }
)

# Four classes; a password must draw on at least two. This accepts a real
# passphrase ("correct horse battery staple" is lower + symbol) while rejecting
# single-class strings like "aaaaaaaaaa" or "1234567890".
_CHARACTER_CLASSES = (
    ("lowercase", lambda c: c.islower()),
    ("uppercase", lambda c: c.isupper()),
    ("digit", lambda c: c.isdigit()),
    ("symbol", lambda c: not c.isalnum()),
)


def validate_password_strength(password: str) -> list[str]:
    """Return the policy violations for `password`; empty means acceptable.

    Returning every problem at once (rather than raising on the first) lets the
    registration form explain the whole requirement in one response.
    """
    problems: list[str] = []

    if len(password) < PASSWORD_MIN_LENGTH:
        problems.append(f"Password must be at least {PASSWORD_MIN_LENGTH} characters.")
    if len(password) > PASSWORD_MAX_LENGTH:
        problems.append(f"Password must be at most {PASSWORD_MAX_LENGTH} characters.")

    # Normalise before the class check so a Cyrillic "а" cannot impersonate a
    # Latin "a" in a deny-list comparison.
    normalised = unicodedata.normalize("NFKC", password)
    lowered = normalised.lower()

    classes = sum(1 for _, test in _CHARACTER_CLASSES if any(test(c) for c in normalised))
    if classes < 2:
        problems.append(
            "Password must combine at least two of: lowercase, uppercase, digits, symbols."
        )

    if any(common in lowered for common in _COMMON_PASSWORDS):
        problems.append("Password is too common; choose something less predictable.")

    if len(set(normalised)) < 4:
        problems.append("Password repeats too few distinct characters.")

    return problems


def hash_password(password: str) -> str:
    """Argon2id hash, salted and parameterised per call."""
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Constant-time-ish verification through Argon2.

    Any failure (mismatch, or a stored value that is not a valid Argon2 digest)
    is reported as "not verified" rather than raised, so a corrupt row cannot
    turn a login attempt into a 500.
    """
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    except Exception:  # noqa: BLE001  (never let hashing break the auth flow)
        logger.warning("Unexpected error verifying a password hash")
        return False


def needs_rehash(password_hash: str) -> bool:
    """True when a stored hash was produced with weaker parameters than today's."""
    try:
        return _hasher.check_needs_rehash(password_hash)
    except Exception:  # noqa: BLE001
        return True


# ── Opaque tokens ─────────────────────────────────────────────────────

TOKEN_BYTES = 32  # 256 bits of entropy


def generate_opaque_token() -> str:
    """A URL-safe secret used for refresh and password-reset tokens."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(token: str) -> str:
    """SHA-256 hex digest of an opaque token, for at-rest storage.

    Not a password hash on purpose: the input is already full-entropy random,
    so key stretching buys nothing, and a fast digest keeps the unique index on
    `auth_sessions.token_hash` usable for lookups.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def tokens_equal(left: str, right: str) -> bool:
    """Timing-safe comparison for two token digests."""
    return hmac.compare_digest(left, right)


def hash_identifier(value: str) -> str:
    """Keyed digest for low-entropy identifiers (email, IP) in the audit log.

    Plain SHA-256 would be reversible by brute force for an email address, so
    the value is keyed with AUTH_SECRET: the log stays correlatable across
    events without storing the identifier itself.
    """
    digest = hmac.new(
        settings.AUTH_SECRET.encode("utf-8"),
        value.strip().lower().encode("utf-8"),
        hashlib.sha256,
    )
    return digest.hexdigest()


# ── Access tokens ─────────────────────────────────────────────────────

ACCESS_TOKEN_TYPE = "access"
_JWT_ALGORITHM = "HS256"


def create_access_token(
    *,
    user_id: str,
    session_id: str,
    now: datetime | None = None,
    expires_minutes: int | None = None,
) -> tuple[str, datetime]:
    """Mint a short-lived access token.

    Claims are deliberately minimal — subject, session, issued-at, expiry and a
    unique id. No email, name or role: the role is read from the database on
    every request so a revoked or downgraded account takes effect immediately
    rather than at token expiry.
    """
    issued = now or datetime.now(timezone.utc)
    ttl = timedelta(
        minutes=expires_minutes
        if expires_minutes is not None
        else settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    expires_at = issued + ttl

    payload: dict[str, Any] = {
        "sub": user_id,
        "sid": session_id,
        "typ": ACCESS_TOKEN_TYPE,
        "jti": secrets.token_urlsafe(12),
        "iat": int(issued.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(payload, settings.AUTH_SECRET, algorithm=_JWT_ALGORITHM)
    return token, expires_at


class AccessTokenError(Exception):
    """Raised when an access token is missing, malformed, or no longer valid."""

    def __init__(self, message: str, *, expired: bool = False) -> None:
        super().__init__(message)
        self.message = message
        self.expired = expired


def decode_access_token(token: str) -> dict[str, Any]:
    """Validate signature and expiry, then return the claims.

    Raises `AccessTokenError` with `expired=True` for an expired token so the
    caller can answer with a distinguishable 401 and the client can attempt one
    refresh instead of dropping the session.
    """
    try:
        claims = jwt.decode(
            token,
            settings.AUTH_SECRET,
            algorithms=[_JWT_ALGORITHM],
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AccessTokenError("Authentication token has expired.", expired=True) from exc
    except jwt.InvalidTokenError as exc:
        raise AccessTokenError("Authentication token is invalid.") from exc

    if claims.get("typ") != ACCESS_TOKEN_TYPE:
        raise AccessTokenError("Authentication token is invalid.")
    if not claims.get("sid"):
        raise AccessTokenError("Authentication token is invalid.")
    return claims


__all__ = [
    "ACCESS_TOKEN_TYPE",
    "AccessTokenError",
    "PASSWORD_MAX_LENGTH",
    "PASSWORD_MIN_LENGTH",
    "TOKEN_BYTES",
    "create_access_token",
    "decode_access_token",
    "generate_opaque_token",
    "hash_identifier",
    "hash_password",
    "hash_token",
    "needs_rehash",
    "tokens_equal",
    "validate_password_strength",
    "verify_password",
]
