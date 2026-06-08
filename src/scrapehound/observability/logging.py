"""Structured logging helper."""

from __future__ import annotations

import json
import sys
from typing import Any


def log_event(event: str, *, level: str = "info", **fields: Any) -> None:
    payload = {"event": event, "level": level, **fields}
    # Logs go to stderr so they never corrupt JSON written to stdout (e.g. export).
    # default=str keeps non-JSON-serializable values from raising.
    print(json.dumps(payload, sort_keys=True, default=str), file=sys.stderr)
