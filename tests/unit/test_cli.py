"""Unit test for CLI."""

from __future__ import annotations

import pytest

from scrapehound.cli.exit_codes import CONFIG_ERROR
from scrapehound.cli.main import build_parser, main


def test_version_flag_prints_and_exits(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "scrapehound" in capsys.readouterr().out


def test_doctor_reports_runtime(capsys):
    assert main(["doctor"]) == 0
    out = capsys.readouterr().out
    assert "python=" in out
    assert "sqlite=" in out


def test_crawl_block_private_addresses_flag_defaults_to_none():
    # Absent flag must stay None so it does not override config.
    assert build_parser().parse_args(["crawl", "http://x/"]).block_private_addresses is None
    assert (
        build_parser().parse_args(["crawl", "http://x/", "--block-private-addresses"]).block_private_addresses is True
    )


def test_invalid_config_returns_config_error(tmp_path, capsys):
    bad = tmp_path / "bad.toml"
    bad.write_text("this is = = not valid toml", encoding="utf-8")
    assert main(["crawl", "http://x/", "--config", str(bad)]) == CONFIG_ERROR


def test_allow_domain_flag_is_repeatable():
    ns = build_parser().parse_args(["crawl", "http://x/", "--allow-domain", "a.com", "--allow-domain", "b.com"])
    assert ns.allow_domain == ["a.com", "b.com"]
    assert build_parser().parse_args(["crawl", "http://x/"]).allow_domain is None
