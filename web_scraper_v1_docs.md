# Architecture Decision Record
## App — Web Scraper v1
**Web Crawling Systems Group | Document 1 of 5**
**Status: Accepted**

---

## Context

The Web Crawling Systems group requires a Python command-line web scraper that demonstrates the networking path from a seed URL to a persisted crawl result. The project must show DNS lookup, TCP connection, optional TLS, hand-built HTTP/1.1 request bytes, response parsing, HTML link extraction, crawl frontier management, robots.txt policy checks, rate limiting, retries, redirects, and SQLite-backed resume/export behavior.

The project is intentionally a capstone-scale crawler. It is production-minded in its boundaries and safety defaults, but it is not a public-internet-scale crawler and does not claim to bypass site restrictions, logins, bot protections, CAPTCHAs, or anti-abuse systems.

The selected architecture separates protocol, crawling, parsing, politeness, and persistence:

```text
CLI
  -> CrawlEngine
      -> Scheduler / RateLimiter / RobotsCache
      -> Fetcher interface
          -> RawSocketFetcher
          -> LibraryFetcher
      -> Parser interface
      -> SQLite Storage repositories
```

The raw socket transport is the primary learning artifact. The library transport exists to prove that the crawler can operate behind the same fetcher contract while delegating HTTP details to the standard library.

---

## Decisions

### Decision 1 — Build a raw-socket HTTP fetcher

**Chosen:** `RawSocketFetcher` manually resolves DNS, opens sockets, wraps TLS, writes HTTP/1.1 GET request bytes, reads the response, parses framing, and returns a typed result.

**Rejected:** Using only `urllib`, `requests`, Scrapy, or Playwright.

**Reason:** The project is a Networking and Protocols capstone. Delegating the main protocol path would hide the learning target.

---

### Decision 2 — Provide a library fetcher behind the same interface

**Chosen:** `LibraryFetcher` uses Python's standard `urllib` stack behind the same `Fetcher` interface.

**Rejected:** Making the raw fetcher the only backend.

**Reason:** The second backend demonstrates interface design. The crawl engine depends on behavior, not implementation, and can run through either transport.

---

### Decision 3 — Use hand-built HTTP request serialization

**Chosen:** `build_get_request()` creates origin-form GET requests with Host, User-Agent, Accept, Accept-Encoding, and Connection headers.

**Rejected:** Letting a high-level HTTP package construct request bytes.

**Reason:** Request-line and header serialization are central protocol concepts. The implementation validates request targets, header names, header values, Host headers, default ports, IDNA hosts, and IPv6 host formatting.

---

### Decision 4 — Reject ambiguous response framing

**Chosen:** If a response contains both `Transfer-Encoding` and `Content-Length`, the parser raises `MalformedResponse`.

**Rejected:** Choosing one framing rule silently.

**Reason:** A crawler should avoid misreading response bodies. Rejecting ambiguous framing is safer and easier to explain in an academic protocol project.

---

### Decision 5 — Enforce explicit byte and time budgets

**Chosen:** Requests carry connect, read, total timeout, max response bytes, and redirect limit settings.

**Rejected:** Unbounded socket reads or unlimited redirects.

**Reason:** Scrapers need firm limits. Time and byte budgets prevent a single slow or large response from dominating a crawl.

---

### Decision 6 — Persist crawl state in SQLite

**Chosen:** Crawl jobs, frontier state, pages, and failures live in SQLite.

**Rejected:** In-memory-only frontier or ad hoc JSON files.

**Reason:** SQLite provides durable resume, deduplication, job status, queryable stats, and simple export without requiring a server database.

---

### Decision 7 — Deduplicate by normalized URL per job

**Chosen:** The `frontier` table has `UNIQUE(job_id, normalized_url)` and repository code uses normalized URLs for frontier identity.

**Rejected:** Deduplicating only by raw URL string.

**Reason:** URLs can differ by case, default ports, fragments, path normalization, tracking parameters, and query order. Normalization reduces repeated work.

---

### Decision 8 — Default to seed-domain scope

**Chosen:** The crawler stays on the seed domain unless additional domains are allowlisted.

**Rejected:** Following every discovered external link.

**Reason:** Safe default scope is essential for a beginner crawler. It also keeps demo crawls bounded and predictable.

---

### Decision 9 — Honor robots.txt by default

**Chosen:** `CrawlOptions.obey_robots` defaults to true, and the CLI requires explicit `--ignore-robots` to disable checks.

**Rejected:** Treating robots.txt as optional by default.

**Reason:** The project has an ethics component. Respecting robots.txt should be the default behavior.

