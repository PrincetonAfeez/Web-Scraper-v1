"""Unit test for redirects."""

from __future__ import annotations

import pytest

from scrapehound.models import FetchRequest
from scrapehound.transport import make_fetcher
from scrapehound.transport.library_fetcher import LibraryFetcher
from scrapehound.transport.redirects import (
    is_http_url,
    same_origin,
    strip_sensitive_headers,
)
from scrapehound.transport.socket_fetcher import RawSocketFetcher, _is_blocked_address


def test_same_origin_treats_default_ports_as_equal():
    assert same_origin("http://example.com/a", "http://example.com:80/b")
    assert same_origin("https://example.com/a", "https://example.com:443/b")
    assert not same_origin("http://example.com/", "http://other.com/")
    assert not same_origin("http://example.com/", "https://example.com/")


def test_strip_sensitive_headers_removes_credentials():
    headers = {"Authorization": "Bearer x", "Cookie": "s=1", "X-Keep": "ok"}

    assert strip_sensitive_headers(headers) == {"X-Keep": "ok"}


def test_is_http_url():
    assert is_http_url("http://x/")
    assert is_http_url("https://x/")
    assert not is_http_url("file:///etc/passwd")
    assert not is_http_url("ftp://x/")


@pytest.mark.parametrize(
    "ip, blocked",
    [
        ("127.0.0.1", True),
        ("10.0.0.1", True),
        ("169.254.1.1", True),
        ("::1", True),
        ("0.0.0.0", True),
        ("8.8.8.8", False),
        ("93.184.216.34", False),
    ],
)
def test_blocked_address_classification(ip, blocked):
    assert _is_blocked_address(ip) is blocked


@pytest.mark.parametrize("fetcher", [RawSocketFetcher(), LibraryFetcher()])
def test_non_http_scheme_is_rejected_without_connecting(fetcher):
    result = fetcher.fetch(FetchRequest(url="file:///etc/passwd", user_agent="t"))

    assert result.error_category in {"unsupported_scheme", "unsupported_redirect"}
    assert result.body == b""


def test_make_fetcher_normalizes_name():
    assert type(make_fetcher(" RAW_SOCKET ")).__name__ == "RawSocketFetcher"
    assert type(make_fetcher("Library")).__name__ == "LibraryFetcher"
    with pytest.raises(ValueError):
        make_fetcher("nope")
