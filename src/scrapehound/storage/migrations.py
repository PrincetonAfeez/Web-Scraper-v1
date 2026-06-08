"""Schema versioning for this capstone-scale SQLite project.

The base schema (version 1) lives in ``schema.sql`` and is applied to a fresh
database. Later schema changes are expressed as incremental migration steps
keyed by the version they produce; ``db.init_db`` stamps ``PRAGMA user_version``
and applies any pending steps in order.
"""

from __future__ import annotations

SCHEMA_VERSION = 2

# version N -> SQL statements that upgrade a database from version N-1 to N.
# Version 1 is the base schema (schema.sql), so it has no incremental step.
INCREMENTAL_MIGRATIONS: dict[int, list[str]] = {
    # v2: the seen_urls and robots_cache tables were retired. Fresh databases
    # never create them; this drops them from databases built before v2.
    2: [
        "DROP TABLE IF EXISTS seen_urls",
        "DROP TABLE IF EXISTS robots_cache",
    ],
}


def pending_migrations(from_version: int) -> list[tuple[int, list[str]]]:
    return [
        (version, INCREMENTAL_MIGRATIONS[version])
        for version in range(from_version + 1, SCHEMA_VERSION + 1)
        if version in INCREMENTAL_MIGRATIONS
    ]