---

### Decision 10 — Implement a small robots.txt subset parser

**Chosen:** Support user-agent group selection, Allow, Disallow, Crawl-delay, Sitemap, `*`, trailing `$`, longest matching user-agent, most-specific path rule, and Allow ties.

**Rejected:** A full third-party robots parser.

**Reason:** A capstone should show the policy mechanics directly while remaining honest about scope.

---

### Decision 11 — Rate limit per domain

**Chosen:** Use a thread-safe per-domain `RateLimiter` that reserves the next allowed time atomically and sleeps outside the lock.

**Rejected:** A single global sleep or no delay.

**Reason:** Politeness is domain-specific. A global sleep would unnecessarily serialize unrelated domains; no delay would be impolite.

---

### Decision 12 — Retry only stable failure categories

**Chosen:** Retry status codes and categories such as DNS error, connection timeout, read timeout, 429, and server errors.

**Rejected:** Retrying every failure.

**Reason:** Retrying client errors and parse errors usually wastes traffic. Retry behavior should be deliberate and persisted in the frontier.

---

### Decision 13 — Record skipped and failed URLs

**Chosen:** Skips and failures are stored with categories and messages.

**Rejected:** Silently dropping disallowed, unsupported, failed, or out-of-scope URLs.

**Reason:** A crawler must explain what it did not crawl. Stable categories make debugging and reporting easier.

---

### Decision 14 — Use stdlib HTML parsing

**Chosen:** Use `html.parser.HTMLParser` to extract title, description, headings, base href, and links.

**Rejected:** BeautifulSoup, lxml, or browser rendering.

**Reason:** The runtime has no third-party dependencies. The parser is sufficient for capstone-scale HTML extraction and keeps the learning path simple.

---

### Decision 15 — Include a deterministic WSGI fixture server

**Chosen:** Ship `server.wsgi_fixture_app` with pages, robots.txt, redirects, retryable statuses, slow response, large response, and gzip response.

**Rejected:** Requiring live external websites for tests and demos.

**Reason:** A reproducible local fixture makes protocol, crawl, retry, robots, redirect, and parser behavior testable without relying on the public web.

---

## Consequences

**Positive:**
- The networking path is visible from URL to socket to response framing.
- The crawler can resume because frontier state is durable.
- Safe defaults reduce accidental over-crawling.
- Robots and rate limiting are first-class workflow steps.
- Fetcher interface keeps the engine independent from the HTTP backend.
- SQLite gives stats and export without infrastructure.
- The fixture server makes tests deterministic.
- Stable categories make failures auditable.

**Negative / Trade-offs:**
- The crawler is synchronous and single-process.
- It is not suitable for public-internet-scale crawling.
- The robots parser is a subset, not a full commercial crawler policy engine.
- The stdlib parser does not execute JavaScript.
- The raw socket backend implements only GET.
- It does not authenticate, maintain sessions, solve CAPTCHAs, or bypass access restrictions.
- The library transport cannot support the same private-address blocking guarantee as raw sockets.

---

## Alternatives Not Explored

- Scrapy.
- Browser automation.
- Async crawler with `asyncio`.
- Distributed frontier.
- PostgreSQL or Redis-backed queue.
- Full-text search/indexing.
- JavaScript rendering.
- Sitemap seeding.
- Full robots.txt policy coverage.
- Cookie/session management.
- Proxy rotation.
- Public-internet-scale politeness infrastructure.

---

*Constitution reference: Article 1 (Python fundamentals and architectural thinking), Article 3.3 (scope discipline), Article 4 (quality proportional to scope), Article 5 (trade-off documentation), Article 6 (behavior verification), and Article 7 (progressive complexity).*

---


# Technical Design Document
## App — Web Scraper v1
**Web Crawling Systems Group | Document 2 of 5**

---

## Overview

Web Scraper v1 ships as the `scrapehound` package and CLI. It is a protocol-focused crawler with two fetch transports, a synchronous crawl engine, a stdlib HTML parser, SQLite persistence, and a deterministic WSGI fixture app.

**Package:** `scrapehound`  
**Console script:** `scrapehound`  
**Python:** `>=3.11`  
**Runtime dependencies:** none  
**Dev dependencies:** pytest, Ruff, setuptools  
**Default transport:** `raw_socket`  
**Storage:** SQLite  
**Fixture server:** `python -m server.wsgi_fixture_app --port 8000`

---

## System Flow

