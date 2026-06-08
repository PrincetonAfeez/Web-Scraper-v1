"""Shared typed models used across scraper layers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from scrapehound.politeness.user_agent import DEFAULT_USER_AGENT


@dataclass(slots=True)
class TimingBreakdown:
    dns: float = 0.0
    tcp_connect: float = 0.0
    tls_handshake: float = 0.0
    request_write: float = 0.0
    time_to_first_byte: float = 0.0
    body_read: float = 0.0
    total: float = 0.0

    def as_dict(self) -> dict[str, float]:
        return {
            "dns": self.dns,
            "tcp_connect": self.tcp_connect,
            "tls_handshake": self.tls_handshake,
            "request_write": self.request_write,
            "time_to_first_byte": self.time_to_first_byte,
            "body_read": self.body_read,
            "total": self.total,
        }


@dataclass(slots=True)
class FetchRequest:
    url: str
    user_agent: str
    connect_timeout: float = 5.0
    read_timeout: float = 10.0
    total_timeout: float = 30.0
    max_response_bytes: int = 2 * 1024 * 1024
    redirect_limit: int = 5
    headers: dict[str, str] = field(default_factory=dict)
    # When True, the raw-socket fetcher refuses to connect to loopback,
    # private, link-local, or other non-public addresses (SSRF guard).
    block_private_addresses: bool = False


@dataclass(slots=True)
class RedirectHop:
    url: str
    status_code: int
    location: str


@dataclass(slots=True)
class FetchResult:
    url: str
    final_url: str
    status_code: int | None
    reason: str
    headers: dict[str, str]
    body: bytes
    timings: TimingBreakdown
    redirect_history: list[RedirectHop] = field(default_factory=list)
    transport: str = "unknown"
    error_category: str | None = None
    error_message: str | None = None

    @property
    def ok(self) -> bool:
        return self.error_category is None and self.status_code is not None

    @property
    def content_type(self) -> str:
        for key, value in self.headers.items():
            if key.lower() == "content-type":
                return value
        return ""


@dataclass(slots=True)
class ParsedPage:
    final_url: str
    title: str | None
    description: str | None
    headings: list[str]
    links: list[str]
    text_encoding: str


@dataclass(slots=True)
class CrawlOptions:
    db_path: str = "scrapehound.sqlite"
    transport: str = "raw_socket"
    user_agent: str = DEFAULT_USER_AGENT
    max_pages: int = 100
    max_depth: int = 2
    max_response_bytes: int = 2 * 1024 * 1024
    connect_timeout: float = 5.0
    read_timeout: float = 10.0
    total_timeout: float = 30.0
    redirect_limit: int = 5
    retry_count: int = 2
    min_delay_seconds: float = 1.0
    obey_robots: bool = True
    stay_on_seed_domain: bool = True
    block_private_addresses: bool = False
    allowed_domains: set[str] = field(default_factory=set)
    trace: bool = False
    allowed_content_types: tuple[str, ...] = ("text/html", "application/xhtml+xml")


@dataclass(slots=True)
class CrawlSummary:
    job_id: int
    fetched: int
    failed: int
    skipped: int
    pending: int
    pages: int
    failures: int
    details: dict[str, Any] = field(default_factory=dict)
