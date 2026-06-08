"""Unit test for frontier states."""

from __future__ import annotations

from scrapehound.crawl import frontier as states
from scrapehound.storage.repositories import Storage


def test_storage_recovers_in_progress_frontier_items(tmp_path):
    storage = Storage(str(tmp_path / "crawl.sqlite"))
    job_id = storage.create_job("http://example.com/page", 10, 2)
    frontier_id = storage.enqueue_url(job_id, "http://example.com/page", 0)
    assert frontier_id is not None
    item = storage.next_frontier_item(job_id)
    assert item is not None
    storage.mark_in_progress(item.id)

    assert storage.recover_in_progress(job_id) == 1
    recovered = storage.next_frontier_item(job_id)

    assert recovered is not None
    assert recovered.status == states.PENDING


def test_enqueue_invalid_url_is_skipped_not_raised(tmp_path):
    storage = Storage(str(tmp_path / "crawl.sqlite"))
    job_id = storage.create_job("http://example.com/page", 10, 2)

    # A malformed discovered link must return None, not abort the crawl.
    assert storage.enqueue_url(job_id, "javascript:void(0)", 1) is None
    assert storage.enqueue_url(job_id, "mailto:a@b.com", 1) is None
    assert storage.enqueue_url(job_id, "http://example.com/ok", 1) is not None
