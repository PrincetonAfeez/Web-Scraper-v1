"""Configuration for integration tests."""

from __future__ import annotations

import threading
from wsgiref.simple_server import make_server

import pytest

from server.wsgi_fixture_app import application


@pytest.fixture()
def fixture_server():
    server = make_server("127.0.0.1", 0, application)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
