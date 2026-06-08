"""Typed exceptions that collapse to stable persisted failure categories."""

from __future__ import annotations


class ScrapehoundError(Exception):
    """Base class for scraper failures."""


class FetchError(ScrapehoundError):
    """Network or protocol error raised by a fetcher."""

    def __init__(self, category: str, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.category = category
        self.status_code = status_code


class ResponseTooLarge(FetchError):
    """Raised when a response crosses the configured byte budget."""

    def __init__(self, message: str = "response exceeded configured byte limit"):
        super().__init__("response_too_large", message)


class MalformedResponse(FetchError):
    """Raised when status line, headers, or body framing is invalid."""

    def __init__(self, message: str):
        super().__init__("malformed_response", message)


class RobotsDisallowed(ScrapehoundError):
    """Raised when robots.txt disallows a URL."""


class ConfigurationError(ScrapehoundError):
    """Raised when CLI or TOML configuration is invalid."""


class ParseError(ScrapehoundError):
    """Raised when HTML parsing or decoding fails."""
