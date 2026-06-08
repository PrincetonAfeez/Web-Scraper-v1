# ADR 0001: Raw Socket Transport

## Status

Accepted

## Context

The capstone goal is to demonstrate end-to-end HTTP over TCP/IP: DNS resolution, socket connect, optional TLS, hand-built request bytes, response framing, redirects, and timeouts. A crawler also needs a mature HTTP path to show that transport choice is an implementation detail, not a crawl-engine concern.

## Decision

Keep two fetcher backends behind the same `Fetcher` interface:

- `raw_socket` — manual protocol implementation for learning and demonstration
- `library` — stdlib `urllib` client for comparison and pragmatic defaults

The crawl engine, parser, and SQLite storage depend only on the interface.

## Rationale

The raw socket backend proves protocol understanding: URL parsing, DNS, TCP, TLS, request serialization, status-line and header parsing, `Content-Length` and chunked bodies, and redirect handling.

The library backend proves interface substitution: the same crawler can swap transports without rewriting crawl logic. That mirrors how production systems delegate HTTP edge cases to mature libraries while keeping domain logic stable.

## Consequences

- More code to maintain (two transports, shared redirect and timeout policy)
- Better educational value and a clearer rubric story
- Tests can compare behavior across backends where semantics align
- Raw socket remains the default demo path in docs and fixture workflows

## Accepted Limits

This is an HTTP/1.1 learning implementation, not a browser-grade client. It does not aim for HTTP/2, connection pooling at scale, full cookie jars, or every edge case handled by production HTTP stacks.
