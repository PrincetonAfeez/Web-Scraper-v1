"""Integration test for transport security."""

from __future__ import annotations

import time

import pytest

from scrapehound.models import FetchRequest
from scrapehound.transport.library_fetcher import LibraryFetcher
from scrapehound.transport.socket_fetcher import RawSocketFetcher


@pytest.mark.parametrize("fetcher", [RawSocketFetcher(), LibraryFetcher()])
def test_redirect_loop_is_detected_quickly(fetcher, fixture_server):
    result = fetcher.fetch(FetchRequest(url=f"{fixture_server}/redirect-loop", user_agent="t", redirect_limit=5))

    assert result.error_category == "redirect_loop"
    # Detected on the repeat rather than burning the whole redirect budget.
    assert len(result.redirect_history) == 1


def test_total_timeout_bounds_a_slow_server(fixture_server):
    start = time.perf_counter()
    result = RawSocketFetcher().fetch(
        FetchRequest(
            url=f"{fixture_server}/slow",
            user_agent="t",
            total_timeout=0.5,
            read_timeout=10.0,
        )
    )
    elapsed = time.perf_counter() - start

    assert result.error_category in {"read_timeout", "total_timeout"}
    assert elapsed < 1.5


def test_library_transport_rejects_block_private_addresses():
    # urllib can't reliably screen the target, so it must fail loudly rather
    # than give false SSRF assurance.
    result = LibraryFetcher().fetch(
        FetchRequest(url="http://example.com/", user_agent="t", block_private_addresses=True)
    )
    assert result.error_category == "unsupported_option"


def test_block_private_addresses_refuses_loopback(fixture_server):
    blocked = RawSocketFetcher().fetch(
        FetchRequest(url=f"{fixture_server}/page", user_agent="t", block_private_addresses=True)
    )
    assert blocked.error_category == "blocked_address"

    allowed = RawSocketFetcher().fetch(
        FetchRequest(
            url=f"{fixture_server}/page",
            user_agent="t",
            block_private_addresses=False,
            max_response_bytes=1024 * 1024,
        )
    )
    assert allowed.status_code == 200
