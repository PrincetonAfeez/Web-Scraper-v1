"""Chunked transfer decoding used by parser fixtures and raw test server."""

from __future__ import annotations

import re

from scrapehound.exceptions import MalformedResponse, ResponseTooLarge

_HEX_RE = re.compile(rb"[0-9A-Fa-f]+")


def decode_chunked(data: bytes, max_response_bytes: int) -> bytes:
    output = bytearray()
    position = 0
    while True:
        line_end = data.find(b"\r\n", position)
        if line_end < 0:
            raise MalformedResponse("chunk size line missing CRLF")
        raw_size = data[position:line_end].split(b";", 1)[0].strip()
        if not _HEX_RE.fullmatch(raw_size):
            raise MalformedResponse(f"invalid chunk size: {raw_size!r}")
        size = int(raw_size, 16)
        position = line_end + 2
        if size == 0:
            if data[position : position + 2] == b"\r\n":
                return bytes(output)
            if data.find(b"\r\n\r\n", position) < 0:
                raise MalformedResponse("final chunk missing trailer terminator")
            return bytes(output)
        if len(output) + size > max_response_bytes:
            raise ResponseTooLarge()
        chunk = data[position : position + size]
        if len(chunk) != size:
            raise MalformedResponse("incomplete chunk body")
        output.extend(chunk)
        position += size
        if data[position : position + 2] != b"\r\n":
            raise MalformedResponse("chunk body missing trailing CRLF")
        position += 2
