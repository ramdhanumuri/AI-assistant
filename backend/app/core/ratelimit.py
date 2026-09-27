"""Request throttling with a shared-state option.

Two implementations behind one interface:

* `RedisRateLimiter` — counters live in Redis, so every worker shares one
  budget. This is the production control: with the in-process limiter, N
  workers each allow the full rate and an attacker gets N× by spreading
  requests. Enable it by setting `REDIS_URL`.
* `InProcessRateLimiter` — the same sliding-window algorithm in local memory.
  Correct for a single worker and for tests; a documented degrade-only for a
  multi-worker deployment without Redis.

The window is deliberately not aggressive: it caps a burst without permanently
locking a legitimate user, and account-level lockout (in `AuthService`) is the
slower, coarser control on top. Budgets are per-scope so exhausting login
attempts cannot block registration, and every budget is environment-tunable.

The Redis path is imported lazily and falls back to in-process if the `redis`
package is missing or the server is unreachable at startup, so a Redis outage
degrades throttling rather than taking authentication down with it. Callers can
read `active_backend()` to see which control is in force.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Evict empty buckets once the table grows past this, so a distributed attack
# with unique keys cannot exhaust memory.
_MAX_TRACKED_KEYS = 10_000

# Scopes whose budget is the authentication window. Everything here is a
# credential-guessing or account-enumeration surface.
AUTH_SCOPES = frozenset({"login", "register", "refresh", "password-reset"})

# Non-authentication budgets, in (max_events, window_seconds). Kept realistic:
# a human using the product never approaches these, but a script does.
_GENERAL_SCOPES: dict[str, tuple[int, int]] = {
    "api": (600, 60),
    "ai": (60, 60),
    "write": (120, 60),
    "search": (120, 60),
    "admin": (240, 60),
    "upload": (20, 3600),
}


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after_seconds: int


def scoped_limit(scope: str) -> tuple[int, int]:
    """(max_events, window_seconds) for a scope, read at call time.

    Read on every check (rather than cached) so a settings change — including a
    test's monkeypatch — takes effect without a restart.
    """
    if scope in AUTH_SCOPES:
        return settings.AUTH_RATE_LIMIT_ATTEMPTS, settings.AUTH_RATE_LIMIT_WINDOW_SECONDS
    if scope in _GENERAL_SCOPES:
        return _GENERAL_SCOPES[scope]
    return settings.GENERAL_RATE_LIMIT_ATTEMPTS, settings.GENERAL_RATE_LIMIT_WINDOW_SECONDS


class SlidingWindowLimiter:
    """Counts events per key inside a rolling time window (local memory)."""

    def __init__(self, *, max_events: int, window_seconds: int) -> None:
        self.max_events = max_events
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str, *, now: float | None = None) -> RateLimitResult:
        moment = now if now is not None else time.monotonic()
        cutoff = moment - self.window_seconds

        with self._lock:
            if len(self._events) > _MAX_TRACKED_KEYS:
                self._evict(cutoff)

            bucket = self._events.setdefault(key, deque())
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= self.max_events:
                oldest = bucket[0]
                retry_after = max(1, int(oldest + self.window_seconds - moment) + 1)
                return RateLimitResult(False, 0, retry_after)

            bucket.append(moment)
            return RateLimitResult(True, self.max_events - len(bucket), 0)

    def reset(self, key: str) -> None:
        with self._lock:
            self._events.pop(key, None)

    def _evict(self, cutoff: float) -> None:
        stale = [key for key, bucket in self._events.items() if not bucket or bucket[-1] <= cutoff]
        for key in stale:
            self._events.pop(key, None)
        if len(self._events) > _MAX_TRACKED_KEYS:
            # Still oversized (a burst of fresh keys): drop the oldest half.
            logger.warning("Rate-limit table oversized; evicting oldest buckets")
            for key in list(self._events)[: len(self._events) // 2]:
                self._events.pop(key, None)


class InProcessRateLimiter:
    """Scope-aware wrapper around one `SlidingWindowLimiter` per scope."""

    def __init__(self) -> None:
        self._limiters: dict[str, SlidingWindowLimiter] = {}

    def check(self, scope: str, key: str) -> RateLimitResult:
        max_events, window = scoped_limit(scope)
        limiter = self._limiters.get(scope)
        if (
            limiter is None
            or limiter.max_events != max_events
            or limiter.window_seconds != window
        ):
            # Rebuild when the configured budget changes (tests, or a reload).
            limiter = SlidingWindowLimiter(max_events=max_events, window_seconds=window)
            self._limiters[scope] = limiter
        return limiter.check(key)

    def reset(self) -> None:
        self._limiters.clear()


# Atomic "count this event in a rolling window" script. Runs server-side so two
# workers cannot interleave a read-modify-write and both admit the last slot.
_REDIS_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local cutoff = now - window
redis.call('ZREMRANGEBYSCORE', key, 0, cutoff)
local count = redis.call('ZCARD', key)
if count >= limit then
  local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
  local retry = window
  if oldest[2] then retry = math.ceil(tonumber(oldest[2]) + window - now) end
  if retry < 1 then retry = 1 end
  return {0, 0, retry}
end
redis.call('ZADD', key, now, tostring(now) .. ':' .. ARGV[4])
redis.call('EXPIRE', key, window)
return {1, limit - count - 1, 0}
"""