```text
scrapehound crawl SEED_URL
  │
  ▼
CLI parses config + flags
  │
  ▼
CrawlOptions
  │
  ▼
CrawlEngine
  │
  ├── Storage creates or resumes crawl job
  ├── seed URL enqueued in frontier
  ├── DomainScope created from seed + allowlist
  ├── RobotsCache created when obey_robots=True
  ├── RateLimiter/Scheduler applies per-domain delay
  └── Fetcher selected by transport name
        │
        ▼
Fetch URL
  │
  ├── RawSocketFetcher or LibraryFetcher
  ├── Redirect policy
  ├── Timeout and byte budgets
  └── FetchResult
        │
        ▼
CrawlEngine classifies result
  │
  ├── retryable error/status → schedule retry
  ├── terminal error/status → save failure
  ├── unsupported content type → save skip/failure
  └── HTML page → parse + save page + enqueue links
```

---

## Module Layout

```text
Web-Scraper-v1/
  src/scrapehound/
    __init__.py
    config.py
    exceptions.py
    models.py
    cli/
      main.py
      output.py
      exit_codes.py
    crawl/
      engine.py
      frontier.py
      normalize.py
      retry.py
      scheduler.py
      scope.py
    http/
      chunked.py
      encoding.py
      headers.py
      parser.py
      request.py
      response.py
    parse/
      stdlib_parser.py
    politeness/
      rate_limit.py
      robots.py
      user_agent.py
    storage/
      db.py
      export.py
      repositories.py
      schema.sql
    transport/
      __init__.py
      base.py
      library_fetcher.py
      redirects.py
      socket_fetcher.py
      timeouts.py
  server/
    wsgi_fixture_app.py
  tests/
  pyproject.toml
  README.md
  .github/workflows/ci.yml
```

---

## Core Data Structures

### `TimingBreakdown`

Tracks:
- DNS lookup
- TCP connect
- TLS handshake
- request write
- time to first byte
- body read
- total time

Used by fetch results and persisted page timing JSON.

---

### `FetchRequest`

Fields:
- `url`
- `user_agent`
- connect/read/total timeouts
- `max_response_bytes`
- `redirect_limit`
- extra headers
- `block_private_addresses`

Purpose:
- fully describes one HTTP GET fetch budget and safety posture.

---

### `FetchResult`

Fields:
- original URL
- final URL
- status code
- reason
- headers
- body bytes
- timings
- redirect history
- transport name
- error category
- error message

Computed:
- `ok` is true only when no error category and status exists.
- `content_type` returns the response Content-Type header.

---

### `ParsedPage`

Fields:
- final URL
- title
- description
- headings
- links
- text encoding

Produced by `StdlibHTMLParser`.

---

### `CrawlOptions`

Important defaults:
- database path: `scrapehound.sqlite`
- transport: `raw_socket`
- max pages: `100`
- max depth: `2`
- max response bytes: `2 MiB`
- connect timeout: `5s`
- read timeout: `10s`
- total timeout: `30s`
- redirect limit: `5`
- retry count: `2`
- per-domain delay: `1s`
- obey robots: true
- stay on seed domain: true
- block private addresses: false
- allowed content types: HTML/XHTML

---

### `CrawlSummary`

Fields:
- job ID
- fetched count
- failed count
- skipped count
- pending count
- persisted page count
- persisted failure count
- details dictionary

Returned by `CrawlEngine.crawl()` and printed by the CLI.

---

## Component Details

### CLI

Subcommands:
- `scrape`
- `crawl`
- `resume`
- `stats`
- `export`
- `robots`
- `serve-fixture`
- `doctor`

The CLI merges TOML config and command-line flags into `CrawlOptions`. Explicit CLI arguments override config values.

Error handling:
- config file missing → config error
- invalid TOML / configuration → config error
- keyboard interrupt → interrupted exit code
- unexpected error → generic error, with traceback when trace is enabled

---

### Raw HTTP Request Builder

`build_get_request()` constructs:

```text
GET /path?query HTTP/1.1

Host: example.com

User-Agent: ...

Accept: text/html, application/xhtml+xml;q=0.9, */*;q=0.1

Accept-Encoding: identity

Connection: close



```

Validation:
- origin-form target cannot contain CR, LF, NUL, or spaces
- header name must match token grammar
- header value cannot contain CR, LF, or NUL
- non-ASCII host labels are IDNA encoded
- IPv6 host headers regain brackets
- default ports are omitted from Host

---

### HTTP Response Parser

Parser responsibilities:
- parse status line
- parse headers
- combine repeated headers except Set-Cookie behavior
- validate Content-Length
- split response head and body start
- read body by response framing
- enforce header and body limits
- record time to first byte and body read timing

