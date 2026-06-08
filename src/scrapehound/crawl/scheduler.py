"""Synchronous scheduling facade over the rate limiter.

The engine drives politeness through this object so that per-domain pacing and
back-off live behind one seam (per the capstone architecture).
"""

from __future__ import annotations

from scrapehound.politeness.rate_limit import RateLimiter


class Scheduler:
    def __init__(self, limiter: RateLimiter):
        self.limiter = limiter

    def wait_for_domain(self, domain: str, delay_seconds: float) -> float:
        return self.limiter.wait(domain, delay_seconds)

    def pause_domain(self, domain: str, seconds: float) -> None:
        self.limiter.pause(domain, seconds)
