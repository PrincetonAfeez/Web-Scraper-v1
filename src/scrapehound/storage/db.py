"""SQLite connection and schema helpers."""

from __future__ import annotations

import sqlite3 
from pathlib import Path

from scrapehound.storage.migrations import SCHEMA_VERSION, pending_migrations


def connect(path: str) -> sqlite3.Connection:
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False lets AsyncCrawlEngine run a crawl in a worker
    # thread against a connection created on the main thread. The single
    # connection still serializes operations; it is not a multi-writer pool.
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version >= SCHEMA_VERSION:
        return
    if version == 0:
        schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
        conn.executescript(schema)
    for _version, statements in pending_migrations(version):
        for statement in statements:
            conn.execute(statement)
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    conn.commit()
