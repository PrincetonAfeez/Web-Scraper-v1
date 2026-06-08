# Scrapehound Database Schema

This document describes the SQLite persistence schema used by `scrapehound`.

## Tables

### `crawl_jobs`

Represents one crawl run from a seed URL.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | INTEGER | Primary key. |
| `seed_url` | TEXT | Original crawl seed. |
| `status` | TEXT | Defaults to `running`; finished jobs are updated by the storage layer. |
| `max_pages` | INTEGER | Page budget for this job. |
| `max_depth` | INTEGER | Crawl depth budget for this job. |
| `created_at` | TEXT | SQLite UTC datetime string. |
| `started_at` | TEXT | SQLite UTC datetime string. |
| `finished_at` | TEXT | Nullable completion timestamp. |

### `frontier`

Stores discovered URLs and crawl scheduling state.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | INTEGER | Primary key. |
| `job_id` | INTEGER | Foreign key to `crawl_jobs(id)` with cascade delete. |
| `url` | TEXT | URL as discovered or submitted. |
| `normalized_url` | TEXT | Deduplication key. |
| `depth` | INTEGER | Crawl depth from seed. |
| `status` | TEXT | One of `pending`, `in_progress`, `fetched`, `skipped`, `failed`, `retry_scheduled`. |
| `discovered_from` | TEXT | Nullable source URL. |
| `retry_count` | INTEGER | Number of retries already attempted. |
| `next_fetch_at` | REAL | Epoch timestamp used for polite scheduling and retries. |
| `created_at` | TEXT | SQLite UTC datetime string. |
| `updated_at` | TEXT | SQLite UTC datetime string. |

Deduplication rule: `UNIQUE(job_id, normalized_url)`.

Scheduling index: `idx_frontier_job_status_next(job_id, status, next_fetch_at, depth, id)`.

### `pages`

Stores successful page fetches and parsed HTML metadata.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | INTEGER | Primary key. |
| `job_id` | INTEGER | Foreign key to `crawl_jobs(id)` with cascade delete. |
| `url` | TEXT | Original frontier URL. |
| `final_url` | TEXT | Final URL after redirects. |
| `normalized_url` | TEXT | Unique page key per job. |
| `status_code` | INTEGER | HTTP status code. |
| `content_type` | TEXT | Nullable response content type. |
| `title` | TEXT | Nullable parsed page title. |
| `description` | TEXT | Nullable parsed meta description. |
| `headings_json` | TEXT | JSON array of headings. |
| `links_json` | TEXT | JSON array of extracted links. |
| `body_sha256` | TEXT | SHA-256 hash of response body bytes. |
| `body_text` | TEXT | Nullable decoded body text. |
| `text_encoding` | TEXT | Nullable detected/used text encoding. |
| `timing_json` | TEXT | JSON object matching `timing-breakdown.schema.json`. |
| `transport` | TEXT | Transport backend name, usually `raw_socket` or `library`. |
| `depth` | INTEGER | Crawl depth for the page. |
| `fetched_at` | TEXT | SQLite UTC datetime string. |

Deduplication/upsert rule: `UNIQUE(job_id, normalized_url)`.

### `failures`

Stores failed fetches, parse problems, robots blocks, and retry-exhausted URLs.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | INTEGER | Primary key. |
| `job_id` | INTEGER | Foreign key to `crawl_jobs(id)` with cascade delete. |
| `url` | TEXT | URL that failed. |
| `normalized_url` | TEXT | Nullable normalized URL. |
| `category` | TEXT | Stable failure category. |
| `message` | TEXT | Nullable human-readable message. |
| `status_code` | INTEGER | Nullable HTTP status code. |
| `retry_count` | INTEGER | Retries attempted when failure was recorded. |
| `created_at` | TEXT | SQLite UTC datetime string. |

Failure lookup index: `idx_failures_job(job_id)`.

## Entity Relationship Summary

```text
crawl_jobs 1 ──── * frontier
crawl_jobs 1 ──── * pages
crawl_jobs 1 ──── * failures
```

Deleting a crawl job cascades to frontier items, pages, and failures.
