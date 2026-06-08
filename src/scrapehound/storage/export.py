"""Export helpers."""

from __future__ import annotations

import json

from scrapehound.storage.repositories import Storage


def export_json(storage: Storage, job_id: int | None = None) -> str:
    return json.dumps(storage.export_json(job_id), indent=2, sort_keys=True)
