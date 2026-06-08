"""Unit test for encoding."""

from __future__ import annotations

import gzip
import zlib

import pytest

from scrapehound.exceptions import FetchError, MalformedResponse, ParseError, ResponseTooLarge
from scrapehound.http.encoding import decode_html, decompress_body


def test_utf16_bom_is_detected_and_decoded():
    text, encoding = decode_html("héllo".encode("utf-16"), "")

    assert encoding == "utf-16"
    assert text == "héllo"


def test_utf8_bom_is_stripped():
    text, encoding = decode_html(b"\xef\xbb\xbfhello", "")

    assert encoding == "utf-8-sig"
    assert text == "hello"
    assert not text.startswith("﻿")


def test_iso_8859_1_is_treated_as_windows_1252():
    # 0x93/0x94 are C1 controls in latin-1 but smart quotes in windows-1252.
    text, encoding = decode_html(b"\x93smart\x94", "text/html; charset=iso-8859-1")

    assert encoding == "windows-1252"
    assert text == "“smart”"


def test_charset_from_content_type_wins_over_meta():
    body = b"<meta charset='utf-8'><body>caf\xe9</body>"
    text, encoding = decode_html(body, "text/html; charset=windows-1252")

    assert encoding == "windows-1252"
    assert "café" in text


def test_decompress_gzip_deflate_and_identity():
    assert decompress_body(gzip.compress(b"hello gzip"), "gzip", 1 << 20) == b"hello gzip"
    assert decompress_body(zlib.compress(b"hello deflate"), "deflate", 1 << 20) == b"hello deflate"
    assert decompress_body(b"raw", "", 1 << 20) == b"raw"
    assert decompress_body(b"raw", "identity", 1 << 20) == b"raw"


def test_decompress_is_bounded_against_zip_bombs():
    bomb = gzip.compress(b"x" * 100_000)
    with pytest.raises(ResponseTooLarge):
        decompress_body(bomb, "gzip", 1024)


def test_decompress_rejects_unknown_encoding():
    with pytest.raises(FetchError):
        decompress_body(b"\x00\x01", "br", 1 << 20)


def test_decode_html_raises_parse_error_for_invalid_declared_charset():
    with pytest.raises(ParseError, match="cannot decode body as utf-8"):
        decode_html(b"\x80\x81", "text/html; charset=utf-8")


def test_decompress_corrupt_body_raises_malformed_not_zliberror():
    # A server may declare gzip and send garbage; this must be a catchable
    # MalformedResponse, not an uncaught zlib.error that crashes the fetch.
    with pytest.raises(MalformedResponse):
        decompress_body(b"\x1f\x8b\x08not-actually-gzip", "gzip", 1 << 20)
