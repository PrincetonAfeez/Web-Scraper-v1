"""HTML text decoding helpers."""

from __future__ import annotations

import re
import zlib

from scrapehound.exceptions import FetchError, MalformedResponse, ResponseTooLarge

CHARSET_RE = re.compile(r"charset\s*=\s*['\"]?([A-Za-z0-9._-]+)", re.IGNORECASE)
META_CHARSET_RE = re.compile(r"<meta[^>]+charset=['\"]?([A-Za-z0-9._-]+)", re.IGNORECASE)

_BOM_CHAR = "﻿"

# Byte-order marks, longest first so UTF-32 is tested before UTF-16.
_BOMS: tuple[tuple[bytes, str], ...] = (
    (b"\x00\x00\xfe\xff", "utf-32"),
    (b"\xff\xfe\x00\x00", "utf-32"),
    (b"\xef\xbb\xbf", "utf-8-sig"),
    (b"\xfe\xff", "utf-16"),
    (b"\xff\xfe", "utf-16"),
)

# WHATWG/HTML5 mandates treating these labels as windows-1252.
_HTML5_LABEL_OVERRIDES = {
    "iso-8859-1": "windows-1252",
    "latin-1": "windows-1252",
    "latin1": "windows-1252",
    "ascii": "windows-1252",
    "us-ascii": "windows-1252",
}


def _normalize_label(label: str) -> str:
    return _HTML5_LABEL_OVERRIDES.get(label.strip().lower(), label)


def _detect_bom(body: bytes) -> str | None:
    for bom, encoding in _BOMS:
        if body.startswith(bom):
            return encoding
    return None


def _inflate(body: bytes, wbits: int, max_response_bytes: int) -> bytes:
    decompressor = zlib.decompressobj(wbits)
    output = decompressor.decompress(body, max_response_bytes + 1)
    if decompressor.unconsumed_tail:
        raise ResponseTooLarge("decompressed response exceeded byte limit")
    output += decompressor.flush()
    if len(output) > max_response_bytes:
        raise ResponseTooLarge("decompressed response exceeded byte limit")
    return output


def decompress_body(body: bytes, content_encoding: str | None, max_response_bytes: int) -> bytes:
    """Decode a gzip/deflate Content-Encoding body, bounded by max_response_bytes."""
    encoding = (content_encoding or "").split(",")[0].strip().lower()
    if not encoding or encoding == "identity":
        return body
    try:
        if encoding == "gzip":
            return _inflate(body, 31, max_response_bytes)
        if encoding == "deflate":
            try:
                return _inflate(body, 15, max_response_bytes)  # zlib-wrapped
            except zlib.error:
                return _inflate(body, -15, max_response_bytes)  # raw deflate
    except zlib.error as exc:
        # A corrupt body for the declared encoding is a malformed response,
        # not an uncaught crash. ResponseTooLarge is not zlib.error, so the
        # byte-cap still surfaces as its own category.
        raise MalformedResponse(f"corrupt {encoding} Content-Encoding: {exc}") from exc
    raise FetchError("unsupported_content_encoding", f"cannot decode Content-Encoding: {encoding}")


def charset_from_content_type(content_type: str) -> str | None:
    match = CHARSET_RE.search(content_type or "")
    return match.group(1) if match else None


def charset_from_meta(sample: bytes) -> str | None:
    text = sample[:4096].decode("ascii", errors="ignore")
    match = META_CHARSET_RE.search(text)
    return match.group(1) if match else None


def decode_html(body: bytes, content_type: str) -> tuple[str, str]:
    bom_encoding = _detect_bom(body)
    if bom_encoding:
        return body.decode(bom_encoding, errors="replace"), bom_encoding
    for encoding in (
        charset_from_content_type(content_type),
        charset_from_meta(body),
        "utf-8",
    ):
        if not encoding:
            continue
        normalized = _normalize_label(encoding)
        try:
            text = body.decode(normalized, errors="replace")
        except LookupError:
            continue
        return text.lstrip(_BOM_CHAR), normalized
    return body.decode("utf-8", errors="replace").lstrip(_BOM_CHAR), "utf-8"
