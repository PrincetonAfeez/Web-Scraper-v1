"""Educational raw-socket HTTP/1.1 fetcher."""

from __future__ import annotations

import ipaddress
import socket
import ssl
import threading
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

from scrapehound.exceptions import FetchError, MalformedResponse
from scrapehound.http.encoding import decompress_body
from scrapehound.http.parser import read_http_response
from scrapehound.http.request import build_get_request
from scrapehound.models import FetchRequest, FetchResult, RedirectHop, TimingBreakdown
from scrapehound.transport.redirects import (
    ALLOWED_SCHEMES,
    is_redirect,
    redirect_target,
    same_origin,
    strip_sensitive_headers,
)
from scrapehound.transport.timeouts import Deadline


@dataclass(slots=True)
class ParsedURL:
    scheme: str
    host: str
    port: int
    path: str
    query: str


class RawSocketFetcher:
    """Fetches HTTP(S) resources by manually opening sockets and writing bytes."""

    name = "raw_socket"

    def fetch(self, request: FetchRequest) -> FetchResult:
        deadline = Deadline(request.total_timeout)
        current_url = request.url
        headers = dict(request.headers)
        history: list[RedirectHop] = []
        visited: set[str] = set()
        for _hop in range(request.redirect_limit + 1):
            result = self._fetch_once(current_url, request, deadline, headers)
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
                return self._redirect_error(
                    request.url,
                    next_url,
                    history,
                    "unsupported_redirect",
                    f"redirect to non-HTTP(S) URL: {next_url}",
                )
            if next_url in visited:
                return self._redirect_error(
                    request.url,
                    next_url,
                    history,
                    "redirect_loop",
                    f"redirect loop detected at {next_url}",
                )
            if not same_origin(current_url, next_url):
                headers = strip_sensitive_headers(headers)
            current_url = next_url
        return self._redirect_error(
            request.url,
            current_url,
            history,
            "too_many_redirects",
            f"exceeded redirect limit of {request.redirect_limit}",
        )

    def _redirect_error(
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

    def _fetch_once(
        self,
        url: str,
        request: FetchRequest,
        deadline: Deadline,
        headers: dict[str, str],
    ) -> FetchResult:
        timings = TimingBreakdown()
        started = time.perf_counter()
        sock: socket.socket | None = None

        def fail(category: str, message: str) -> FetchResult:
            timings.total = time.perf_counter() - started
            return _error_result(request.url, url, timings, self.name, category, message)

        try:
            parsed = parse_url(url)
            dns_start = time.perf_counter()
            infos = _resolve(parsed.host, parsed.port, deadline.cap(request.connect_timeout))
            timings.dns = time.perf_counter() - dns_start
            if request.block_private_addresses:
                infos = [info for info in infos if not _is_blocked_address(info[4][0])]
                if not infos:
                    raise FetchError(
                        "blocked_address",
                        f"refusing to connect to non-public host {parsed.host}",
                    )
            if not infos:
                raise FetchError("dns_error", f"no DNS results for {parsed.host}")
            last_error: OSError | None = None
            candidate: socket.socket | None = None
            connect_started = time.perf_counter()
            for family, socktype, proto, _canonname, sockaddr in infos:
                try:
                    candidate = socket.socket(family, socktype, proto)
                    candidate.settimeout(deadline.cap(request.connect_timeout))
                    candidate.connect(sockaddr)
                    sock = candidate
                    candidate = None
                    break
                except OSError as exc:
                    last_error = exc
                    if candidate is not None:
                        candidate.close()
                        candidate = None
            timings.tcp_connect = time.perf_counter() - connect_started
            if sock is None:
                raise FetchError("connection_error", str(last_error or "could not connect"))
            if parsed.scheme == "https":
                tls_started = time.perf_counter()
                context = ssl.create_default_context()
                context.minimum_version = ssl.TLSVersion.TLSv1_2
                sock.settimeout(deadline.cap(request.connect_timeout))
                sock = context.wrap_socket(sock, server_hostname=parsed.host)
                timings.tls_handshake = time.perf_counter() - tls_started
            outbound = build_get_request(url, request.user_agent, headers)
            write_started = time.perf_counter()
            sock.settimeout(deadline.cap(request.read_timeout))
            sock.sendall(outbound)
            timings.request_write = time.perf_counter() - write_started
            status_code, reason, response_headers, body = read_http_response(
                sock,
                request.max_response_bytes,
                timings,
                deadline,
                request.read_timeout,
            )
            body = decompress_body(
                body,
                _header(response_headers, "Content-Encoding"),
                request.max_response_bytes,
            )
            timings.total = time.perf_counter() - started
            return FetchResult(
                url=request.url,
                final_url=url,
                status_code=status_code,
                reason=reason,
                headers=response_headers,
                body=body,
                timings=timings,
                transport=self.name,
            )
        except socket.gaierror as exc:
            return fail("dns_error", str(exc))
        except ssl.SSLError as exc:
            return fail("tls_error", str(exc))
        except TimeoutError as exc:
            return fail("read_timeout", str(exc))
        except MalformedResponse as exc:
            return fail(exc.category, str(exc))
        except FetchError as exc:
            return fail(exc.category, str(exc))
        except (ValueError, UnicodeError) as exc:
            return fail("malformed_url", str(exc))
        except OSError as exc:
            return fail("connection_error", str(exc))
        finally:
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass


def _resolve(host: str, port: int, timeout: float) -> list:
    """Resolve host:port with a wall-clock timeout (getaddrinfo itself has none)."""
    outcome: dict[str, object] = {}

    def worker() -> None:
        try:
            outcome["infos"] = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except Exception as exc:  # noqa: BLE001 - any resolver failure maps to dns_error
            outcome["error"] = exc

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        raise FetchError("dns_error", f"DNS resolution timed out for {host}")
    error = outcome.get("error")
    if error is not None:
        if isinstance(error, OSError):
            raise error  # socket.gaierror etc. are categorized by _fetch_once
        raise FetchError("dns_error", f"DNS resolution failed for {host}: {error}")
    return outcome.get("infos", [])  # type: ignore[return-value]


def parse_url(url: str) -> ParsedURL:
    parsed = urlsplit(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise FetchError("unsupported_scheme", f"unsupported URL scheme: {parsed.scheme}")
    if not parsed.hostname:
        raise FetchError("malformed_url", f"URL has no host: {url}")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    path = parsed.path or "/"
    return ParsedURL(parsed.scheme, parsed.hostname, port, path, parsed.query)


def _is_blocked_address(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


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
