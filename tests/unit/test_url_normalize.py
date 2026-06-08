"""Unit test for URL normalization."""

from __future__ import annotations

from scrapehound.crawl.normalize import domain_for_url, normalize_url


def test_normalize_lowercases_and_removes_fragment_and_default_port():
    assert normalize_url("HTTP://Example.COM:80/a/../b/?z=2&a=1#frag") == "http://example.com/b/?a=1&z=2"


def test_normalize_strips_tracking_params():
    assert normalize_url("https://example.com/page?utm_source=x&b=2&a=1") == "https://example.com/page?a=1&b=2"


def test_domain_for_url_is_lowercase():
    assert domain_for_url("https://EXAMPLE.com/path") == "example.com"


def test_normalize_brackets_ipv6_and_drops_default_port():
    assert normalize_url("http://[::1]:8080/a/") == "http://[::1]:8080/a/"
    assert normalize_url("https://[2606:4700::1111]:443/") == "https://[2606:4700::1111]/"


def test_normalize_punycodes_idn_host():
    assert normalize_url("http://münchen.de/Pfad") == "http://xn--mnchen-3ya.de/Pfad"
    assert domain_for_url("http://münchen.de/x") == "xn--mnchen-3ya.de"
