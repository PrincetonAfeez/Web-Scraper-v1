"""Unit test for HTTP parser."""

from __future__ import annotations

import pytest

from scrapehound.exceptions import MalformedResponse
from scrapehound.http.parser import (
    parse_content_length,
    parse_headers,
    parse_status_line,
)
from scrapehound.http.request import build_get_request, host_header, origin_form
from scrapehound.http.response import is_allowed_content_type


def test_content_type_filter_denies_missing_type():
    allowed = ("text/html", "application/xhtml+xml")
    assert is_allowed_content_type("text/html; charset=utf-8", allowed)
    assert not is_allowed_content_type("", allowed)  # undeclared body is denied
    assert not is_allowed_content_type("application/pdf", allowed)


def test_status_line_parses_reason_phrase():
    version, status, reason = parse_status_line(b"HTTP/1.1 200 OK")

    assert version == "HTTP/1.1"
    assert status == 200
    assert reason == "OK"


def test_status_line_allows_empty_reason_phrase():
    assert parse_status_line(b"HTTP/1.1 200") == ("HTTP/1.1", 200, "")
    assert parse_status_line(b"HTTP/1.1 204 ") == ("HTTP/1.1", 204, "")


@pytest.mark.parametrize("line", [b"NOTHTTP 200 OK", b"HTTP/1.1 999 X", b"HTTP/1.1 abc OK"])
def test_malformed_status_line_fails_clearly(line):
    with pytest.raises(MalformedResponse):
        parse_status_line(line)


def test_headers_are_case_insensitive():
    headers = parse_headers(b"Content-Type: text/html\r\ncontent-length: 12")

    assert headers["content-type"] == "text/html"
    assert headers["Content-Length"] == "12"


def test_duplicate_headers_are_combined_with_comma():
    headers = parse_headers(b"Via: 1.1 a\r\nVia: 1.1 b")

    assert headers["via"] == "1.1 a, 1.1 b"


def test_set_cookie_is_not_comma_folded():
    # Cookies must never be comma-folded (RFC 6265); keep the last value.
    headers = parse_headers(b"Set-Cookie: a=1\r\nSet-Cookie: b=2")

    assert headers["set-cookie"] == "b=2"


def test_header_name_must_be_a_token():
    with pytest.raises(MalformedResponse):
        parse_headers(b"Bad Name: value")


def test_content_length_validation():
    assert parse_content_length("12") == 12
    assert parse_content_length("10, 10") == 10
    for bad in ("-5", "abc", "10, 20", "0x10", "1.0"):
        with pytest.raises(MalformedResponse):
            parse_content_length(bad)


def test_manual_get_request_uses_crlf_and_origin_form():
    request = build_get_request("http://example.com/path?q=1", "test-agent")

    assert request.startswith(b"GET /path?q=1 HTTP/1.1\r\n")
    assert b"Host: example.com\r\n" in request
    assert b"User-Agent: test-agent\r\n" in request
    assert request.endswith(b"\r\n\r\n")
    assert origin_form("http://example.com") == "/"


def test_request_builder_rejects_header_injection():
    with pytest.raises(ValueError):
        build_get_request("http://example.com/", "agent\r\nEvil: injected")
    with pytest.raises(ValueError):
        build_get_request("http://example.com/", "agent", {"X-Foo": "ok\r\nInjected: 1"})
    with pytest.raises(ValueError):
        build_get_request("http://example.com/", "agent", {"Bad Name": "value"})


def test_origin_form_rejects_control_characters():
    with pytest.raises(ValueError):
        origin_form("http://example.com/path\r\nEvil: 1")


def test_host_header_brackets_ipv6_and_punycodes_idn():
    assert host_header("http://[::1]:8080/") == "[::1]:8080"
    assert host_header("https://[2606:4700::1111]/") == "[2606:4700::1111]"
    assert host_header("http://münchen.de/") == "xn--mnchen-3ya.de"


def test_extra_headers_override_host_case_insensitively():
    request = build_get_request("http://example.com/", "agent", {"host": "override.test"})

    assert request.lower().count(b"host:") == 1
    assert b"override.test" in request
