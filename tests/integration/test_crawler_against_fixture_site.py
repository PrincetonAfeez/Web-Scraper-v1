"""Integration test for crawler against fixture site."""

from __future__ import annotations

from scrapehound.crawl.engine import CrawlEngine
from scrapehound.models import CrawlOptions
from scrapehound.storage.repositories import Storage


def test_crawler_persists_pages_failures_and_frontier(fixture_server, tmp_path):
    db_path = str(tmp_path / "crawl.sqlite")
    options = CrawlOptions(
        db_path=db_path,
        max_pages=10,
        max_depth=2,
        min_delay_seconds=0,
        retry_count=0,
        user_agent="scrapehound-test",
    )
    summary = CrawlEngine(options).crawl(f"{fixture_server}/page")
    storage = Storage(db_path)
    exported = storage.export_json(summary.job_id)

    assert summary.pages >= 3
    assert any(page["title"] == "Fixture Page" for page in exported["pages"])
    assert any(failure["category"] == "robots_disallowed" for failure in exported["failures"])


def test_cli_crawl_command_runs_end_to_end(fixture_server, tmp_path, capsys):
    from scrapehound.cli.main import main

    db_path = tmp_path / "cli.sqlite"
    exit_code = main(
        [
            "crawl",
            f"{fixture_server}/page",
            "--db",
            str(db_path),
            "--max-pages",
            "5",
            "--max-depth",
            "1",
            "--delay",
            "0",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "job_id=" in captured.out
