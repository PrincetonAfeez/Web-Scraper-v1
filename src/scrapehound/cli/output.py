"""CLI formatting helpers."""

from __future__ import annotations

import json

from scrapehound.models import CrawlSummary, FetchResult


def print_fetch_result(result: FetchResult, *, trace: bool = False) -> None:
    if result.error_category:
        print(f"ERROR {result.error_category}: {result.error_message}")
        return
    print(f"{result.status_code} {result.reason or '-'} {result.final_url}")
    print(f"bytes={len(result.body)} transport={result.transport} redirects={len(result.redirect_history)}")
    content_type = _header(result.headers, "Content-Type")
    if content_type:
        print(f"content-type={content_type}")
    if trace:
        print("timings=" + json.dumps(result.timings.as_dict(), sort_keys=True))
        for name, value in result.headers.items():
            print(f"header {name}: {value}")


def print_summary(summary: CrawlSummary) -> None:
    print(f"job_id={summary.job_id}")
    print(f"pages={summary.pages} failures={summary.failures} pending={summary.pending}")
    print(f"run_fetched={summary.fetched} run_failed={summary.failed} run_skipped={summary.skipped}")
    print("frontier=" + json.dumps(summary.details.get("frontier", {}), sort_keys=True))


def print_verify_report(report: dict) -> None:
    valid_count = len(report["valid"])
    mismatch_count = len(report["mismatches"])
    missing_count = len(report["missing"])
    print(
        f"verified {report['total']} pages: "
        f"{valid_count} valid, {mismatch_count} mismatch, {missing_count} missing"
    )
    for item in report["mismatches"]:
        print(
            f"mismatch id={item['id']} url={item['url']} "
            f"stored={item['stored']} computed={item['computed']}"
        )
    for item in report["missing"]:
        print(f"missing id={item['id']} url={item['url']} reason={item['reason']}")


def _header(headers: dict[str, str], name: str) -> str | None:
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return None
