"""A small robots.txt subset parser for capstone crawling."""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from scrapehound.models import FetchRequest


def _compile_rule(pattern: str) -> re.Pattern[str]:
    """Compile a robots path pattern (supporting ``*`` and a trailing ``$``)."""
    anchored_end = pattern.endswith("$")
    body = pattern[:-1] if anchored_end else pattern
    regex = ["^"]
    for char in body:
        regex.append(".*" if char == "*" else re.escape(char))
    if anchored_end:
        regex.append("$")
    return re.compile("".join(regex))


@dataclass(slots=True)
class _Rule:
    pattern: str
    regex: re.Pattern[str]

    @property
    def specificity(self) -> int:
        # Longer patterns are more specific; the trailing "$" does not count.
        return len(self.pattern.rstrip("$"))


def _make_rules(patterns: list[str]) -> list[_Rule]:
    return [_Rule(pattern, _compile_rule(pattern)) for pattern in patterns]


@dataclass(slots=True)
class RobotsRules:
    allow: list[str] = field(default_factory=list)
    disallow: list[str] = field(default_factory=list)
    crawl_delay: float | None = None
    sitemaps: list[str] = field(default_factory=list)
    _allow_rules: list[_Rule] | None = field(default=None, compare=False, repr=False)
    _disallow_rules: list[_Rule] | None = field(default=None, compare=False, repr=False)

    @staticmethod
    def _best_match(target: str, rules: list[_Rule]) -> int:
        best = -1
        for rule in rules:
            if rule.regex.match(target) and rule.specificity > best:
                best = rule.specificity
        return best

    def allowed(self, url: str) -> bool:
        # Compile patterns once and cache, rather than on every call.
        if self._allow_rules is None:
            self._allow_rules = _make_rules(self.allow)
            self._disallow_rules = _make_rules(self.disallow)
        parsed = urlsplit(url)
        target = parsed.path or "/"
        if parsed.query:
            target = f"{target}?{parsed.query}"
        disallow_len = self._best_match(target, self._disallow_rules)
        if disallow_len < 0:
            return True
        allow_len = self._best_match(target, self._allow_rules)
        # Per RFC 9309, the most specific rule wins; ties go to Allow.
        return allow_len >= disallow_len


def parse_robots(text: str, user_agent: str = "*") -> RobotsRules:
    groups: list[tuple[list[str], RobotsRules]] = []
    current_agents: list[str] = []
    current_rules = RobotsRules()
    saw_directive = False
    sitemaps: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if key == "sitemap":
            # Sitemap is a file-global directive, independent of agent groups.
            if value:
                sitemaps.append(value)
            continue
        if key == "user-agent":
            if saw_directive:
                groups.append((current_agents, current_rules))
                current_agents = []
                current_rules = RobotsRules()
                saw_directive = False
            if value:
                current_agents.append(value.lower())
        elif key == "allow":
            saw_directive = True
            if value:
                current_rules.allow.append(value)
        elif key == "disallow":
            saw_directive = True
            if value:
                current_rules.disallow.append(value)
        elif key == "crawl-delay":
            saw_directive = True
            try:
                current_rules.crawl_delay = float(value)
            except ValueError:
                pass
    if current_agents or saw_directive:
        groups.append((current_agents, current_rules))

    selected = _select_group(groups, user_agent)
    selected.sitemaps = sitemaps
    return selected


def _select_group(groups: list[tuple[list[str], RobotsRules]], user_agent: str) -> RobotsRules:
    token = _product_token(user_agent)
    best_specific: RobotsRules | None = None
    best_len = -1
    wildcard: RobotsRules | None = None
    for agents, rules in groups:
        for agent in agents:
            if agent == "*":
                wildcard = rules
            elif agent and token.startswith(agent) and len(agent) > best_len:
                # RFC 9309: longest matching agent prefix wins.
                best_len = len(agent)
                best_specific = rules
    return best_specific or wildcard or RobotsRules()


def _product_token(user_agent: str) -> str:
    parts = user_agent.lower().split("/", 1)[0].split()
    return parts[0] if parts else ""


class RobotsCache:
    def __init__(
        self,
        fetcher,  # type: ignore[no-untyped-def]
        user_agent: str,
        *,
        max_response_bytes: int = 128 * 1024,
        ttl_seconds: float = 3600.0,
    ) -> None:
        self.fetcher = fetcher
        self.user_agent = user_agent
        self.max_response_bytes = max_response_bytes
        self.ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        self._rules: dict[str, tuple[float, RobotsRules]] = {}

    def rules_for(self, url: str) -> RobotsRules:
        parsed = urlsplit(url)
        scheme = parsed.scheme or "http"
        host = parsed.hostname or ""
        port = parsed.port
        origin = f"{scheme}://{host}:{port}" if port else f"{scheme}://{host}"
        now = time.time()
        # Hold the lock across the fetch so concurrent workers neither race the
        # cache nor fetch the same robots.txt twice.
        with self._lock:
            cached = self._rules.get(origin)
            if cached is not None and now - cached[0] < self.ttl_seconds:
                return cached[1]
            rules = self._fetch_rules(scheme, host, port)
            self._rules[origin] = (now, rules)
            return rules

    def _fetch_rules(self, scheme: str, host: str, port: int | None) -> RobotsRules:
        authority = f"[{host}]" if ":" in host else host
        if port:
            authority = f"{authority}:{port}"
        robots_url = f"{scheme}://{authority}/robots.txt"
        result = self.fetcher.fetch(
            FetchRequest(
                url=robots_url,
                user_agent=self.user_agent,
                connect_timeout=5.0,
                read_timeout=5.0,
                total_timeout=10.0,
                max_response_bytes=self.max_response_bytes,
                redirect_limit=3,
            )
        )
        status = result.status_code
        if status is not None and 200 <= status < 300:
            # An empty 2xx robots.txt parses to no rules, i.e. allow everything.
            return parse_robots(result.body.decode("utf-8-sig", errors="replace"), self.user_agent)
        if status is not None and 400 <= status < 500:
            # RFC 9309 §2.3.1.2: an unavailable (4xx) robots.txt imposes no rules.
            return RobotsRules()
        # RFC 9309 §2.3.1.3: 5xx or unreachable robots.txt → assume disallow all.
        return RobotsRules(disallow=["/"])

    def allowed(self, url: str) -> bool:
        return self.rules_for(url).allowed(url)

    def crawl_delay(self, url: str) -> float | None:
        return self.rules_for(url).crawl_delay

    def sitemaps(self, url: str) -> list[str]:
        return self.rules_for(url).sitemaps
