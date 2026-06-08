"""Small TOML configuration loader with CLI override support."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from scrapehound.models import CrawlOptions


def load_config(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(path)
    with config_path.open("rb") as handle:
        return tomllib.load(handle)


def options_from_config(config: dict[str, Any], **overrides: Any) -> CrawlOptions:
    crawl = config.get("crawl", {})
    http = config.get("http", {})
    storage = config.get("storage", {})
    defaults = CrawlOptions()
    allowed_domains = crawl.get("allowed_domains", [])
    if isinstance(allowed_domains, str):
        allowed_domains = [allowed_domains]
    options = CrawlOptions(
        db_path=storage.get("db_path", defaults.db_path),
        transport=http.get("transport", defaults.transport),
        user_agent=http.get("user_agent", defaults.user_agent),
        max_pages=int(crawl.get("max_pages", defaults.max_pages)),
        max_depth=int(crawl.get("max_depth", defaults.max_depth)),
        max_response_bytes=int(crawl.get("max_response_bytes", defaults.max_response_bytes)),
        connect_timeout=float(http.get("connect_timeout", defaults.connect_timeout)),
        read_timeout=float(http.get("read_timeout", defaults.read_timeout)),
        total_timeout=float(http.get("total_timeout", defaults.total_timeout)),
        redirect_limit=int(crawl.get("redirect_limit", defaults.redirect_limit)),
        retry_count=int(crawl.get("retry_count", defaults.retry_count)),
        min_delay_seconds=float(crawl.get("min_delay_seconds", defaults.min_delay_seconds)),
        obey_robots=bool(crawl.get("obey_robots", defaults.obey_robots)),
        stay_on_seed_domain=bool(crawl.get("stay_on_seed_domain", defaults.stay_on_seed_domain)),
        block_private_addresses=bool(crawl.get("block_private_addresses", defaults.block_private_addresses)),
        allowed_domains={str(domain).lower() for domain in allowed_domains},
    )
    for key, value in overrides.items():
        if value is not None and hasattr(options, key):
            setattr(options, key, value)
    return options
