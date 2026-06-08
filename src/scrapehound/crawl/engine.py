"""Synchronous crawl engine."""

from __future__ import annotations

import time
from urllib.parse import urlsplit

from scrapehound.crawl.retry import RetryPolicy
from scrapehound.crawl.scheduler import Scheduler
from scrapehound.crawl.scope import DomainScope
from scrapehound.http.encoding import decode_html
from scrapehound.http.response import is_allowed_content_type
from scrapehound.models import CrawlOptions, CrawlSummary, FetchRequest, FetchResult
from scrapehound.parse.stdlib_parser import StdlibHTMLParser
from scrapehound.politeness.rate_limit import RateLimiter
from scrapehound.politeness.robots import RobotsCache
from scrapehound.storage.repositories import FrontierItem, Storage
from scrapehound.transport import make_fetcher


class CrawlEngine:
    def __init__(
        self,
        options: CrawlOptions,
        *,
        storage: Storage | None = None,
        fetcher=None,  # type: ignore[no-untyped-def]
        parser: StdlibHTMLParser | None = None,
        limiter: RateLimiter | None = None,
    ):
        self.options = options
        self.storage = storage or Storage(options.db_path)
        self.fetcher = fetcher or make_fetcher(options.transport)
        self.parser = parser or StdlibHTMLParser()
        self.limiter = limiter or RateLimiter()
        self.scheduler = Scheduler(self.limiter)
        self.retry_policy = RetryPolicy(max_retries=options.retry_count)
        self.robots = RobotsCache(self.fetcher, options.user_agent)

    def crawl(self, seed_url: str, *, job_id: int | None = None) -> CrawlSummary:
        new_job = job_id is None
        if job_id is None:
            job_id = self.storage.create_job(seed_url, self.options.max_pages, self.options.max_depth)
            self.storage.enqueue_url(job_id, seed_url, 0, None)
        else:
            self.storage.recover_in_progress(job_id)
        scope = DomainScope(
            seed_url,
            stay_on_seed_domain=self.options.stay_on_seed_domain,
            allowed_domains=self.options.allowed_domains,
        )

        fetched_this_run = 0
        failed_this_run = 0
        skipped_this_run = 0
        try:
            while self.storage.stats(job_id)["pages"] < self.options.max_pages:
                item = self.storage.next_frontier_item(job_id)
                if item is None:
                    if not self.storage.has_pending_work(job_id):
                        break
                    wait_for = self.storage.seconds_until_next(job_id)
                    time.sleep(min(wait_for if wait_for is not None else 1.0, 1.0))
                    continue
                if item.depth > self.options.max_depth:
                    skipped_this_run += self._skip(
                        job_id,
                        item,
                        "max_depth_exceeded",
                        "URL depth exceeded configured max depth",
                    )
                    continue
                if not scope.allows(item.url):
                    skipped_this_run += self._skip(job_id, item, "off_domain", "URL outside configured crawl scope")
                    continue
                if self.options.obey_robots and not self.robots.allowed(item.url):
                    skipped_this_run += self._skip(
                        job_id,
                        item,
                        "robots_disallowed",
                        "robots.txt disallowed this URL",
                    )
                    continue

                domain = (urlsplit(item.url).hostname or "").lower()
                crawl_delay = self.robots.crawl_delay(item.url) if self.options.obey_robots else None
                delay = max(self.options.min_delay_seconds, crawl_delay or 0.0)
                if self.options.trace:
                    print(f"[rate-limit] domain={domain} delay={delay:.3f}s url={item.url}")
                self.scheduler.wait_for_domain(domain, delay)
                self.storage.mark_in_progress(item.id)
                result = self._fetch(item)
                if result.error_category:
                    if self._maybe_retry(item, result):
                        continue
                    failed_this_run += self._fail(
                        job_id,
                        item,
                        result.error_category,
                        result.error_message,
                        None,
                        item.retry_count,
                    )
                    continue

                retry_category = _status_failure_category(result.status_code)
                if retry_category:
                    if self._maybe_retry(item, result, category=retry_category):
                        continue
                    failed_this_run += self._fail(
                        job_id,
                        item,
                        retry_category,
                        result.reason,
                        result.status_code,
                        item.retry_count,
                    )
                    continue

                content_type = _header(result.headers, "Content-Type") or ""
                if not is_allowed_content_type(content_type, self.options.allowed_content_types):
                    skipped_this_run += self._skip(
                        job_id,
                        item,
                        "unsupported_content_type",
                        f"skipped content type {content_type!r}",
                        status_code=result.status_code,
                    )
                    continue

                try:
                    parsed = self.parser.parse(result.body, result.final_url, content_type)
                    body_text, _encoding = decode_html(result.body, content_type)
                except Exception as exc:
                    failed_this_run += self._fail(
                        job_id,
                        item,
                        "parse_error",
                        str(exc),
                        result.status_code,
                        item.retry_count,
                    )
                    continue
                self.storage.save_page(job_id, item, result, parsed, body_text)
                self.storage.mark_fetched(item.id)
                fetched_this_run += 1
                if self.options.trace:
                    print(f"[fetched] {result.status_code} {result.final_url} links={len(parsed.links)}")
                next_depth = item.depth + 1
                if next_depth <= self.options.max_depth:
                    for link in parsed.links:
                        if scope.allows(link):
                            self.storage.enqueue_url(job_id, link, next_depth, result.final_url)
            # "finished" means the frontier drained; "budget_reached" means we hit
            # max_pages while work remained (so a resume can still make progress).
            final_status = "finished" if not self.storage.has_pending_work(job_id) else "budget_reached"
            self.storage.finish_job(job_id, final_status)
        except KeyboardInterrupt:
            self.storage.finish_job(job_id, "interrupted")
            raise
        except Exception:
            self.storage.finish_job(job_id, "errored")
            raise
        stats = self.storage.stats(job_id)
        return CrawlSummary(
            job_id=job_id,
            fetched=fetched_this_run,
            failed=failed_this_run,
            skipped=skipped_this_run,
            pending=stats["frontier"].get("pending", 0) + stats["frontier"].get("retry_scheduled", 0),
            pages=stats["pages"],
            failures=stats["failures"],
            details={"new_job": new_job, "frontier": stats["frontier"]},
        )

    def _fetch(self, item: FrontierItem) -> FetchResult:
        if self.options.trace:
            print(f"[fetch] {item.url}")
        return self.fetcher.fetch(
            FetchRequest(
                url=item.url,
                user_agent=self.options.user_agent,
                connect_timeout=self.options.connect_timeout,
                read_timeout=self.options.read_timeout,
                total_timeout=self.options.total_timeout,
                max_response_bytes=self.options.max_response_bytes,
                redirect_limit=self.options.redirect_limit,
                block_private_addresses=self.options.block_private_addresses,
            )
        )

    def _maybe_retry(self, item: FrontierItem, result: FetchResult, *, category: str | None = None) -> bool:
        failure_category = category or result.error_category
        if not self.retry_policy.should_retry(
            status_code=result.status_code,
            category=failure_category,
            retry_count=item.retry_count,
        ):
            # The caller records the terminal failure via _fail(); don't mark here.
            return False
        retry_after = _header(result.headers, "Retry-After")
        delay = self.retry_policy.delay_seconds(item.retry_count, retry_after)
        domain = (urlsplit(item.url).hostname or "").lower()
        # Back off the whole domain when the server signals overload, not just
        # this URL — otherwise the next URL on the domain ignores the 429/503.
        if retry_after or failure_category in {"rate_limited", "server_error"}:
            self.scheduler.pause_domain(domain, delay)
        self.storage.schedule_retry(item.id, item.retry_count + 1, delay)
        if self.options.trace:
            print(f"[retry] {item.url} category={failure_category} delay={delay:.2f}s")
        return True

    def _skip(
        self,
        job_id: int,
        item: FrontierItem,
        category: str,
        message: str,
        *,
        status_code: int | None = None,
    ) -> int:
        self.storage.mark_skipped(item.id)
        self.storage.save_failure(
            job_id,
            item.url,
            category,
            message,
            status_code=status_code,
            retry_count=item.retry_count,
        )
        if self.options.trace:
            print(f"[skip] {category} {item.url}")
        return 1

    def _fail(
        self,
        job_id: int,
        item: FrontierItem,
        category: str,
        message: str | None,
        status_code: int | None,
        retry_count: int,
    ) -> int:
        self.storage.mark_failed(item.id)
        self.storage.save_failure(
            job_id,
            item.url,
            category,
            message,
            status_code=status_code,
            retry_count=retry_count,
        )
        if self.options.trace:
            print(f"[fail] {category} {item.url} {message or ''}")
        return 1


def _status_failure_category(status_code: int | None) -> str | None:
    if status_code is None:
        return None
    if status_code == 429:
        return "rate_limited"
    if 500 <= status_code:
        return "server_error"
    if 400 <= status_code:
        return "client_error"
    return None


def _header(headers: dict[str, str], name: str) -> str | None:
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return None
