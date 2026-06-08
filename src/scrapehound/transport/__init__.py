"""HTTP transport backends."""

from scrapehound.transport.base import Fetcher
from scrapehound.transport.library_fetcher import LibraryFetcher
from scrapehound.transport.socket_fetcher import RawSocketFetcher

__all__ = ["Fetcher", "LibraryFetcher", "RawSocketFetcher", "make_fetcher"]


def make_fetcher(name: str) -> Fetcher:
    normalized = name.strip().lower()
    if normalized == "raw_socket":
        return RawSocketFetcher()
    if normalized == "library":
        return LibraryFetcher()
    raise ValueError(f"unknown transport: {name!r}")
