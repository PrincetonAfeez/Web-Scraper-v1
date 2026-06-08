"""Integration test for socket fetcher against WSGI fixture."""

from __future__ import annotations

from scrapehound.models import FetchRequest
from scrapehound.transport.socket_fetcher import RawSocketFetcher


def test_raw_socket_fetcher_fetches_wsgi_fixture(fixture_server):
    result = RawSocketFetcher().fetch(
        FetchRequest(
            url=f"{fixture_server}/page",
            user_agent="scrapehound-test",
            max_response_bytes=1024 * 1024,
        )
    )

    assert result.error_category is None
    assert result.status_code == 200
    assert b"Fixture Page" in result.body
    assert result.timings.total >= 0


def test_raw_socket_fetcher_follows_redirect(fixture_server):
    result = RawSocketFetcher().fetch(FetchRequest(url=f"{fixture_server}/redirect", user_agent="scrapehound-test"))

    assert result.error_category is None
    assert result.status_code == 200
    assert result.final_url.endswith("/page2")
    assert len(result.redirect_history) == 1
