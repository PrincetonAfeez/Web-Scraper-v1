# Demo Script

## 1. Raw HTTP

```powershell
python -m server.wsgi_fixture_app --port 8000
python -m scrapehound.cli.main scrape http://localhost:8000/page --transport raw_socket --trace
```

Talk through URL parsing, DNS, TCP, request bytes, status line, headers, body framing, and timings.

## 2. Polite Crawl

```powershell
python -m scrapehound.cli.main crawl http://localhost:8000/page --db demo.sqlite --max-pages 20 --delay 0 --trace
```

Show robots fetching, disallowed URL skips, rate limiting, SQLite pages, and deduplication.

## 3. Failure Handling

Fetch `/retry-after` (`rate_limited`), `/unavailable` (`server_error`), and `/large` (`response_too_large`) to show stable failure categories. `/redirect` demonstrates redirect following (it lands on a `200`), and `/slow` only fails when you pass a low timeout, e.g. `--total-timeout 0.5`.

## 4. Transport Swap

```powershell
python -m scrapehound.cli.main scrape http://localhost:8000/page --transport library --trace
```

Explain that the crawler sees the same `FetchResult` model even though the transport implementation changes.