class RedisRateLimiter:
    """Sliding window backed by a Redis sorted set, one key per (scope, key)."""

    def __init__(self, client: object) -> None:
        self._client = client

    def check(self, scope: str, key: str) -> RateLimitResult:
        max_events, window = scoped_limit(scope)
        redis_key = f"aurelis:rl:{scope}:{key}"
        # A unique member per event keeps concurrent events from collapsing.
        member = f"{time.monotonic()}:{threading.get_ident()}"
        try:
            allowed, remaining, retry_after = self._client.eval(  # type: ignore[attr-defined]
                _REDIS_SCRIPT,
                1,
                redis_key,
                time.time(),
                window,
                max_events,
                member,
            )
        except Exception as exc:  # noqa: BLE001
            # A throttle that fails closed would turn a Redis blip into an
            # outage; fail open and log loudly instead.
            logger.error("Redis rate-limit check failed; allowing request: %s", exc)
            return RateLimitResult(True, max_events, 0)
        return RateLimitResult(bool(int(allowed)), int(remaining), int(retry_after))


def _try_build_redis_limiter() -> RedisRateLimiter | None:
    url = settings.REDIS_URL.strip()
    if not url:
        return None
    try:
        import redis  # type: ignore[import-not-found]
    except ImportError:
        logger.warning(
            "REDIS_URL is set but the 'redis' package is not installed; "
            "falling back to the in-process limiter (per-worker budgets)."
        )
        return None
    try:
        client = redis.Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1)
        client.ping()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not reach Redis at startup (%s); using in-process limiter", exc)
        return None
    logger.info("Distributed rate limiting enabled via Redis")
    return RedisRateLimiter(client)


# Built lazily so a test that overrides the settings gets a matching limiter.
_limiter: object | None = None
_in_process = InProcessRateLimiter()


def get_rate_limiter():
    global _limiter
    if _limiter is None:
        _limiter = _try_build_redis_limiter() or _in_process
    return _limiter


def active_backend() -> str:
    return type(get_rate_limiter()).__name__


def check_rate_limit(scope: str, key: str) -> RateLimitResult:
    return get_rate_limiter().check(scope, key)


def reset_limiter() -> None:
    """Drop all counters and re-select a backend. Used by tests and on reload."""
    global _limiter
    _limiter = None
    _in_process.reset()


__all__ = [
    "AUTH_SCOPES",
    "InProcessRateLimiter",
    "RateLimitResult",
    "RedisRateLimiter",
    "SlidingWindowLimiter",
    "active_backend",
    "check_rate_limit",
    "get_rate_limiter",
    "reset_limiter",
    "scoped_limit",
]
