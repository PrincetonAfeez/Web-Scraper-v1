"""Timing helper."""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def elapsed() -> Iterator[dict[str, float]]:
    start = time.perf_counter()
    result = {"seconds": 0.0}
    try:
        yield result
    finally:
        result["seconds"] = time.perf_counter() - start