Framing rules:
1. `204`, `304`, and `1xx` responses have no body.
2. Any Transfer-Encoding response with Content-Length is rejected as ambiguous.
3. Transfer-Encoding must end in `chunked` to be supported.
4. Content-Length must be all digits and consistent when repeated.
5. Otherwise the body is read until close.

---

### RawSocketFetcher

Responsibilities:
- parse URL and scheme
- DNS lookup with wall-clock timeout
- optional private-address blocking
- TCP connect against resolved addresses
- TLS wrapping for HTTPS with minimum TLS 1.2
- build request bytes
- send request
- read/parse response
- decompress according to Content-Encoding
- follow redirects up to limit
- detect redirect loops
- reject unsupported redirect schemes
- strip sensitive headers on cross-origin redirects
- convert failures to stable `FetchResult.error_category`

Failure categories include:
- `dns_error`
- `blocked_address`
- `connection_error`
- `tls_error`
- `read_timeout`
- `total_timeout`
- `malformed_url`
- `malformed_response`
- `response_too_large`
- `redirect_loop`
- `too_many_redirects`
- `unsupported_redirect`

---

### LibraryFetcher

Uses standard-library `urllib` with the same result shape.

Design details:
- builds an opener with HTTP(S) handlers only
- disables default redirect following so project redirect policy remains shared
- blocks file/ftp fetch behavior
- returns `unsupported_option` if private-address blocking is requested
- maps `URLError` reasons into crawler failure categories
- applies max response byte checks

---

### CrawlEngine

Main loop:
1. Create or resume a crawl job.
2. Enqueue the seed URL.
3. Pull next due frontier item.
4. Skip max-depth items.
5. Enforce domain scope.
6. Check robots.txt when enabled.
7. Apply per-domain delay and Crawl-delay.
8. Mark item in progress.
9. Fetch URL.
10. Retry retryable failures/statuses.
11. Persist terminal failures.
12. Skip unsupported content types.
13. Parse HTML.
14. Save page.
15. Mark frontier item fetched.
16. Enqueue discovered links within scope.
17. Finish job as `finished`, `budget_reached`, `interrupted`, or `errored`.

---

### RetryPolicy

Retryable statuses:
- `408`
- `425`
- `429`
- `500`
- `502`
- `503`
- `504`

Retryable categories:
- DNS error
- connect timeout
- connection error
- read timeout
- total timeout
- server error
- rate limited

Backoff:
- respects `Retry-After` when present
- otherwise uses exponential delay with jitter
- pauses the whole domain for rate-limited/server-overload categories

---

### RobotsCache and RobotsRules

Supported robots behavior:
- User-agent groups
- wildcard group
- longest matching user-agent prefix wins
- Allow / Disallow
- most-specific path rule wins
- ties go to Allow
- `*` and trailing `$` pattern support
- Crawl-delay
- Sitemap collection
- cache TTL

Fetch policy:
- 2xx robots response: parse rules
- 4xx robots response: allow all
- 5xx or unreachable robots response: disallow all

---

### RateLimiter

Behavior:
- tracks next allowed request time per domain
- tracks pause-until time per domain
- reserves domain slot atomically
- sleeps outside lock
- prunes old entries after threshold to bound memory

---

### StdlibHTMLParser

Extracts:
- links from `<a>`, `<area>`, `<iframe>`, and `<frame>`
- first `<base href>`
- `<title>`
- meta description and og:description
- headings h1-h6

Link handling:
- strips fragments
- resolves relative URLs against base/final URL
- keeps only HTTP(S)
- deduplicates links while preserving discovery order

---

### SQLite Storage

Tables:
- `crawl_jobs`
- `frontier`
- `pages`
- `failures`

Important constraints:
- frontier status CHECK constraint
- `UNIQUE(job_id, normalized_url)` in frontier
- `UNIQUE(job_id, normalized_url)` in pages
- cascade deletes from job to related rows
- index for next frontier work
- index for failures by job

Storage responsibilities:
- create jobs
- enqueue URLs
- deduplicate frontier
- recover in-progress work on resume
- pick next due URL by depth then ID
- schedule retries
- save pages
- save failures
- report stats
- export JSON

---

## External Dependencies

### Runtime

None. The project uses only the Python standard library at runtime.

### Development

- pytest
- Ruff
- setuptools

---

## Concurrency Model

The crawler engine is synchronous. However:
- robots cache uses a lock to avoid duplicate fetches
- rate limiter uses a lock to reserve domain slots safely
- DNS timeout uses a daemon thread because `socket.getaddrinfo()` has no direct timeout parameter

No async event loop or worker pool is used in v1.

---

## Known Limits

