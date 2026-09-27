"""In-process request throttling.

This is the *foundation* the brief asks for, not the finished control. A
process-local sliding window is enough to stop a single attacker hammering one
worker, and it is honest about its limits:

* State is per-process, so N workers allow N× the configured rate. A real
  deployment puts the same window in Redis (or an edge WAF) and leaves this
  interface unchanged.
* Memory is bounded by evicting stale buckets on write, so a spray of unique
  keys cannot grow the dict without limit.

The window is deliberately not aggressive: it caps a burst without permanently
locking a legitimate user, and account-level lockout (in `AuthService`) is the
slower, coarser control on top.
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


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after_seconds: int


class SlidingWindowLimiter:
    """Counts events per key inside a rolling time window."""

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


def _build_limiter() -> SlidingWindowLimiter:
    return SlidingWindowLimiter(
        max_events=settings.AUTH_RATE_LIMIT_ATTEMPTS,
        window_seconds=settings.AUTH_RATE_LIMIT_WINDOW_SECONDS,
    )


# Built lazily so a test that overrides the settings gets a matching limiter.
_limiter: SlidingWindowLimiter | None = None


def get_limiter() -> SlidingWindowLimiter:
    global _limiter
    if _limiter is None:
        _limiter = _build_limiter()
    return _limiter


def reset_limiter() -> None:
    """Drop all counters. Used by tests and after a settings change."""
    global _limiter
    _limiter = None


__all__ = ["RateLimitResult", "SlidingWindowLimiter", "get_limiter", "reset_limiter"]
