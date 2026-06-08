# ADR 0004: Per-Domain Rate Limiter

The crawler spaces requests per host using a per-domain "next allowed time"
tracked on a monotonic clock, plus a minimum-delay guard. Each request reserves
its slot atomically under a lock and then sleeps outside the lock, so workers on
different domains do not serialize on each other.

`Crawl-delay` from robots.txt can raise a host's delay. A `Retry-After` header
(or a 429/503 response) pauses the whole domain until a later monotonic deadline.

An earlier token-bucket sketch was dropped in favor of this simpler timestamp
scheme, which is sufficient for single-process, bounded crawls.
