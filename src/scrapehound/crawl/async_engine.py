"""Async extension point.

The capstone builds synchronous crawling first so the protocol path is easy to
inspect. This wrapper runs one blocking crawl in a worker thread so an asyncio
caller is not blocked; it does NOT provide intra-crawl concurrency. Each engine
owns a single SQLite connection and a single in-progress crawl, so do not invoke
the same engine from multiple tasks at once. A fuller version would replace this
with asyncio streams and a worker pool over a connection-per-worker store.
"""

from __future__ import annotations

import asyncio

from scrapehound.crawl.engine import CrawlEngine
from scrapehound.models import CrawlSummary


class AsyncCrawlEngine:
    def __init__(self, engine: CrawlEngine):
        self.engine = engine

    async def crawl(self, seed_url: str, *, job_id: int | None = None) -> CrawlSummary:
        return await asyncio.to_thread(self.engine.crawl, seed_url, job_id=job_id)
