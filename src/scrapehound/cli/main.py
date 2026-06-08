"""scrapehound command line entry point."""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
import traceback
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from scrapehound.cli.exit_codes import CONFIG_ERROR, ERROR, INTERRUPTED, OK
from scrapehound.cli.logging_config import configure_trace_logging
from scrapehound.cli.output import print_fetch_result, print_summary, print_verify_report
from scrapehound.config import load_config, options_from_config
from scrapehound.crawl.engine import CrawlEngine
from scrapehound.exceptions import ConfigurationError
from scrapehound.models import CrawlOptions, FetchRequest
from scrapehound.politeness.robots import RobotsCache
from scrapehound.politeness.user_agent import DEFAULT_USER_AGENT
from scrapehound.storage.export import export_json
from scrapehound.storage.repositories import Storage
from scrapehound.transport import make_fetcher


def _version() -> str:
    try:
        return version("scrapehound")
    except PackageNotFoundError:
        return "0.1.0"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scrapehound", description="Protocol-focused capstone web scraper")
    parser.add_argument("--version", action="version", version=f"scrapehound {_version()}")
    sub = parser.add_subparsers(dest="command", required=True)

    scrape = sub.add_parser("scrape", help="Fetch one URL")
    scrape.add_argument("url")
    scrape.add_argument("--config", default=None)
    scrape.add_argument("--transport", choices=["raw_socket", "library"], default=None)
    scrape.add_argument("--user-agent", default=None)
    scrape.add_argument("--connect-timeout", type=float, default=None)
    scrape.add_argument("--read-timeout", type=float, default=None)
    scrape.add_argument("--total-timeout", type=float, default=None)
    scrape.add_argument("--max-bytes", type=int, default=None)
    scrape.add_argument("--redirect-limit", type=int, default=None)
    scrape.add_argument(
        "--block-private-addresses",
        action="store_true",
        help="Refuse to connect to loopback/private/link-local hosts",
    )
    scrape.add_argument("--trace", action="store_true")

    crawl = sub.add_parser("crawl", help="Crawl from a seed URL")
    _add_crawl_args(crawl)
    crawl.add_argument("url")

    resume = sub.add_parser("resume", help="Resume a persisted crawl job")
    resume.add_argument("--db", default="scrapehound.sqlite")
    resume.add_argument("--job-id", type=int, default=None)
    resume.add_argument("--config", default=None)
    resume.add_argument("--trace", action="store_true")
    resume.add_argument("--delay", type=float, default=None)

    stats = sub.add_parser("stats", help="Show crawl stats from SQLite")
    stats.add_argument("--db", default="scrapehound.sqlite")
    stats.add_argument("--job-id", type=int, default=None)

    export = sub.add_parser("export", help="Export pages and failures")
    export.add_argument("--db", default="scrapehound.sqlite")
    export.add_argument("--job-id", type=int, default=None)
    export.add_argument("--format", choices=["json"], default="json")
    export.add_argument("--output", default=None)

    verify = sub.add_parser("verify", help="Verify stored page body integrity")
    verify.add_argument("--db", default="scrapehound.sqlite")
    verify.add_argument("--job-id", type=int, default=None)

    robots = sub.add_parser("robots", help="Check robots.txt policy for a URL")
    robots.add_argument("url")
    robots.add_argument("--transport", choices=["raw_socket", "library"], default="raw_socket")
    robots.add_argument("--user-agent", default=DEFAULT_USER_AGENT)

    serve = sub.add_parser("serve-fixture", help="Run the deterministic WSGI fixture server")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)

    sub.add_parser("doctor", help="Print basic runtime diagnostics")
    return parser


def _add_crawl_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", default=None)
    parser.add_argument("--db", default=None)
    parser.add_argument("--transport", choices=["raw_socket", "library"], default=None)
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--max-depth", type=int, default=None)
    parser.add_argument("--max-bytes", type=int, default=None)
    parser.add_argument("--connect-timeout", type=float, default=None)
    parser.add_argument("--read-timeout", type=float, default=None)
    parser.add_argument("--total-timeout", type=float, default=None)
    parser.add_argument("--redirect-limit", type=int, default=None)
    parser.add_argument("--retry-count", type=int, default=None)
    parser.add_argument("--delay", type=float, default=None, help="Minimum delay per domain in seconds")
    parser.add_argument(
        "--allow-domain",
        action="append",
        default=None,
        metavar="DOMAIN",
        help="Additional in-scope domain (repeatable); merged with config",
    )
    parser.add_argument("--ignore-robots", action="store_true")
    parser.add_argument(
        "--block-private-addresses",
        action="store_true",
        default=None,
        help="Refuse to connect to loopback/private/link-local hosts (SSRF guard)",
    )
    parser.add_argument("--trace", action="store_true")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "scrape":
            return _cmd_scrape(args)
        if args.command == "crawl":
            return _cmd_crawl(args)
        if args.command == "resume":
            return _cmd_resume(args)
        if args.command == "stats":
            return _cmd_stats(args)
        if args.command == "export":
            return _cmd_export(args)
        if args.command == "verify":
            return _cmd_verify(args)
        if args.command == "robots":
            return _cmd_robots(args)
        if args.command == "serve-fixture":
            return _cmd_serve_fixture(args)
        if args.command == "doctor":
            return _cmd_doctor()
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return INTERRUPTED
    except FileNotFoundError as exc:
        print(f"config file not found: {exc}", file=sys.stderr)
        return CONFIG_ERROR
    except (tomllib.TOMLDecodeError, ConfigurationError) as exc:
        print(f"invalid configuration: {exc}", file=sys.stderr)
        return CONFIG_ERROR
    except Exception as exc:
        if getattr(args, "trace", False):
            traceback.print_exc()
        else:
            print(f"scrapehound error: {exc}", file=sys.stderr)
        return ERROR
    return OK


