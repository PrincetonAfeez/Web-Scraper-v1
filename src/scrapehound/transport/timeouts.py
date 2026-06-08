"""Small helpers for total timeout accounting."""

from __future__ import annotations

import time

from scrapehound.exceptions import FetchError


class Deadline:
    def __init__(self, seconds: float):
        self.expires_at = time.monotonic() + seconds

    def remaining(self) -> float:
        remaining = self.expires_at - time.monotonic()
        if remaining <= 0:
            raise FetchError("total_timeout", "total request timeout elapsed")
        return remaining

    def cap(self, seconds: float) -> float:
        return max(0.001, min(seconds, self.remaining()))