- Synchronous single-process crawler.
- No JavaScript rendering.
- No authentication/session crawling.
- No CAPTCHA or bot-protection bypass.
- No distributed frontier.
- No proxy support.
- No sitemap seeding.
- No browser automation.
- Runtime stdlib HTML parser is not a full browser parser.
- Raw transport only performs GET.

---

## Verification Summary

The repository documents tests for:
- protocol parsing
- chunked decoding
- URL normalization
- robots parsing
- rate limiting
- HTML parsing
- raw socket integration against WSGI fixture
- end-to-end crawl

CI runs Ruff lint, Ruff format check, and pytest on Python 3.11, 3.12, and 3.13.

---

*Constitution reference: Article 4 (engineering quality), Article 6 (behavior verification), Article 7 (progressive complexity), and Article 8 (valid learner work).*

---


# Interface Design Specification
## App — Web Scraper v1
**Web Crawling Systems Group | Document 3 of 5**

---

## Public CLI Interface

### Program

```powershell
scrapehound <command> [options]
```

### Version

```powershell
scrapehound --version
```

---

## Commands

### `scrape`

Fetch one URL.

```powershell
scrapehound scrape URL [options]
```

Important options:
- `--config PATH`
- `--transport raw_socket|library`
- `--user-agent TEXT`
- `--connect-timeout SECONDS`
- `--read-timeout SECONDS`
- `--total-timeout SECONDS`
- `--max-bytes BYTES`
- `--redirect-limit N`
- `--block-private-addresses`
- `--trace`

Exit:
- success if fetch has no error category
- error if fetch returns an error category

---

### `crawl`

Run a bounded crawl from a seed URL.

```powershell
scrapehound crawl URL --db demo.sqlite --max-pages 10 --max-depth 2
```

Important options:
- `--config PATH`
- `--db PATH`
- `--transport raw_socket|library`
- `--max-pages N`
- `--max-depth N`
- `--max-bytes BYTES`
- `--connect-timeout SECONDS`
- `--read-timeout SECONDS`
- `--total-timeout SECONDS`
- `--redirect-limit N`
- `--retry-count N`
- `--delay SECONDS`
- `--allow-domain DOMAIN` repeatable
- `--ignore-robots`
- `--block-private-addresses`
- `--trace`

Behavior:
- creates a new crawl job
- enqueues seed URL
- prints summary when done
- warning is printed when `--ignore-robots` is explicit

---

### `resume`

Resume a persisted crawl job.

```powershell
scrapehound resume --db demo.sqlite
scrapehound resume --db demo.sqlite --job-id 3
```

Behavior:
- defaults to latest job when `--job-id` omitted
- recovers `in_progress` frontier rows back to pending
- resumes using persisted seed URL

---

### `stats`

Print crawl stats from SQLite.

```powershell
scrapehound stats --db demo.sqlite
scrapehound stats --db demo.sqlite --job-id 3
```

Output:
- JSON summary of frontier statuses, page count, and failure count

---

### `export`

Export pages and failures.

```powershell
scrapehound export --db demo.sqlite --format json
scrapehound export --db demo.sqlite --format json --output results.json
```

Output:
- JSON string to stdout or file

---

### `robots`

Check robots policy for one URL.

```powershell
scrapehound robots URL --transport raw_socket --user-agent scrapehound/0.1
```

Output:

```json
{"url":"...","allowed":true,"crawl_delay":0.1}
```

---

### `serve-fixture`

Run deterministic fixture server.

```powershell
scrapehound serve-fixture --host 127.0.0.1 --port 8000
```

Equivalent module form:

```powershell
python -m server.wsgi_fixture_app --port 8000
```

---

### `doctor`

Print runtime diagnostics.

```powershell
scrapehound doctor
```

Output includes:
- scrapehound version
- Python version
- SQLite version
- available transports

---

## Configuration Contract

Config files are TOML.

Sections:
- `[http]`
- `[crawl]`
- `[storage]`

Supported fields include:
- `http.transport`
- `http.user_agent`
- `http.connect_timeout`
- `http.read_timeout`
- `http.total_timeout`
- `crawl.max_pages`
- `crawl.max_depth`
- `crawl.max_response_bytes`
- `crawl.redirect_limit`
- `crawl.retry_count`
- `crawl.min_delay_seconds`
- `crawl.obey_robots`
- `crawl.stay_on_seed_domain`
- `crawl.block_private_addresses`
- `crawl.allowed_domains`
- `storage.db_path`

Precedence:
```text
CLI options > TOML config > CrawlOptions defaults
```

---

## Public Library Surface

### Models

