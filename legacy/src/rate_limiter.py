"""Shared per-model rate limiting for API calls.

Free-tier Gemini quotas are per-model per-minute. This keeps bursts under
the observed limits for both embedding (100/min) and generation (lower).
"""

from __future__ import annotations

import time

# Conservative per-minute budgets (well under observed free-tier limits).
EMBEDDING_PER_MINUTE = 90
GENERATION_PER_MINUTE = 10
WINDOW_SECONDS = 60.0


class RateLimiter:
    """Spacing-based rate limiter that paces calls evenly to avoid bursts.

    Each call waits until at least `window / per_minute` seconds have passed
    since the previous call, so requests are spread smoothly over the window
    instead of being allowed to burst up to the budget.
    """

    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self._min_interval = WINDOW_SECONDS / max(per_minute, 1)
        self._last_call: float | None = None

    def acquire(self) -> None:
        now = time.monotonic()
        if self._last_call is not None:
            wait = self._min_interval - (now - self._last_call)
            if wait > 0:
                print(f"    [rate-limit] pacing {wait:.1f}s ({self.per_minute} req/min) ...")
                time.sleep(wait)
        self._last_call = time.monotonic()


_embedding_limiter = RateLimiter(EMBEDDING_PER_MINUTE)
_generation_limiters: dict[str, RateLimiter] = {}


def acquire_embedding() -> None:
    _embedding_limiter.acquire()


def acquire_generation(model: str) -> None:
    key = model or "default"
    limiter = _generation_limiters.get(key)
    if limiter is None:
        limiter = RateLimiter(GENERATION_PER_MINUTE)
        _generation_limiters[key] = limiter
    limiter.acquire()