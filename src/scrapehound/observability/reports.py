"""Human-readable report helpers."""

from __future__ import annotations

from scrapehound.models import CrawlSummary


def summary_report(summary: CrawlSummary) -> str:
    return (
        f"job {summary.job_id}: pages={summary.pages}, failures={summary.failures}, "
        f"pending={summary.pending}, fetched_this_run={summary.fetched}"
    )
