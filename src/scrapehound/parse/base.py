"""Parser interface."""

from __future__ import annotations

from typing import Protocol

from scrapehound.models import ParsedPage


class PageParser(Protocol):
    def parse(self, body: bytes, final_url: str, content_type: str) -> ParsedPage:
        """Parse body bytes into links and structured metadata."""
