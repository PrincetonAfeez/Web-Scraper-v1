# ADR 0003: Sync Vs Async Fetching

Synchronous crawling is built first because it makes the protocol path easiest to inspect and test.

The async extension point can wrap blocking fetchers in `asyncio.to_thread` or use asyncio streams, while preserving the same politeness rules through shared schedulers and per-domain limits.
