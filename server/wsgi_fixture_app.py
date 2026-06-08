"""Deterministic WSGI fixture site for protocol and crawler tests."""

from __future__ import annotations

import argparse
import gzip
import time
from wsgiref.simple_server import make_server


def application(environ, start_response):  # type: ignore[no-untyped-def]
    path = environ.get("PATH_INFO", "/")
    if path == "/robots.txt":
        return _response(
            start_response,
            "200 OK",
            b"User-agent: *\nDisallow: /blocked\nCrawl-delay: 0.1\n",
            "text/plain; charset=utf-8",
        )
    if path in {"/", "/page"}:
        return _html(
            start_response,
            """
            <html>
              <head>
                <title>Fixture Page</title>
                <meta name="description" content="A deterministic fixture page">
              </head>
              <body>
                <h1>Fixture Page</h1>
                <a href="/page2">Page two</a>
                <a href="/blocked">Blocked page</a>
                <a href="/redirect">Redirect page</a>
              </body>
            </html>
            """,
        )
    if path == "/page2":
        return _html(
            start_response,
            """
            <html>
              <head><title>Fixture Page Two</title></head>
              <body>
                <h1>Fixture Page Two</h1>
                <h2>Nested Links</h2>
                <a href="/deep/page3?b=2&a=1#fragment">Deep page</a>
                <a href="/page">Duplicate page</a>
              </body>
            </html>
            """,
        )
    if path == "/deep/page3":
        return _html(
            start_response,
            "<html><head><title>Deep</title></head><body><h1>Deep Page</h1></body></html>",
        )
    if path == "/blocked":
        return _html(start_response, "<html><body><h1>Blocked</h1></body></html>")
    if path == "/redirect":
        body = b"redirecting"
        start_response("302 Found", [("Location", "/page2"), ("Content-Length", str(len(body)))])
        return [body]
    if path == "/redirect-loop":
        body = b"loop"
        start_response(
            "302 Found",
            [("Location", "/redirect-loop"), ("Content-Length", str(len(body)))],
        )
        return [body]
    if path == "/retry-after":
        body = b"too many requests"
        start_response(
            "429 Too Many Requests",
            [("Retry-After", "1"), ("Content-Length", str(len(body)))],
        )
        return [body]
    if path == "/unavailable":
        body = b"temporarily unavailable"
        start_response(
            "503 Service Unavailable",
            [("Retry-After", "1"), ("Content-Length", str(len(body)))],
        )
        return [body]
    if path == "/slow":
        time.sleep(2.0)
        return _html(start_response, "<html><body><h1>Slow Page</h1></body></html>")
    if path == "/large":
        body = b"x" * (3 * 1024 * 1024)
        return _response(start_response, "200 OK", body, "text/html; charset=utf-8")
    if path == "/gzip":
        raw = b"<html><body><h1>Gzip Page</h1></body></html>"
        body = gzip.compress(raw)
        start_response(
            "200 OK",
            [
                ("Content-Type", "text/html; charset=utf-8"),
                ("Content-Encoding", "gzip"),
                ("Content-Length", str(len(body))),
            ],
        )
        return [body]
    return _response(start_response, "404 Not Found", b"not found", "text/plain; charset=utf-8")


def _html(start_response, html: str):  # type: ignore[no-untyped-def]
    return _response(start_response, "200 OK", html.encode("utf-8"), "text/html; charset=utf-8")


def _response(start_response, status: str, body: bytes, content_type: str):  # type: ignore[no-untyped-def]
    start_response(status, [("Content-Type", content_type), ("Content-Length", str(len(body)))])
    return [body]


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    with make_server(host, port, application) as httpd:
        print(f"serving scrapehound fixture on http://{host}:{port}/page")
        httpd.serve_forever()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    serve(args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
