# Production Reflection

This educational scraper proves protocol and crawler architecture understanding. The raw socket backend is intentionally readable and explicit: it shows what an HTTP client library normally hides.

For production crawling, I would usually rely on mature HTTP libraries, battle-tested robots.txt parsing, stronger observability, crawl budget controls, legal review, and operational guardrails. I would also consider PostgreSQL or a queue-backed frontier when multiple workers or machines need to coordinate.
