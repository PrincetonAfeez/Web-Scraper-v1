"""URL normalization for deduplication and frontier identity."""

from __future__ import annotations

import posixpath
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

TRACKING_PARAMS = {
    "fbclid",
    "gclid",
    "gbraid",
    "wbraid",
    "msclkid",
    "dclid",
    "yclid",
    "igshid",
    "mc_cid",
    "mc_eid",
}


def _ascii_host(host: str) -> str:
    """Return an ASCII host, punycoding non-ASCII labels (IDNA)."""
    try:
        host.encode("ascii")
        return host
    except UnicodeEncodeError:
        try:
            return host.encode("idna").decode("ascii")
        except (UnicodeError, ValueError):
            return host


def normalize_url(url: str, *, strip_tracking: bool = True) -> str:
    parsed = urlsplit(url.strip())
    scheme = parsed.scheme.lower()
    host = _ascii_host((parsed.hostname or "").lower())
    if not scheme or not host:
        raise ValueError(f"URL must include scheme and host: {url}")
    port = parsed.port
    authority = f"[{host}]" if ":" in host else host  # bracket IPv6 literals
    netloc = authority
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{authority}:{port}"
    path = parsed.path or "/"
    had_trailing_slash = path.endswith("/")
    path = posixpath.normpath(path)
    if not path.startswith("/"):
        path = "/" + path
    if path.startswith("//"):
        path = "/" + path.lstrip("/")
    if had_trailing_slash and not path.endswith("/"):
        path += "/"
    path = quote(path, safe="/%:@")
    query_items = parse_qsl(parsed.query, keep_blank_values=True)
    if strip_tracking:
        query_items = [
            (key, value)
            for key, value in query_items
            if not key.lower().startswith("utm_") and key.lower() not in TRACKING_PARAMS
        ]
    query = urlencode(sorted(query_items), doseq=True)
    return urlunsplit((scheme, netloc, path, query, ""))


def domain_for_url(url: str) -> str:
    parsed = urlsplit(url)
    return _ascii_host((parsed.hostname or "").lower())
