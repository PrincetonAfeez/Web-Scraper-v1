"""Minimal WSGI results viewer for a scrapehound SQLite database."""

from __future__ import annotations

import html
import os
from wsgiref.simple_server import make_server

from scrapehound.storage.repositories import Storage


def application(environ, start_response):  # type: ignore[no-untyped-def]
    db_path = environ.get("SCRAPEHOUND_DB") or os.environ.get("SCRAPEHOUND_DB", "scrapehound.sqlite")
    with Storage(db_path) as storage:
        data = storage.export_json()
    rows = "\n".join(
        f"<li><a href='{html.escape(page['final_url'])}'>{html.escape(page.get('title') or page['final_url'])}</a></li>"
        for page in data["pages"]
    )
    body = f"<html><body><h1>scrapehound results</h1><ul>{rows}</ul></body></html>".encode()
    start_response(
        "200 OK",
        [
            ("Content-Type", "text/html; charset=utf-8"),
            ("Content-Length", str(len(body))),
        ],
    )
    return [body]


def serve(host: str = "127.0.0.1", port: int = 8010) -> None:
    with make_server(host, port, application) as httpd:
        print(f"serving results viewer on http://{host}:{port}/")
        httpd.serve_forever()
