# ADR 0001: Raw Sockets Vs Library HTTP Client

Both transports exist behind the same fetcher interface.

The raw socket backend proves protocol mastery: URL parsing, DNS, TCP, TLS, manual request bytes, response framing, timeouts, and redirects.

The library backend demonstrates the production lesson: real systems usually delegate HTTP edge cases to mature libraries. Keeping both behind `Fetcher` lets the crawl engine stay independent from transport details.
