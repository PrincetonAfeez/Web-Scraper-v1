"""Integration test for chunked response decoding."""

from __future__ import annotations

import socketserver
import threading

from scrapehound.models import FetchRequest
from scrapehound.transport.socket_fetcher import RawSocketFetcher
from server.chunked_test_server import ChunkedHandler


def test_raw_socket_fetcher_decodes_chunked_response():
    server = socketserver.TCPServer(("127.0.0.1", 0), ChunkedHandler)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = RawSocketFetcher().fetch(FetchRequest(url=f"http://{host}:{port}/", user_agent="scrapehound-test"))
    finally:
        server.shutdown()
        thread.join(timeout=5)

    assert result.error_category is None
    assert result.status_code == 200
    assert result.body == b"<html><body>Hi</body></html>"