```python
from scrapehound.models import (
    FetchRequest,
    FetchResult,
    ParsedPage,
    CrawlOptions,
    CrawlSummary,
)
```

### Crawl engine

```python
from scrapehound.crawl.engine import CrawlEngine
from scrapehound.models import CrawlOptions

options = CrawlOptions(db_path="demo.sqlite", max_pages=10, min_delay_seconds=0.5)
summary = CrawlEngine(options).crawl("http://localhost:8000/page")
```

### Fetchers

```python
from scrapehound.transport import make_fetcher
from scrapehound.models import FetchRequest

fetcher = make_fetcher("raw_socket")
result = fetcher.fetch(FetchRequest(url="http://localhost:8000/page", user_agent="scrapehound/0.1"))
```

Valid fetcher names:
- `raw_socket`
- `library`

---

## FetchResult Contract

Success:
- `status_code` is set
- `body` may contain bytes
- `headers` contains response headers
- `error_category` is `None`
- `ok` is true

Failure:
- `status_code` may be `None`
- `body` is empty for transport/protocol failures
- `error_category` contains a stable failure code
- `error_message` explains failure
- `ok` is false

---

## SQLite Output Contract

### `crawl_jobs`

Tracks:
- seed URL
- job status
- max pages/depth
- creation/start/finish timestamps

### `frontier`

Tracks:
- URL
- normalized URL
- depth
- status
- discovered-from URL
- retry count
- next fetch timestamp

Statuses:
- `pending`
- `in_progress`
- `fetched`
- `skipped`
- `failed`
- `retry_scheduled`

### `pages`

Tracks:
- original URL
- final URL
- normalized URL
- status code
- content type
- title
- description
- headings JSON
- links JSON
- body hash
- body text
- encoding
- timings JSON
- transport
- depth

### `failures`

Tracks:
- URL
- normalized URL when possible
- category
- message
- status code
- retry count

---

## Exit Code Contract

Named constants are used by the CLI:
- `OK`
- `ERROR`
- `CONFIG_ERROR`
- `INTERRUPTED`

Observed command behavior:
- normal command success returns OK
- failed fetch returns ERROR
- missing/invalid config returns CONFIG_ERROR
- keyboard interrupt returns INTERRUPTED

---

## Ethical Use Contract

The tool should not be used to:
- bypass logins
- solve CAPTCHAs
- scrape private data
- evade blocking
- crawl sites that prohibit automated access

Safe defaults:
- obey robots.txt
- seed-domain-only crawl
- max pages
- max depth
- max response bytes
- timeouts
- redirect limit
- retry budget
- descriptive User-Agent
- recorded skip/failure categories

---

*Constitution reference: Article 4 (input/output boundaries), Article 6 (verification), and Article 8 (understandable and verifiable work).*

---


# Runbook
## App — Web Scraper v1
**Web Crawling Systems Group | Document 4 of 5**

---

## Requirements

### Runtime

- Python 3.11 or newer
- SQLite from Python standard library
- No third-party runtime dependencies

### Development

- pytest
- Ruff

---

## Installation

```powershell
python -m pip install -e .
```

Development install:

```powershell
python -m pip install -e ".[dev]"
```

---

## Start Fixture Server

```powershell
python -m server.wsgi_fixture_app --port 8000
```

Expected startup output:

```text
serving scrapehound fixture on http://127.0.0.1:8000/page
```

---

## Smoke Tests

### Fetch one page with raw socket transport

```powershell
scrapehound scrape http://localhost:8000/page --transport raw_socket --trace
```

Expected:
- status code 200
- final URL shown
- response headers/body summary shown
- trace details when enabled

---

### Fetch with library transport

```powershell
scrapehound scrape http://localhost:8000/page --transport library
```

Expected:
- same high-level fetch result shape
- transport field indicates library backend

---

### Run a bounded crawl

```powershell
scrapehound crawl http://localhost:8000/page --db demo.sqlite --max-pages 10 --delay 0 --trace
```

Expected:
- seed page fetched
- discovered in-scope links enqueued
- robots-disallowed `/blocked` skipped when robots applies
- crawl summary printed

---

### Inspect stats

```powershell
scrapehound stats --db demo.sqlite
```

Expected:
- JSON with frontier counts, pages, and failures

---

### Export data

```powershell
scrapehound export --db demo.sqlite --format json --output results.json
```

Expected:
- `results.json` contains pages, failures, and stats

---

### Check robots policy

```powershell
scrapehound robots http://localhost:8000/blocked
```

Expected:
- JSON states whether URL is allowed and includes crawl delay if present

---

