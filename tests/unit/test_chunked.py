"""Unit test for chunked response decoding."""

from __future__ import annotations

import pytest

from scrapehound.exceptions import MalformedResponse, ResponseTooLarge
from scrapehound.http.chunked import decode_chunked


def test_decode_chunked_response():
    assert decode_chunked(b"4\r\nWiki\r\n5\r\npedia\r\n0\r\n\r\n", 100) == b"Wikipedia"


def test_invalid_chunk_size_raises_malformed_response():
    with pytest.raises(MalformedResponse):
        decode_chunked(b"Z\r\nnope\r\n0\r\n\r\n", 100)


def test_chunked_body_obeys_max_bytes():
    with pytest.raises(ResponseTooLarge):
        decode_chunked(b"4\r\nWiki\r\n0\r\n\r\n", 3)


def test_negative_or_signed_chunk_size_is_rejected():
    with pytest.raises(MalformedResponse):
        decode_chunked(b"-1\r\nx\r\n0\r\n\r\n", 100)
    with pytest.raises(MalformedResponse):
        decode_chunked(b"+4\r\nWiki\r\n0\r\n\r\n", 100)


def test_final_chunk_requires_trailer_terminator():
    with pytest.raises(MalformedResponse):
        decode_chunked(b"4\r\nWiki\r\n0\r\n", 100)


def test_chunked_supports_trailers():
    assert decode_chunked(b"4\r\nWiki\r\n0\r\nX-Trailer: 1\r\n\r\n", 100) == b"Wiki"
