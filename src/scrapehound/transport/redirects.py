"""Redirect helper functions."""

from __future__ import annotations

from urllib.parse import urljoin, urlsplit

REDIRECT_STATUSES = {301, 302, 303, 307, 308}
ALLOWED_SCHEMES = {"http", "https"}
# Headers that must not be forwarded across an origin boundary on redirect.
_SENSITIVE_HEADERS = {"authorization", "cookie", "proxy-authorization"}


def is_redirect(status_code: int | None) -> bool:
    return status_code in REDIRECT_STATUSES


def redirect_target(current_url: str, location: str) -> str:
    return urljoin(current_url, location)


def is_http_url(url: str) -> bool:
    return urlsplit(url).scheme in ALLOWED_SCHEMES


def _origin(url: str) -> tuple[str | None, str | None, int | None]:
    parsed = urlsplit(url)
    try:
        port = parsed.port
    except ValueError:
        port = None
    if port is None:
        port = 443 if parsed.scheme == "https" else 80
    return (parsed.scheme, parsed.hostname, port)


def same_origin(a: str, b: str) -> bool:
    return _origin(a) == _origin(b)


def strip_sensitive_headers(headers: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in headers.items() if key.lower() not in _SENSITIVE_HEADERS}
