# ADR 0002: SQLite Frontier And Resume

## Status

Accepted

## Context

The capstone needs durable crawl state: a URL frontier, fetched pages, failure records, and the ability to resume after interruption. The crawler is local, bounded, and single-process by default.

## Decision

Persist crawl state in a single local SQLite database file with:

- explicit frontier statuses (`pending`, `in_progress`, `fetched`, `skipped`, `failed`, `retry_scheduled`)
- WAL mode, foreign keys, and a busy timeout for production-minded defaults
- schema versioning via `PRAGMA user_version` and startup migrations
- recovery of interrupted `in_progress` rows back to `pending` on resume

## Rationale

SQLite keeps the persistence layer simple and inspectable for a capstone: one file per crawl, no external services, and SQL queries for stats and export. Frontier states make resume and failure analysis testable without a distributed queue.

A single-writer model matches the intended use case: one crawler process per database file on one machine.

## Consequences

- Resume works after Ctrl-C or crash by re-queuing in-flight URLs
- Stats, export, and verify can read the same database without extra tooling
- Parallel crawlers must use separate database files; sharing one file is not supported
- PostgreSQL or a queue-backed design would be appropriate for distributed crawling at scale

## Accepted Limits

This is not a multi-writer, horizontally scaled persistence layer. Concurrent crawler processes against the same database file are out of scope.
