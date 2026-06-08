"""Unit test for storage."""

from __future__ import annotations

import hashlib
import sqlite3

import pytest

from scrapehound.cli.exit_codes import ERROR, OK
from scrapehound.cli.main import main
from scrapehound.models import FetchResult, ParsedPage, TimingBreakdown
from scrapehound.storage.repositories import Storage


def _seed(tmp_path):
    storage = Storage(str(tmp_path / "s.sqlite"))
    job_id = storage.create_job("http://e.com/", 10, 1)
    storage.enqueue_url(job_id, "http://e.com/p", 0)
    item = storage.next_frontier_item(job_id)
    return storage, job_id, item


def _result():
    return FetchResult(
        url="http://e.com/p",
        final_url="http://e.com/p",
        status_code=200,
        reason="OK",
        headers={"Content-Type": "text/html"},
        body=b"<html>",
        timings=TimingBreakdown(),
    )


def _page(title):
    return ParsedPage(
        final_url="http://e.com/p",
        title=title,
        description=None,
        headings=[],
        links=[],
        text_encoding="utf-8",
    )


def test_save_page_upserts_in_place_without_rowid_churn(tmp_path):
    storage, job_id, item = _seed(tmp_path)
    storage.save_page(job_id, item, _result(), _page("First"), "body1")
    first_id = storage.conn.execute("SELECT id FROM pages WHERE normalized_url = ?", ("http://e.com/p",)).fetchone()[
        "id"
    ]

    storage.save_page(job_id, item, _result(), _page("Second"), "body2")
    row = storage.conn.execute("SELECT id, title FROM pages WHERE normalized_url = ?", ("http://e.com/p",)).fetchone()

    assert row["id"] == first_id  # rowid preserved (no delete+insert)
    assert row["title"] == "Second"  # row updated in place
    assert storage.stats(job_id)["pages"] == 1


def test_frontier_status_check_constraint(tmp_path):
    storage, _job_id, item = _seed(tmp_path)
    with pytest.raises(sqlite3.IntegrityError):
        with storage.conn:
            storage.conn.execute("UPDATE frontier SET status = ? WHERE id = ?", ("bogus", item.id))


def test_storage_context_manager_closes_connection(tmp_path):
    with Storage(str(tmp_path / "s.sqlite")) as storage:
        storage.create_job("http://e.com/", 1, 1)
    with pytest.raises(sqlite3.ProgrammingError):
        storage.conn.execute("SELECT 1")


def test_schema_is_versioned_and_drops_dead_tables(tmp_path):
    from scrapehound.storage.migrations import SCHEMA_VERSION

    storage = Storage(str(tmp_path / "s.sqlite"))
    assert storage.conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    names = {row["name"] for row in storage.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "seen_urls" not in names
    assert "robots_cache" not in names
    storage.close()


def test_enqueue_dedupes_via_frontier(tmp_path):
    storage = Storage(str(tmp_path / "s.sqlite"))
    job_id = storage.create_job("http://e.com/", 10, 1)
    assert storage.enqueue_url(job_id, "http://e.com/p", 0) is not None
    # Same normalized URL on re-discovery is ignored (no seen_urls table needed).
    assert storage.enqueue_url(job_id, "http://e.com/p", 0) is None
    storage.close()


def test_verify_pages_reports_valid_and_mismatch(tmp_path):
    storage, job_id, item = _seed(tmp_path)
    storage.save_page(job_id, item, _result(), _page("OK"), "stored body")
    report = storage.verify_pages(job_id)
    assert report["total"] == 1
    assert len(report["valid"]) == 1
    assert report["mismatches"] == []
    assert report["missing"] == []

    with storage.conn:
        storage.conn.execute(
            "UPDATE pages SET body_sha256 = ? WHERE job_id = ?",
            ("0" * 64, job_id),
        )
    report = storage.verify_pages(job_id)
    assert report["mismatches"][0]["url"] == "http://e.com/p"
    storage.close()


def _seed_at(db_path):
    storage = Storage(str(db_path))
    job_id = storage.create_job("http://e.com/", 10, 1)
    storage.enqueue_url(job_id, "http://e.com/p", 0)
    item = storage.next_frontier_item(job_id)
    return storage, job_id, item


def test_verify_cli_exits_nonzero_on_mismatch(tmp_path, capsys):
    db_path = tmp_path / "verify.sqlite"
    storage, job_id, item = _seed_at(db_path)
    storage.save_page(job_id, item, _result(), _page("OK"), "body")
    with storage.conn:
        storage.conn.execute(
            "UPDATE pages SET body_sha256 = ? WHERE job_id = ?",
            (hashlib.sha256(b"wrong").hexdigest(), job_id),
        )
    storage.close()

    assert main(["verify", "--db", str(db_path), "--job-id", str(job_id)]) == ERROR
    out = capsys.readouterr().out
    assert "mismatch" in out


def test_verify_cli_succeeds_for_valid_page(tmp_path, capsys):
    db_path = tmp_path / "verify.sqlite"
    storage, job_id, item = _seed_at(db_path)
    storage.save_page(job_id, item, _result(), _page("OK"), "body")
    storage.close()

    assert main(["verify", "--db", str(db_path), "--job-id", str(job_id)]) == OK
    assert "1 valid" in capsys.readouterr().out
