"""Allow `python -m scrapehound` after install or with PYTHONPATH=src."""

from scrapehound.cli.main import main

if __name__ == "__main__":
    raise SystemExit(main())
