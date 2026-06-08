# ADR 0005: Robots And Ethical Crawling

Robots.txt is honored by default. The parser covers `User-agent`, `Allow`,
`Disallow`, `Crawl-delay`, and `Sitemap`, with `*` wildcards, `$` end-anchors,
and longest-match precedence (Allow wins ties).

Unreachable-status handling follows RFC 9309: a 2xx robots.txt is parsed, a 4xx
(such as a missing file) imposes no restrictions (fail open), and a 5xx or a
network failure is treated as "disallow all" (fail closed) so a flaky server
cannot silently widen the crawl. `--ignore-robots` is explicit and prints a
warning.
