"""Stats helpers."""

from __future__ import annotations

from typing import Any

from scrapehound.storage.repositories import Storage


def load_stats(db_path: str, job_id: int | None = None) -> dict[str, Any]:
    with Storage(db_path) as storage:
        return storage.stats(job_id)
