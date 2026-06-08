"""Repository methods hiding SQL details from the crawl engine."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass
from typing import Any

from scrapehound.crawl import frontier as states
from scrapehound.crawl.normalize import normalize_url
from scrapehound.models import FetchResult, ParsedPage
from scrapehound.storage.db import connect, init_db


@dataclass(slots=True)
class FrontierItem:
    id: int
    job_id: int
    url: str
    normalized_url: str
    depth: int
    status: str
    retry_count: int


class Storage:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = connect(db_path)
        init_db(self.conn)

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> Storage:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def create_job(self, seed_url: str, max_pages: int, max_depth: int) -> int:
        with self.conn:
            cursor = self.conn.execute(
                "INSERT INTO crawl_jobs(seed_url, max_pages, max_depth) VALUES (?, ?, ?)",
                (seed_url, max_pages, max_depth),
            )
        return int(cursor.lastrowid)

    def get_job(self, job_id: int) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM crawl_jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None

    def finish_job(self, job_id: int, status: str = "finished") -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE crawl_jobs SET status = ?, finished_at = datetime('now') WHERE id = ?",
                (status, job_id),
            )

    def recover_in_progress(self, job_id: int) -> int:
        with self.conn:
            cursor = self.conn.execute(
                """
                UPDATE frontier
                SET status = ?, updated_at = datetime('now')
                WHERE job_id = ? AND status = ?
                """,
                (states.PENDING, job_id, states.IN_PROGRESS),
            )
        return cursor.rowcount

    def enqueue_url(self, job_id: int, url: str, depth: int, discovered_from: str | None = None) -> int | None:
        try:
            normalized = normalize_url(url)
        except ValueError:
            # A malformed discovered link must not abort the whole crawl.
            return None
        with self.conn:
            # The frontier's UNIQUE(job_id, normalized_url) is the dedup key:
            # a URL already enqueued (in any state) is ignored on re-discovery.
            cursor = self.conn.execute(
                """
                INSERT OR IGNORE INTO frontier(job_id, url, normalized_url, depth, status, discovered_from)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (job_id, url, normalized, depth, states.PENDING, discovered_from),
            )
        if cursor.rowcount == 0:
            return None
        return int(cursor.lastrowid)

    def next_frontier_item(self, job_id: int) -> FrontierItem | None:
        now = time.time()
        row = self.conn.execute(
            """
            SELECT * FROM frontier
            WHERE job_id = ?
              AND status IN (?, ?)
              AND next_fetch_at <= ?
            ORDER BY depth ASC, id ASC
            LIMIT 1
            """,
            (job_id, states.PENDING, states.RETRY_SCHEDULED, now),
        ).fetchone()
        if row is None:
            return None
        return _frontier_item(row)

    def has_pending_work(self, job_id: int) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM frontier WHERE job_id = ? AND status IN (?, ?) LIMIT 1",
            (job_id, states.PENDING, states.RETRY_SCHEDULED),
        ).fetchone()
        return row is not None

    def seconds_until_next(self, job_id: int) -> float | None:
        row = self.conn.execute(
            """
            SELECT MIN(next_fetch_at) AS next_fetch_at
            FROM frontier
            WHERE job_id = ? AND status IN (?, ?)
            """,
            (job_id, states.PENDING, states.RETRY_SCHEDULED),
        ).fetchone()
        if row is None or row["next_fetch_at"] is None:
            return None
        return max(0.0, float(row["next_fetch_at"]) - time.time())

    def mark_in_progress(self, frontier_id: int) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE frontier SET status = ?, updated_at = datetime('now') WHERE id = ?",
                (states.IN_PROGRESS, frontier_id),
            )

    def mark_fetched(self, frontier_id: int) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE frontier SET status = ?, updated_at = datetime('now') WHERE id = ?",
                (states.FETCHED, frontier_id),
            )

    def mark_skipped(self, frontier_id: int) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE frontier SET status = ?, updated_at = datetime('now') WHERE id = ?",
                (states.SKIPPED, frontier_id),
            )

    def mark_failed(self, frontier_id: int) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE frontier SET status = ?, updated_at = datetime('now') WHERE id = ?",
                (states.FAILED, frontier_id),
            )

    def schedule_retry(self, frontier_id: int, retry_count: int, delay_seconds: float) -> None:
        with self.conn:
            self.conn.execute(
                """
                UPDATE frontier
                SET status = ?, retry_count = ?, next_fetch_at = ?, updated_at = datetime('now')
                WHERE id = ?
                """,
                (
                    states.RETRY_SCHEDULED,
                    retry_count,
                    time.time() + delay_seconds,
                    frontier_id,
                ),
            )

    def save_page(
        self,
        job_id: int,
        item: FrontierItem,
        result: FetchResult,
        parsed: ParsedPage,
        body_text: str,
    ) -> None:
        normalized = normalize_url(result.final_url)
        content_type = _header(result.headers, "Content-Type") or ""
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO pages(
                  job_id, url, final_url, normalized_url, status_code, content_type,
                  title, description, headings_json, links_json, body_sha256, body_text,
                  text_encoding, timing_json, transport, depth
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id, normalized_url) DO UPDATE SET
                  url = excluded.url,
                  final_url = excluded.final_url,
                  status_code = excluded.status_code,
                  content_type = excluded.content_type,
                  title = excluded.title,
                  description = excluded.description,
                  headings_json = excluded.headings_json,
                  links_json = excluded.links_json,
                  body_sha256 = excluded.body_sha256,
                  body_text = excluded.body_text,
                  text_encoding = excluded.text_encoding,
                  timing_json = excluded.timing_json,
                  transport = excluded.transport,
                  depth = excluded.depth,
                  fetched_at = datetime('now')
                """,
                (
                    job_id,
                    item.url,
                    result.final_url,
                    normalized,
                    result.status_code or 0,
                    content_type,
                    parsed.title,
                    parsed.description,
                    json.dumps(parsed.headings),
                    json.dumps(parsed.links),
                    hashlib.sha256(result.body).hexdigest(),
                    body_text,
                    parsed.text_encoding,
                    json.dumps(result.timings.as_dict()),
                    result.transport,
                    item.depth,
                ),
            )

    def save_failure(
        self,
        job_id: int,
        url: str,
        category: str,
        message: str | None = None,
        *,
        status_code: int | None = None,
        retry_count: int = 0,
    ) -> None:
        try:
            normalized = normalize_url(url)
        except ValueError:
            normalized = None
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO failures(job_id, url, normalized_url, category, message, status_code, retry_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (job_id, url, normalized, category, message, status_code, retry_count),
            )

    def stats(self, job_id: int | None = None) -> dict[str, Any]:
        params: tuple[Any, ...] = (job_id,) if job_id is not None else ()
        suffix = "WHERE job_id = ?" if job_id is not None else ""
        status_rows = self.conn.execute(
            f"SELECT status, COUNT(*) AS count FROM frontier {suffix} GROUP BY status",
            params,
        ).fetchall()
        page_count = self.conn.execute(f"SELECT COUNT(*) AS count FROM pages {suffix}", params).fetchone()["count"]
        failure_count = self.conn.execute(f"SELECT COUNT(*) AS count FROM failures {suffix}", params).fetchone()[
            "count"
        ]
        return {
            "frontier": {row["status"]: row["count"] for row in status_rows},
            "pages": page_count,
            "failures": failure_count,
        }

    def export_json(self, job_id: int | None = None) -> dict[str, Any]:
        params: tuple[Any, ...] = (job_id,) if job_id is not None else ()
        suffix = "WHERE job_id = ?" if job_id is not None else ""
        pages = [
            _dict_with_json(row, ("headings_json", "links_json", "timing_json"))
            for row in self.conn.execute(f"SELECT * FROM pages {suffix}", params)
        ]
        failures = [dict(row) for row in self.conn.execute(f"SELECT * FROM failures {suffix}", params)]
        return {"pages": pages, "failures": failures, "stats": self.stats(job_id)}

    def latest_job_id(self) -> int | None:
        row = self.conn.execute("SELECT id FROM crawl_jobs ORDER BY id DESC LIMIT 1").fetchone()
        return int(row["id"]) if row else None


def _frontier_item(row: sqlite3.Row) -> FrontierItem:
    return FrontierItem(
        id=int(row["id"]),
        job_id=int(row["job_id"]),
        url=row["url"],
        normalized_url=row["normalized_url"],
        depth=int(row["depth"]),
        status=row["status"],
        retry_count=int(row["retry_count"]),
    )


def _dict_with_json(row: sqlite3.Row, json_fields: tuple[str, ...]) -> dict[str, Any]:
    data = dict(row)
    for field in json_fields:
        value = data.pop(field, None)
        key = field.removesuffix("_json")
        # timing is an object; headings/links are arrays.
        default: Any = {} if key == "timing" else []
        data[key] = json.loads(value) if value else default
    return data


def _header(headers: dict[str, str], name: str) -> str | None:
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return None