## Standard Operating Procedures

### Crawl a local site politely

```powershell
scrapehound crawl http://localhost:8000/page `
  --db demo.sqlite `
  --max-pages 25 `
  --max-depth 2 `
  --delay 1.0
```

---

### Resume interrupted crawl

```powershell
scrapehound resume --db demo.sqlite
```

Specific job:

```powershell
scrapehound resume --db demo.sqlite --job-id 2
```

---

### Allow an additional domain

```powershell
scrapehound crawl http://example.test/ --allow-domain cdn.example.test
```

---

### Explicitly disable robots checks

```powershell
scrapehound crawl http://localhost:8000/page --ignore-robots
```

Expected:
- warning printed to stderr

---

### Enable private-address blocking

```powershell
scrapehound scrape https://example.com --transport raw_socket --block-private-addresses
```

Use only with `raw_socket`; library transport cannot provide this guarantee.

---

## Running Tests

```powershell
python -m pytest
```

Run lint:

```powershell
ruff check .
ruff format --check .
```

---

## CI Parity

The GitHub Actions workflow runs:
- Ruff lint
- Ruff format check
- pytest
- Python 3.11, 3.12, and 3.13 test matrix

---

## Health Checks

### CLI import/version

```powershell
scrapehound --version
scrapehound doctor
```

Expected:
- package version
- Python version
- SQLite version
- transports list

---

### Database initialization

```powershell
scrapehound crawl http://localhost:8000/page --db demo.sqlite --max-pages 1 --delay 0
```

Expected:
- SQLite database created
- crawl_jobs/frontier/pages/failures tables initialized

---

### Robots check

```powershell
scrapehound robots http://localhost:8000/page
```

Expected:
- allowed true
- crawl delay from fixture robots.txt

---

## Known Failure Modes

### DNS failure

Category:
```text
dns_error
```

Resolution:
- verify host spelling
- verify network
- use fixture server for deterministic tests

---

### Connection failure

Category:
```text
connection_error
```

Resolution:
- verify server is running
- verify host and port
- compare `raw_socket` and `library` transports

---

### TLS failure

Category:
```text
tls_error
```

Resolution:
- verify URL scheme
- verify certificate configuration
- use HTTP fixture for local protocol tests

---

### Read or total timeout

Categories:
```text
read_timeout
total_timeout
```

Resolution:
- increase timeout values
- inspect slow endpoints
- reduce concurrency assumptions; engine is synchronous

---

### Malformed response

Category:
```text
malformed_response
```

Triggers:
- bad status line
- invalid header
- bad Content-Length
- unsupported Transfer-Encoding
- ambiguous framing
- bad chunked body

Resolution:
- reproduce with parser tests
- inspect trace or fixture behavior

---

### Response too large

Category:
```text
response_too_large
```

Resolution:
- raise `--max-bytes` only when appropriate
- keep max response size bounded for crawls

---

### Robots disallowed

Category:
```text
robots_disallowed
```

Resolution:
- do not crawl disallowed paths
- only use `--ignore-robots` for controlled local tests or with permission

---

### Off-domain URL

Category:
```text
off_domain
```

Resolution:
- add `--allow-domain` if the external domain is intentionally in scope

---

### Unsupported content type

Category:
```text
unsupported_content_type
```

Resolution:
- crawler currently saves/parses HTML/XHTML only
- extend allowed content types only with a parser strategy

---

## Troubleshooting Decision Tree

```text
Crawl produced fewer pages than expected
  ├── Did max-pages stop the crawl?
  │     └── increase --max-pages
  ├── Did max-depth stop link expansion?
  │     └── increase --max-depth
  ├── Were links off-domain?
  │     └── add --allow-domain intentionally
  ├── Did robots block URLs?
  │     └── inspect scrapehound robots URL
  ├── Were responses not HTML?
  │     └── inspect failures/stats/export
  ├── Were retries exhausted?
  │     └── inspect failures category and retry_count
  └── Did timeout/byte budgets fire?
        └── adjust timeout/max-bytes cautiously
```

---

## Maintenance Notes

- Keep the raw socket fetcher readable and protocol-focused.
- Do not add third-party runtime HTTP clients without a new ADR.
- Preserve safe crawler defaults.
- Add tests before changing robots behavior.
- Add tests before changing URL normalization.
- Add tests before changing response framing rules.
- Keep skip/failure categories stable.
- Keep SQLite schema migration implications documented before changing tables.
- Keep fixture server deterministic.
- Avoid claims of production-scale crawling unless architecture changes support it.

---

