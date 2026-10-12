"""In-process sliding-window rate limiter for login attempts."""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock


class SlidingWindowRateLimiter:
    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            hits = [ts for ts in self._hits[key] if ts >= cutoff]
            if len(hits) >= self.max_attempts:
                self._hits[key] = hits
                return False
            hits.append(now)
            self._hits[key] = hits
            return True

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)


_login_limiter: SlidingWindowRateLimiter | None = None


def get_login_limiter() -> SlidingWindowRateLimiter:
    global _login_limiter
    if _login_limiter is None:
        from app.config import get_settings

        settings = get_settings()
        _login_limiter = SlidingWindowRateLimiter(
            max_attempts=settings.LOGIN_RATE_LIMIT_ATTEMPTS,
            window_seconds=settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS,
        )
    return _login_limiter
