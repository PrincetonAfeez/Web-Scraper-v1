"""Unit test for rate limit."""

from __future__ import annotations

from scrapehound.politeness.rate_limit import RateLimiter


def test_rate_limiter_spaces_same_domain_requests():
    now = [0.0]
    sleeps: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        now[0] += seconds

    limiter = RateLimiter(now=lambda: now[0], sleep=fake_sleep)

    assert limiter.wait("example.com", 1.0) == 0.0
    waited = limiter.wait("example.com", 1.0)

    assert waited == 1.0
    assert sleeps == [1.0]


def test_retry_after_pause_delays_domain():
    now = [10.0]
    sleeps: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        now[0] += seconds

    limiter = RateLimiter(now=lambda: now[0], sleep=fake_sleep)
    limiter.pause("example.com", 5.0)

    assert limiter.wait("example.com", 0.0) == 5.0
