"""HTTP/1.1 response parsing and socket body framing."""

from __future__ import annotations

import re
import socket
import time
from typing import TYPE_CHECKING

from scrapehound.exceptions import FetchError, MalformedResponse, ResponseTooLarge
from scrapehound.http.headers import CaseInsensitiveHeaders
from scrapehound.models import TimingBreakdown

if TYPE_CHECKING:
    from scrapehound.transport.timeouts import Deadline

HEADER_LIMIT = 64 * 1024

_HTTP_VERSION_RE = re.compile(r"HTTP/\d+\.\d+")
_TOKEN_RE = re.compile(r"[!#$%&'*+\-.^_`|~0-9A-Za-z]+")
_HEX_RE = re.compile(rb"[0-9A-Fa-f]+")
_DIGITS_RE = re.compile(r"[0-9]+")
# Statuses that never carry a message body regardless of framing headers.
_NO_BODY_STATUSES = frozenset({204, 304})


def parse_status_line(line: bytes) -> tuple[str, int, str]:
    text = line.decode("iso-8859-1")
    parts = text.split(" ", 2)
    if len(parts) < 2:
        raise MalformedResponse(f"invalid status line: {line!r}")
    version, code = parts[0], parts[1]
    reason = parts[2] if len(parts) > 2 else ""
    if not _HTTP_VERSION_RE.fullmatch(version):
        raise MalformedResponse(f"invalid HTTP version: {version}")
    try:
        status_code = int(code)
    except ValueError as exc:
        raise MalformedResponse(f"invalid status code: {code}") from exc
    if not 100 <= status_code <= 599:
        raise MalformedResponse(f"status code out of range: {status_code}")
    return version, status_code, reason.strip()


def parse_headers(header_block: bytes) -> CaseInsensitiveHeaders:
    headers = CaseInsensitiveHeaders()
    if not header_block:
        return headers
    for line in header_block.split(b"\r\n"):
        if not line:
            continue
        if b":" not in line:
            raise MalformedResponse(f"malformed header line: {line!r}")
        raw_name, raw_value = line.split(b":", 1)
        name = raw_name.decode("iso-8859-1")
        value = raw_value.decode("iso-8859-1").strip()
        if not _TOKEN_RE.fullmatch(name):
            raise MalformedResponse(f"invalid header name: {name!r}")
        if "\r" in value or "\n" in value:
            raise MalformedResponse(f"bare CR/LF in header value: {value!r}")
        if name in headers and name.lower() != "set-cookie":
            # RFC 7230 §3.2.2: combine repeated field-values with a comma.
            # Set-Cookie is exempt (cookies must never be comma-folded); keep last.
            headers[name] = f"{headers[name]}, {value}"
        else:
            headers[name] = value
    return headers


def parse_content_length(raw: str) -> int:
    values = set()
    for part in raw.split(","):
        token = part.strip()
        if not _DIGITS_RE.fullmatch(token):
            raise MalformedResponse(f"invalid Content-Length: {raw!r}")
        values.add(int(token))
    if len(values) != 1:
        raise MalformedResponse(f"conflicting Content-Length values: {raw!r}")
    return values.pop()


def split_response_head(data: bytes) -> tuple[bytes, bytes]:
    marker = data.find(b"\r\n\r\n")
    if marker < 0:
        raise MalformedResponse("response headers were incomplete")
    return data[:marker], data[marker + 4 :]


def parse_response_head(
    data: bytes,
) -> tuple[str, int, str, CaseInsensitiveHeaders, bytes]:
    head, remaining = split_response_head(data)
    lines = head.split(b"\r\n")
    if not lines:
        raise MalformedResponse("empty response")
    version, status_code, reason = parse_status_line(lines[0])
    headers = parse_headers(b"\r\n".join(lines[1:]))
    return version, status_code, reason, headers, remaining


class _Reader:
    """Wraps a socket so every recv is bounded by the request-wide deadline."""

    __slots__ = ("sock", "deadline", "read_timeout")

    def __init__(self, sock: socket.socket, deadline: Deadline, read_timeout: float):
        self.sock = sock
        self.deadline = deadline
        self.read_timeout = read_timeout

    def recv(self, size: int = 8192) -> bytes:
        # cap() raises FetchError("total_timeout") once the deadline elapses.
        self.sock.settimeout(self.deadline.cap(self.read_timeout))
        try:
            return self.sock.recv(size)
        except TimeoutError as exc:
            raise FetchError("read_timeout", "socket read timed out") from exc
        except OSError as exc:
            raise FetchError("connection_error", f"socket read failed: {exc}") from exc

    def recv_required(self, size: int = 8192) -> bytes:
        chunk = self.recv(size)
        if not chunk:
            raise MalformedResponse("connection closed before response completed")
        return chunk