def _pick(cli_value, config_value, default):  # type: ignore[no-untyped-def]
    if cli_value is not None:
        return cli_value
    return config_value if config_value is not None else default


def _cmd_scrape(args: argparse.Namespace) -> int:
    if args.trace:
        configure_trace_logging()
    config = load_config(args.config)
    http = config.get("http", {})
    crawl = config.get("crawl", {})
    defaults = CrawlOptions()
    fetcher = make_fetcher(_pick(args.transport, http.get("transport"), defaults.transport))
    result = fetcher.fetch(
        FetchRequest(
            url=args.url,
            user_agent=_pick(args.user_agent, http.get("user_agent"), DEFAULT_USER_AGENT),
            connect_timeout=float(
                _pick(
                    args.connect_timeout,
                    http.get("connect_timeout"),
                    defaults.connect_timeout,
                )
            ),
            read_timeout=float(_pick(args.read_timeout, http.get("read_timeout"), defaults.read_timeout)),
            total_timeout=float(
                _pick(
                    args.total_timeout,
                    http.get("total_timeout"),
                    defaults.total_timeout,
                )
            ),
            max_response_bytes=int(
                _pick(
                    args.max_bytes,
                    crawl.get("max_response_bytes"),
                    defaults.max_response_bytes,
                )
            ),
            redirect_limit=int(
                _pick(
                    args.redirect_limit,
                    crawl.get("redirect_limit"),
                    defaults.redirect_limit,
                )
            ),
            block_private_addresses=args.block_private_addresses,
        )
    )
    print_fetch_result(result, trace=args.trace)
    return OK if not result.error_category else ERROR


def _cmd_crawl(args: argparse.Namespace) -> int:
    if args.trace:
        configure_trace_logging()
    config = load_config(args.config)
    options = options_from_config(
        config,
        db_path=args.db,
        transport=args.transport,
        max_pages=args.max_pages,
        max_depth=args.max_depth,
        max_response_bytes=args.max_bytes,
        connect_timeout=args.connect_timeout,
        read_timeout=args.read_timeout,
        total_timeout=args.total_timeout,
        redirect_limit=args.redirect_limit,
        retry_count=args.retry_count,
        min_delay_seconds=args.delay,
        obey_robots=False if args.ignore_robots else None,
        block_private_addresses=args.block_private_addresses,
        trace=args.trace,
    )
    if args.allow_domain:
        options.allowed_domains |= {domain.lower() for domain in args.allow_domain}
    if args.ignore_robots:
        print(
            "WARNING: robots.txt checks disabled by explicit --ignore-robots flag",
            file=sys.stderr,
        )
    engine = CrawlEngine(options)
    summary = engine.crawl(args.url)
    print_summary(summary)
    return OK


def _cmd_resume(args: argparse.Namespace) -> int:
    if args.trace:
        configure_trace_logging()
    with Storage(args.db) as storage:
        job_id = args.job_id or storage.latest_job_id()
        if job_id is None:
            print("no crawl jobs found", file=sys.stderr)
            return ERROR
        job = storage.get_job(job_id)
        if not job:
            print(f"job not found: {job_id}", file=sys.stderr)
            return ERROR
        config = load_config(args.config)
        options = options_from_config(config, db_path=args.db, trace=args.trace, min_delay_seconds=args.delay)
        engine = CrawlEngine(options, storage=storage)
        summary = engine.crawl(job["seed_url"], job_id=job_id)
        print_summary(summary)
    return OK


def _cmd_stats(args: argparse.Namespace) -> int:
    with Storage(args.db) as storage:
        print(json.dumps(storage.stats(args.job_id), indent=2, sort_keys=True))
    return OK


def _cmd_export(args: argparse.Namespace) -> int:
    with Storage(args.db) as storage:
        data = export_json(storage, args.job_id)
    if args.output:
        Path(args.output).write_text(data, encoding="utf-8")
    else:
        print(data)
    return OK


def _cmd_verify(args: argparse.Namespace) -> int:
    with Storage(args.db) as storage:
        report = storage.verify_pages(args.job_id)
    print_verify_report(report)
    if report["mismatches"] or report["missing"]:
        return ERROR
    return OK


def _cmd_robots(args: argparse.Namespace) -> int:
    cache = RobotsCache(make_fetcher(args.transport), args.user_agent)
    allowed = cache.allowed(args.url)
    delay = cache.crawl_delay(args.url)
    print(json.dumps({"url": args.url, "allowed": allowed, "crawl_delay": delay}, sort_keys=True))
    return OK


def _cmd_serve_fixture(args: argparse.Namespace) -> int:
    from server.wsgi_fixture_app import serve

    serve(host=args.host, port=args.port)
    return OK


def _cmd_doctor() -> int:
    import sqlite3

    print(f"scrapehound={_version()}")
    print(f"python={sys.version.split()[0]}")
    print(f"sqlite={sqlite3.sqlite_version}")
    print("transports=raw_socket,library")
    return OK


if __name__ == "__main__":
    raise SystemExit(main())
