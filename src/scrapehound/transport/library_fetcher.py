"""Practical stdlib urllib fetcher behind the same Fetcher interface."""

from __future__ import annotations

import socket
import ssl
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from scrapehound.exceptions import FetchError, ResponseTooLarge
from scrapehound.http.encoding import decompress_body
from scrapehound.models import FetchRequest, FetchResult, RedirectHop, TimingBreakdown
from scrapehound.transport.redirects import (
    ALLOWED_SCHEMES,
    is_redirect,
    redirect_target,
    same_origin,
    strip_sensitive_headers,
)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


def _build_opener() -> urllib.request.OpenerDirector:
    # Build an opener with only HTTP(S) handlers so file:// and ftp:// URLs
    # (reachable via the default build_opener handlers) cannot be fetched.
    opener = urllib.request.OpenerDirector()
    for handler in (
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPHandler(),
        urllib.request.HTTPSHandler(),
        urllib.request.HTTPDefaultErrorHandler(),
        urllib.request.HTTPErrorProcessor(),
        _NoRedirect(),
    ):
        opener.add_handler(handler)
    return opener


class LibraryFetcher:
    """Fetches resources with urllib while preserving scrapehound's result shape."""

    name = "library"

    def __init__(self) -> None:
        self._opener = _build_opener()

    def fetch(self, request: FetchRequest) -> FetchResult:
        if request.block_private_addresses:
            # urllib resolves and connects internally, so this backend cannot
            # reliably screen the target address. Fail loudly instead of giving
            # a false sense of SSRF protection — use the raw_socket transport.
            return _error_result(
                request.url,
                request.url,
                TimingBreakdown(),
                self.name,
                "unsupported_option",
                "block_private_addresses requires the raw_socket transport",
            )
        current_url = request.url
        headers = dict(request.headers)
        history: list[RedirectHop] = []
        visited: set[str] = set()
        for _hop in range(request.redirect_limit + 1):
            if urlsplit(current_url).scheme not in ALLOWED_SCHEMES:
                return self._terminal_error(
                    request.url,
                    current_url,
                    history,
                    "unsupported_scheme",
                    f"unsupported URL scheme: {current_url}",
                )
            result = self._fetch_once(current_url, request, headers)
            result.redirect_history = list(history)
            if result.error_category:
                return result
            if not is_redirect(result.status_code):
                return result
            location = _header(result.headers, "Location")
            if not location:
                return result
            history.append(
                RedirectHop(
                    url=current_url,
                    status_code=result.status_code or 0,
                    location=location,
                )
            )
            visited.add(current_url)
            next_url = redirect_target(current_url, location)
            if urlsplit(next_url).scheme not in ALLOWED_SCHEMES:
                return self._terminal_error(
                    request.url,
                    next_url,
                    history,
                    "unsupported_redirect",
                    f"redirect to non-HTTP(S) URL: {next_url}",
                )
            if next_url in visited:
                return self._terminal_error(
                    request.url,
                    next_url,
                    history,
                    "redirect_loop",
                    f"redirect loop detected at {next_url}",
                )
            if not same_origin(current_url, next_url):
                headers = strip_sensitive_headers(headers)
            current_url = next_url
        return self._terminal_error(
            request.url,
            current_url,
            history,
            "too_many_redirects",
            f"exceeded redirect limit of {request.redirect_limit}",
        )

    def _terminal_error(
        self,
        original_url: str,
        final_url: str,
        history: list[RedirectHop],
        category: str,
        message: str,
    ) -> FetchResult:
        result = _error_result(original_url, final_url, TimingBreakdown(), self.name, category, message)
        result.redirect_history = list(history)
        return result

    def _fetch_once(self, url: str, request: FetchRequest, headers: dict[str, str]) -> FetchResult:
        timings = TimingBreakdown()
        started = time.perf_counter()

        def fail(category: str, message: str) -> FetchResult:
            timings.total = time.perf_counter() - started
            return _error_result(request.url, url, timings, self.name, category, message)

        req_headers = {
            "User-Agent": request.user_agent,
            "Accept": "text/html, application/xhtml+xml;q=0.9, */*;q=0.1",
            "Accept-Encoding": "identity",
            "Connection": "close",
        }
        req_headers.update(headers)
        req = urllib.request.Request(url, headers=req_headers, method="GET")
        try:
            # urllib exposes only a single per-operation socket timeout, so it
            # cannot honor the connect/read/total split the way the raw_socket
            # backend does. total_timeout is the closest single bound available.
            response = self._opener.open(req, timeout=request.total_timeout)
            with response:
                status_code = int(getattr(response, "status", None) or response.getcode())
                reason = getattr(response, "reason", "") or ""
                header_map = dict(response.headers.items())
                _check_declared_length(response.headers.get("Content-Length"), request.max_response_bytes)
                body = response.read(request.max_response_bytes + 1)
                if len(body) > request.max_response_bytes:
                    raise ResponseTooLarge()
            body = decompress_body(
                body,
                _header(header_map, "Content-Encoding"),
                request.max_response_bytes,
            )
            timings.total = time.perf_counter() - started
            return FetchResult(
                url=request.url,
                final_url=url,
                status_code=status_code,
                reason=reason,
                headers=header_map,
                body=body,
                timings=timings,
                transport=self.name,
            )
        except urllib.error.HTTPError as exc:
            try:
                body = exc.read(request.max_response_bytes + 1)
            except OSError:
                body = b""
            if len(body) > request.max_response_bytes:
                return fail("response_too_large", "response exceeded configured byte limit")
            timings.total = time.perf_counter() - started
            return FetchResult(
                url=request.url,
                final_url=url,
                status_code=exc.code,
                reason=getattr(exc, "reason", "") or "",
                headers=dict(exc.headers.items()),
                body=body,
                timings=timings,
                transport=self.name,
            )
        except ResponseTooLarge as exc:
            return fail(exc.category, str(exc))
        except urllib.error.URLError as exc:
            return fail(_classify_urlerror(exc.reason), str(exc.reason))
        except FetchError as exc:
            return fail(exc.category, str(exc))
        except (ValueError, UnicodeError) as exc:
            return fail("malformed_url", str(exc))
        except OSError as exc:
            return fail("connection_error", str(exc))


def _check_declared_length(length: str | None, max_response_bytes: int) -> None:
    if length is None:
        return
    try:
        declared = int(length)
    except ValueError:
        return
    if declared > max_response_bytes:
        raise ResponseTooLarge()


def _classify_urlerror(reason: object) -> str:
    if isinstance(reason, (socket.timeout, TimeoutError)):
        return "read_timeout"
    if isinstance(reason, socket.gaierror):
        return "dns_error"
    if isinstance(reason, ssl.SSLError):
        return "tls_error"
    return "connection_error"


def _error_result(
    original_url: str,
    final_url: str,
    timings: TimingBreakdown,
    transport: str,
    category: str,
    message: str,
) -> FetchResult:
    return FetchResult(
        url=original_url,
        final_url=final_url,
        status_code=None,
        reason="",
        headers={},
        body=b"",
        timings=timings,
        transport=transport,
        error_category=category,
        error_message=message,
    )


def _header(headers: dict[str, str], name: str) -> str | None:
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return None