def read_http_response(
    sock: socket.socket,
    max_response_bytes: int,
    timings: TimingBreakdown,
    deadline: Deadline,
    read_timeout: float,
) -> tuple[int, str, dict[str, str], bytes]:
    reader = _Reader(sock, deadline, read_timeout)
    start = time.perf_counter()
    first_byte_at: float | None = None
    buffer = bytearray()
    while b"\r\n\r\n" not in buffer:
        chunk = reader.recv_required()
        if first_byte_at is None:
            first_byte_at = time.perf_counter()
            timings.time_to_first_byte = first_byte_at - start
        buffer.extend(chunk)
        if len(buffer) > HEADER_LIMIT:
            raise ResponseTooLarge("response headers exceeded header limit")
    _version, status_code, reason, headers, body_buffer = parse_response_head(bytes(buffer))
    body_start = time.perf_counter()
    transfer_encoding = (headers.get("Transfer-Encoding", "") or "").lower()
    te_codings = [token.strip() for token in transfer_encoding.split(",") if token.strip()]
    has_content_length = "Content-Length" in headers
    if status_code in _NO_BODY_STATUSES or 100 <= status_code < 200:
        body = b""
    elif te_codings:
        if has_content_length:
            raise MalformedResponse("ambiguous framing: both Transfer-Encoding and Content-Length present")
        if te_codings[-1] != "chunked":
            raise MalformedResponse(f"unsupported transfer-encoding: {transfer_encoding}")
        body = _read_chunked_from_socket(reader, body_buffer, max_response_bytes)
    elif has_content_length:
        length = parse_content_length(headers["Content-Length"])
        body = _read_content_length(reader, body_buffer, length, max_response_bytes)
    else:
        body = _read_until_close(reader, body_buffer, max_response_bytes)
    timings.body_read = time.perf_counter() - body_start
    return status_code, reason, dict(headers), body


def _read_content_length(reader: _Reader, initial: bytes, length: int, max_response_bytes: int) -> bytes:
    if length > max_response_bytes:
        raise ResponseTooLarge()
    body = bytearray(initial[:length])
    while len(body) < length:
        chunk = reader.recv(min(8192, length - len(body)))
        if not chunk:
            raise MalformedResponse("connection closed before Content-Length was satisfied")
        body.extend(chunk)
    return bytes(body)


def _read_until_close(reader: _Reader, initial: bytes, max_response_bytes: int) -> bytes:
    body = bytearray(initial)
    if len(body) > max_response_bytes:
        raise ResponseTooLarge()
    while True:
        chunk = reader.recv()
        if not chunk:
            return bytes(body)
        body.extend(chunk)
        if len(body) > max_response_bytes:
            raise ResponseTooLarge()


def _read_chunked_from_socket(reader: _Reader, initial: bytes, max_response_bytes: int) -> bytes:
    buffer = bytearray(initial)
    output = bytearray()
    while True:
        line = _pop_line(reader, buffer)
        raw_size = line.split(b";", 1)[0].strip()
        if not _HEX_RE.fullmatch(raw_size):
            raise MalformedResponse(f"invalid chunk size: {raw_size!r}")
        size = int(raw_size, 16)
        if size == 0:
            _consume_trailers(reader, buffer)
            return bytes(output)
        if len(output) + size > max_response_bytes:
            raise ResponseTooLarge()
        _ensure_bytes(reader, buffer, size + 2)
        output.extend(buffer[:size])
        del buffer[:size]
        if buffer[:2] != b"\r\n":
            raise MalformedResponse("chunk body missing trailing CRLF")
        del buffer[:2]


def _pop_line(reader: _Reader, buffer: bytearray) -> bytes:
    while b"\r\n" not in buffer:
        if len(buffer) > HEADER_LIMIT:
            raise MalformedResponse("line exceeded maximum length")
        buffer.extend(reader.recv_required())
    index = buffer.find(b"\r\n")
    line = bytes(buffer[:index])
    del buffer[: index + 2]
    return line


def _ensure_bytes(reader: _Reader, buffer: bytearray, count: int) -> None:
    while len(buffer) < count:
        buffer.extend(reader.recv_required())


def _consume_trailers(reader: _Reader, buffer: bytearray) -> None:
    while True:
        line = _pop_line(reader, buffer)
        if not line:
            return
