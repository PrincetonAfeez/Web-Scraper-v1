"""Per-domain request limiter."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

_PRUNE_THRESHOLD = 1024


class RateLimiter:
    def __init__(
        self,
        *,
        now: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._now = now
        self._sleep = sleep
        self._lock = threading.Lock()
        self._next_allowed: dict[str, float] = {}
        self._paused_until: dict[str, float] = {}

    def wait(self, domain: str, min_delay_seconds: float) -> float:
        # Reserve the slot atomically, then sleep outside the lock so concurrent
        # workers on different domains do not serialize on each other.
        with self._lock:
            now = self._now()
            self._prune(now)
            next_allowed = max(self._next_allowed.get(domain, 0.0), self._paused_until.get(domain, 0.0))
            start = max(now, next_allowed)
            self._next_allowed[domain] = start + min_delay_seconds
            waited = max(0.0, start - now)
        if waited > 0:
            self._sleep(waited)
        return waited

    def pause(self, domain: str, seconds: float) -> None:
        with self._lock:
            self._paused_until[domain] = max(self._paused_until.get(domain, 0.0), self._now() + seconds)

    def _prune(self, now: float) -> None:
        # Drop entries whose timestamps have elapsed; they no longer constrain
        # anything, so this bounds memory over long, many-domain crawls.
        if len(self._next_allowed) > _PRUNE_THRESHOLD:
            self._next_allowed = {domain: at for domain, at in self._next_allowed.items() if at > now}
        if len(self._paused_until) > _PRUNE_THRESHOLD:
            self._paused_until = {domain: at for domain, at in self._paused_until.items() if at > now}
