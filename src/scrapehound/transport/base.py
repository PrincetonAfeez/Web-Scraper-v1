"""Fetcher interface."""

from __future__ import annotations

from typing import Protocol

from scrapehound.models import FetchRequest, FetchResult


class Fetcher(Protocol):
    name: str

    def fetch(self, request: FetchRequest) -> FetchResult:
        """Fetch one URL and return a typed result."""
