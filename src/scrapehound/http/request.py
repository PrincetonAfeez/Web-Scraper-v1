"""Manual HTTP/1.1 request construction."""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from scrapehound.http.headers import CaseInsensitiveHeaders

# RFC 7230 token: legal characters for a header field-name.
_TOKEN_RE = re.compile(r"[!#$%&'*+\-.^_`|~0-9A-Za-z]+")
# Characters that must never appear in a request target or header value.
_FORBIDDEN_TARGET = ("\r", "\n", "\x00", " ")
_FORBIDDEN_VALUE = ("\r", "\n", "\x00")


def origin_form(url: str) -> str:
    parsed = urlsplit(url)
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    if any(ch in path for ch in _FORBIDDEN_TARGET):
        raise ValueError(f"invalid request target: {path!r}")
    return path


def _ascii_host(host: str) -> str:
    try:
        host.encode("ascii")
    except UnicodeEncodeError:
        try:
            return host.encode("idna").decode("ascii")
        except (UnicodeError, ValueError) as exc:
            raise ValueError(f"invalid host: {host!r}") from exc
    return host


def host_header(url: str) -> str:
    parsed = urlsplit(url)
    if not parsed.hostname:
        raise ValueError(f"URL has no host: {url}")
    host = parsed.hostname
    if ":" in host:
        # urlsplit strips the brackets from IPv6 literals; restore them.
        host = f"[{host}]"
    else:
        host = _ascii_host(host)
    port = parsed.port
    default_port = 443 if parsed.scheme == "https" else 80
    if port is not None and port != default_port:
        return f"{host}:{port}"
    return host


def _validate_header_name(name: str) -> None:
    if not _TOKEN_RE.fullmatch(name):
        raise ValueError(f"invalid header name: {name!r}")


def _validate_header_value(value: str) -> None:
    if any(ch in value for ch in _FORBIDDEN_VALUE):
        raise ValueError(f"invalid header value (control characters): {value!r}")


def build_get_request(url: str, user_agent: str, extra_headers: dict[str, str] | None = None) -> bytes:
    headers = CaseInsensitiveHeaders(
        [
            ("Host", host_header(url)),
            ("User-Agent", user_agent),
            ("Accept", "text/html, application/xhtml+xml;q=0.9, */*;q=0.1"),
            ("Accept-Encoding", "identity"),
            ("Connection", "close"),
        ]
    )
    if extra_headers:
        for name, value in extra_headers.items():
            headers[name] = value
    lines = [f"GET {origin_form(url)} HTTP/1.1"]
    for name, value in headers.items():
        _validate_header_name(name)
        _validate_header_value(value)
        lines.append(f"{name}: {value}")
    try:
        return ("\r\n".join(lines) + "\r\n\r\n").encode("latin-1")
    except UnicodeEncodeError as exc:
        raise ValueError("request headers contain non-latin-1 characters") from exc
