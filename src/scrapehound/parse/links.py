"""Convenience link extraction wrapper."""

from __future__ import annotations

from scrapehound.parse.stdlib_parser import StdlibHTMLParser


def extract_links(body: bytes, final_url: str, content_type: str = "text/html") -> list[str]:
    return StdlibHTMLParser().parse(body, final_url, content_type).links
