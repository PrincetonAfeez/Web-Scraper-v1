"""Unit tests for crawl engine parse failure categories."""

from __future__ import annotations

from scrapehound.crawl.engine import CrawlEngine
from scrapehound.exceptions import ParseError
from scrapehound.models import CrawlOptions, FetchResult, ParsedPage, TimingBreakdown
from scrapehound.politeness.rate_limit import RateLimiter
from scrapehound.storage.repositories import Storage


class _ParseErrorParser:
    def parse(self, body: bytes, final_url: str, content_type: str) -> ParsedPage:
        raise ParseError("bad html")


class _BrokenParser:
    def parse(self, body: bytes, final_url: str, content_type: str) -> ParsedPage:
        raise RuntimeError("unexpected parser bug")


class _OkParser:
    def parse(self, body: bytes, final_url: str, content_type: str) -> ParsedPage:
        return ParsedPage(
            final_url=final_url,
            title=None,
            description=None,
            headings=[],
            links=[],
            text_encoding="utf-8",
        )


def _engine(tmp_path, parser):
    db = str(tmp_path / "parse.sqlite")
    storage = Storage(db)
    options = CrawlOptions(db_path=db, user_agent="t", min_delay_seconds=0)
    engine = CrawlEngine(
        options,
        storage=storage,
        fetcher=_Fetcher(),
        parser=parser,
        limiter=RateLimiter(),
    )
    job_id = storage.create_job("http://example.com/", 10, 1)
    storage.enqueue_url(job_id, "http://example.com/p", 0)
    return engine, storage, job_id


class _Fetcher:
    def fetch(self, request):
        return FetchResult(
            url=request.url,
            final_url=request.url,
            status_code=200,
            reason="OK",
            headers={"Content-Type": "text/html; charset=utf-8"},
            body=b"<html>ok</html>",
            timings=TimingBreakdown(),
        )


def test_parse_error_is_recorded_as_parse_error(tmp_path):
    engine, storage, job_id = _engine(tmp_path, _ParseErrorParser())
    summary = engine.crawl("http://example.com/", job_id=job_id)

    assert summary.failed == 1
    failure = storage.conn.execute("SELECT category FROM failures WHERE job_id = ?", (job_id,)).fetchone()
    assert failure["category"] == "parse_error"


def test_unexpected_parser_failure_is_internal_parse_error(tmp_path):
    engine, storage, job_id = _engine(tmp_path, _BrokenParser())
    summary = engine.crawl("http://example.com/", job_id=job_id)

    assert summary.failed == 1
    failure = storage.conn.execute("SELECT category FROM failures WHERE job_id = ?", (job_id,)).fetchone()
    assert failure["category"] == "internal_parse_error"


def test_successful_parse_stores_page(tmp_path):
    engine, storage, job_id = _engine(tmp_path, _OkParser())
    summary = engine.crawl("http://example.com/", job_id=job_id)

    assert summary.fetched == 1
    assert storage.stats(job_id)["pages"] == 1
