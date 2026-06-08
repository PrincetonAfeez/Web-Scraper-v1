"""Unit test for robots."""

from __future__ import annotations

from scrapehound.models import FetchResult, TimingBreakdown
from scrapehound.politeness.robots import RobotsCache, parse_robots


def test_robots_allow_wins_when_more_specific():
    rules = parse_robots(
        """
        User-agent: *
        Disallow: /private
        Allow: /private/public
        Crawl-delay: 2.5
        """
    )

    assert not rules.allowed("http://example.com/private/secret")
    assert rules.allowed("http://example.com/private/public/page")
    assert rules.crawl_delay == 2.5


def test_empty_robots_allows_everything():
    assert parse_robots("").allowed("http://example.com/anything")


def test_robots_collects_sitemaps_globally():
    rules = parse_robots("Sitemap: http://x/a.xml\nUser-agent: *\nDisallow: /p\nSitemap: http://x/b.xml")

    assert rules.sitemaps == ["http://x/a.xml", "http://x/b.xml"]
    assert not rules.allowed("http://x/p")


def test_robots_wildcard_and_end_anchor():
    rules = parse_robots("User-agent: *\nDisallow: /*.pdf$\nDisallow: /*?sid=")

    assert not rules.allowed("http://x/docs/a.pdf")
    assert rules.allowed("http://x/docs/a.pdfx")  # $ anchors the match
    assert not rules.allowed("http://x/search?sid=1")
    assert rules.allowed("http://x/search?q=1")


def test_robots_longest_match_is_order_independent():
    rules = parse_robots("User-agent: *\nDisallow: /a\nAllow: /a/b\nDisallow: /a/b/c")

    assert not rules.allowed("http://x/a/b/c/d")  # longest rule (/a/b/c) wins
    assert rules.allowed("http://x/a/b/x")


def test_robots_agent_matched_by_product_token_prefix():
    text = "User-agent: bot\nDisallow: /\n\nUser-agent: scrapehound\nDisallow: /private"
    rules = parse_robots(text, "scrapehound/0.1 (+x)")

    assert rules.allowed("http://x/public")
    assert not rules.allowed("http://x/private")
    # A group for "robot" must not capture an unrelated "bot" crawler.
    other = parse_robots("User-agent: robot\nDisallow: /\n", "bot/1.0")
    assert other.allowed("http://x/anything")


class _FakeFetcher:
    def __init__(self, status, body=b""):
        self.status = status
        self.body = body

    def fetch(self, request):
        return FetchResult(
            url=request.url,
            final_url=request.url,
            status_code=self.status,
            reason="",
            headers={},
            body=self.body,
            timings=TimingBreakdown(),
        )


def test_robots_cache_status_handling():
    # 2xx (incl. empty) and 4xx impose no restrictions; 5xx/unreachable disallow all.
    assert RobotsCache(_FakeFetcher(200, b""), "ua").allowed("http://x/secret")
    assert RobotsCache(_FakeFetcher(403), "ua").allowed("http://x/secret")
    assert not RobotsCache(_FakeFetcher(503), "ua").allowed("http://x/secret")
    assert not RobotsCache(_FakeFetcher(None), "ua").allowed("http://x/secret")
    assert not RobotsCache(_FakeFetcher(200, b"User-agent: *\nDisallow: /secret"), "ua").allowed("http://x/secret")
