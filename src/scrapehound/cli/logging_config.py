"""CLI-only logging configuration for trace diagnostics."""

from __future__ import annotations

import logging
import sys


def configure_trace_logging() -> None:
    """Enable DEBUG logging on stderr when --trace is passed."""
    root = logging.getLogger()
    if root.handlers:
        root.setLevel(logging.DEBUG)
        return
    logging.basicConfig(level=logging.DEBUG, format="%(message)s", stream=sys.stderr)
