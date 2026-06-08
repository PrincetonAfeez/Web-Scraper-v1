"""Retry policy and Retry-After parsing."""

from __future__ import annotations

import email.utils
import random
from dataclasses import dataclass
from datetime import UTC, datetime

RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}
RETRYABLE_CATEGORIES = {
    "dns_error",
    "connect_timeout",
    "connection_error",
    "read_timeout",
    "total_timeout",
    "server_error",
    "rate_limited",
}


@dataclass(slots=True)
class RetryPolicy:
    max_retries: int = 2
    base_delay: float = 1.0
    max_delay: float = 60.0
    jitter: float = 0.1

    def should_retry(self, *, status_code: int | None, category: str | None, retry_count: int) -> bool:
        if retry_count >= self.max_retries:
            return False
        if status_code in RETRYABLE_STATUS:
            return True
        if category in RETRYABLE_CATEGORIES:
            return True
        return False

    def delay_seconds(self, retry_count: int, retry_after: str | None = None) -> float:
        parsed = parse_retry_after(retry_after)
        if parsed is not None:
            return parsed
        base = min(self.max_delay, self.base_delay * (2**retry_count))
        return base + random.uniform(0, self.jitter)


def parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return float(value)
    try:
        dt = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return max(0.0, (dt - datetime.now(UTC)).total_seconds())