*Constitution reference: Article 6 (behavior verification), Article 5 (constraints and trade-offs), and Article 8 (verifiable learner work).*

---


# Lessons Learned
## App — Web Scraper v1
**Web Crawling Systems Group | Document 5 of 5**

---

## Why This Design Was Chosen

This design was chosen because a web scraper is a strong capstone for networking and protocol mastery. It touches URLs, DNS, sockets, TLS, HTTP/1.1 request bytes, response framing, redirects, HTML parsing, robots.txt, rate limiting, retry behavior, and durable state. Each of those topics is visible in this implementation.

The fetcher interface is the main architectural seam. It lets the raw socket backend remain the learning artifact while the library backend proves the crawler is not tightly coupled to one HTTP implementation. The crawl engine only needs a `fetch()` method that returns a `FetchResult`.

SQLite was chosen because crawling is stateful. A real crawler needs to know what is pending, in progress, fetched, skipped, failed, and retry scheduled. Persisting that state makes resume behavior possible and keeps the project honest about failure.

---

## What Was Intentionally Omitted

**Public-internet-scale crawling:** Deferred because the project is synchronous and local/capstone scoped.

**JavaScript rendering:** Deferred because browser automation would move the focus away from HTTP fundamentals.

**Authentication/session crawling:** Deferred to avoid private-data and access-control complexity.

**CAPTCHA or blocking bypass:** Explicitly out of scope.

**Distributed queues:** SQLite is enough for the project scale.

**Proxy rotation:** Out of scope and often associated with abusive scraping workflows.

**Sitemap seeding:** Deferred because the frontier already demonstrates URL discovery and persistence.

**Full robots policy engine:** A documented subset is easier to test and explain.

---

## Biggest Weakness

The biggest weakness is scale. The crawler is synchronous and single-process. It is appropriate for local fixture testing and small demonstrations, but it is not designed for large multi-domain crawls.

The second weakness is parsing fidelity. Python's stdlib `HTMLParser` is useful for basic pages, but it is not a browser. It does not execute JavaScript, recover from every malformed HTML case like modern browsers, or expose rendered DOM state.

The third weakness is crawler policy depth. The robots implementation covers a meaningful subset, but large crawlers require deeper compliance behavior, sitemap integration, crawl budgets, per-host concurrency controls, and operational monitoring.

---

## Scaling Considerations

**If crawler size grows:**
- introduce worker concurrency with clear per-domain scheduling
- move frontier to a server database or queue
- add dedupe across jobs if desired
- add crawl budget controls per domain
- add structured logs/metrics

**If extraction requirements grow:**
- add parser interface implementations
- support metadata extraction rules
- consider BeautifulSoup/lxml only after documenting dependency trade-offs
- add document-type-specific parsers

**If politeness requirements grow:**
- expand robots parser coverage
- cache robots with stronger expiry rules
- add sitemap discovery
- track per-domain crawl budgets
- add retry-after and backoff observability

**If safety requirements grow:**
- default private-address blocking for non-local crawls
- add explicit allowlist mode
- add denylist patterns
- add output redaction policies

---

## What the Next Refactor Would Be

1. **Parser interface formalization** — define an explicit protocol for page parsers so alternative parsers can be plugged in.

2. **Structured trace events** — replace plain trace prints with event objects that can be logged or exported.

3. **Crawler configuration validation** — validate TOML values more strictly instead of relying mostly on type casts.

4. **Schema versioning** — prepare SQLite schema migrations before adding tables or columns.

5. **Optional concurrent workers** — add carefully bounded concurrency while preserving per-domain rate limits.

---

## What This Project Taught

- **A scraper is not just HTML parsing.** The hard parts are HTTP behavior, limits, redirects, retries, robots, rate limiting, frontier state, and failure recording.

- **Protocol framing matters.** Ambiguous or malformed HTTP responses should not be guessed at silently.

- **Politeness is architecture.** Robots checks and per-domain delay need first-class placement in the crawl loop.

- **Persistence changes crawler quality.** SQLite makes resume, dedupe, stats, and export possible.

- **Interfaces keep learning code clean.** The engine can use raw sockets or `urllib` without rewriting crawl logic.

- **Safe defaults matter.** Max pages, max depth, timeouts, byte limits, domain scope, robots, and retry budgets prevent uncontrolled behavior.

- **Deterministic fixtures are powerful.** A local WSGI site lets the project test redirects, robots, retry statuses, gzip, large bodies, and crawl flows without the public internet.

---

*Constitution v2.0 checklist: This document satisfies Article 5 (trade-off documentation), Article 6 (verification), and Article 7 (progressive complexity) for Web Scraper v1.*
