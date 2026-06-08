"""Unit test for retry."""

from __future__ import annotations

from scrapehound.crawl.retry import RetryPolicy, parse_retry_after


def test_retry_policy_retries_429_with_budget():
    policy = RetryPolicy(max_retries=2, jitter=0)

    assert policy.should_retry(status_code=429, category=None, retry_count=0)
    assert not policy.should_retry(status_code=429, category=None, retry_count=2)


def test_parse_retry_after_seconds():
    assert parse_retry_after("3") == 3.0
