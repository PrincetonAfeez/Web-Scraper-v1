"""Structured logging helper."""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def log_event(event: str, *, level: str = "info", **fields: Any) -> None:
    payload = {"event": event, "level": level, **fields}
    message = json.dumps(payload, sort_keys=True, default=str)
    log_fn = getattr(logger, level.lower(), logger.info)
    log_fn(message)
