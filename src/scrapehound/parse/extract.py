"""Convenience metadata extraction wrapper."""

from __future__ import annotations

from scrapehound.models import ParsedPage
from scrapehound.parse.stdlib_parser import StdlibHTMLParser


def extract_page(body: bytes, final_url: str, content_type: str = "text/html") -> ParsedPage:
    return StdlibHTMLParser().parse(body, final_url, content_type)
