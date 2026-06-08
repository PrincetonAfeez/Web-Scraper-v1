# scrapehound

`scrapehound` is a Python command-line web scraper built as a Networking and Protocols capstone. It demonstrates the full path from a seed URL to DNS, TCP, optional TLS, hand-built HTTP/1.1 request bytes, response parsing, HTML link extraction, SQLite-backed crawl state, robots.txt checks, and polite rate limiting.

This is production-minded for capstone scale, not a public-internet-scale crawler.

## Quick Start

Install the project in editable mode from this folder:

```powershell
python -m pip install -e .
```

Run the local deterministic fixture server:

```powershell
python -m server.wsgi_fixture_app --port 8000
```

In another terminal, fetch one page through the raw socket backend:

```powershell
scrapehound scrape http://localhost:8000/page --transport raw_socket --trace
```

Run a small crawl:

```powershell
scrapehound crawl http://localhost:8000/page --db demo.sqlite --max-pages 10 --delay 0 --trace
```

Inspect results:

```powershell
scrapehound stats --db demo.sqlite
scrapehound export --db demo.sqlite --format json
```

## Capstone Rubric Map

| Proof point | Where it lives |
| --- | --- |
| Manual HTTP request bytes | `src/scrapehound/http/request.py` |
| DNS/TCP/TLS socket fetch | `src/scrapehound/transport/socket_fetcher.py` |
| Status line, headers, Content-Length, chunked parsing | `src/scrapehound/http/parser.py`, `src/scrapehound/http/chunked.py` |
| Redirect hop limit | `src/scrapehound/transport/redirects.py` |
| HTML extraction with stdlib parser | `src/scrapehound/parse/stdlib_parser.py` |
| URL normalization and dedup | `src/scrapehound/crawl/normalize.py`, `src/scrapehound/storage/repositories.py` |
| Robots.txt subset and Crawl-delay | `src/scrapehound/politeness/robots.py` |
| Per-domain rate limiting | `src/scrapehound/politeness/rate_limit.py` |
| SQLite frontier and resume | `src/scrapehound/storage/schema.sql`, `src/scrapehound/crawl/engine.py` |
| WSGI fixture app | `server/wsgi_fixture_app.py` |

## Ethics And Safe Defaults

`scrapehound` defaults to polite behavior:

- honors robots.txt unless `--ignore-robots` is passed
- stays on the seed domain unless additional domains are allowlisted in code/config
- uses max pages, max depth, max response bytes, request timeouts, redirect limits, and retry budgets
- sends a descriptive `User-Agent`
- records skipped URLs and stable failure categories

Do not use this project to bypass logins, solve CAPTCHAs, scrape private data, evade blocking, or crawl sites that prohibit automated access.

## Architecture

The crawler depends on interfaces instead of concrete transport implementations:

```text
CLI -> crawl engine -> scheduler/politeness -> Fetcher interface
                                          -> Parser interface
                                          -> SQLite repositories
```

The raw socket backend is the learning artifact. The library backend exists to show the same crawler can use a mature HTTP implementation behind the same `Fetcher` interface.

## Tests

```powershell
python -m pytest
```

The test suite includes protocol parsing, chunked decoding, URL normalization, robots parsing, rate limiting, HTML parsing, raw socket integration against the WSGI fixture, and an end-to-end crawl.
