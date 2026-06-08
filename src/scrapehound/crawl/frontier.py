"""Frontier state names."""

PENDING = "pending"
IN_PROGRESS = "in_progress"
FETCHED = "fetched"
SKIPPED = "skipped"
FAILED = "failed"
RETRY_SCHEDULED = "retry_scheduled"

ALL_STATES = {PENDING, IN_PROGRESS, FETCHED, SKIPPED, FAILED, RETRY_SCHEDULED}
