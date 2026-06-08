"""Unit test for engine retry."""

from __future__ import annotations

from scrapehound.crawl.engine import CrawlEngine
from scrapehound.models import CrawlOptions, FetchResult, TimingBreakdown
from scrapehound.politeness.rate_limit import RateLimiter
from scrapehound.storage.repositories import Storage


def _engine(tmp_path):
    db = str(tmp_path / "c.sqlite")
    storage = Storage(db)
    limiter = RateLimiter()
    options = CrawlOptions(db_path=db, retry_count=2, user_agent="t")
    engine = CrawlEngine(options, storage=storage, fetcher=object(), limiter=limiter)
    job_id = storage.create_job("http://example.com/", 10, 1)
    storage.enqueue_url(job_id, "http://example.com/p", 0)
    item = storage.next_frontier_item(job_id)
    return engine, storage, limiter, item


def _result(status):
    return FetchResult(
        url="http://example.com/p",
        final_url="http://example.com/p",
        status_code=status,
        reason="",
        headers={},
        body=b"",
        timings=TimingBreakdown(),
    )


def test_server_pressure_pauses_domain_without_retry_after(tmp_path):
    engine, _storage, limiter, item = _engine(tmp_path)

    assert engine._maybe_retry(item, _result(429), category="rate_limited") is True
    # The whole domain is backed off, not just this one URL.
    assert "example.com" in limiter._paused_until


def test_exhausted_retries_do_not_double_mark(tmp_path):
    engine, storage, _limiter, item = _engine(tmp_path)
    item.retry_count = 2  # at the retry ceiling

    # _maybe_retry must NOT mark the row failed itself (the caller's _fail does).
    assert engine._maybe_retry(item, _result(503), category="server_error") is False
    refreshed = storage.next_frontier_item(item.job_id)
    assert refreshed is not None and refreshed.id == item.id  # still claimable, not marked failed
