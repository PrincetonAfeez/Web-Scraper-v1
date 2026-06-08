"""Integration test for resume after interrupt."""

from __future__ import annotations

from scrapehound.crawl.engine import CrawlEngine
from scrapehound.models import CrawlOptions
from scrapehound.storage.repositories import Storage


def test_resume_recovers_in_progress_url(fixture_server, tmp_path):
    db_path = str(tmp_path / "resume.sqlite")
    storage = Storage(db_path)
    seed = f"{fixture_server}/page"
    job_id = storage.create_job(seed, 10, 1)
    storage.enqueue_url(job_id, seed, 0)
    item = storage.next_frontier_item(job_id)
    assert item is not None
    storage.mark_in_progress(item.id)

    options = CrawlOptions(
        db_path=db_path,
        max_pages=2,
        max_depth=1,
        min_delay_seconds=0,
        user_agent="scrapehound-test",
    )
    summary = CrawlEngine(options, storage=storage).crawl(seed, job_id=job_id)

    assert summary.pages >= 1
