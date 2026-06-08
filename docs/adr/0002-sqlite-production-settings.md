# ADR 0002: SQLite Production-Minded Settings

SQLite is enough for this capstone because the crawler is local, bounded, and single-process by default.

The database enables WAL mode, foreign keys, a busy timeout, idempotent inserts, and explicit frontier states, and it tracks a schema version (`PRAGMA user_version`) so startup can apply migrations. On startup, interrupted `in_progress` rows are recovered to `pending`, which makes resume behavior testable.

PostgreSQL or a queue-backed design would be appropriate for distributed crawling.
