"""A tiny raw socket server that emits Transfer-Encoding: chunked responses."""

from __future__ import annotations

import argparse
import socketserver


class ChunkedHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        self.request.recv(4096)
        response = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: text/html; charset=utf-8\r\n"
            b"Transfer-Encoding: chunked\r\n"
            b"Connection: close\r\n"
            b"\r\n"
            b"6\r\n<html>\r\n"
            b"8\r\n<body>Hi\r\n"
            b"7\r\n</body>\r\n"
            b"7\r\n</html>\r\n"
            b"0\r\n\r\n"
        )
        self.request.sendall(response)


def serve(host: str = "127.0.0.1", port: int = 0):  # type: ignore[no-untyped-def]
    server = socketserver.TCPServer((host, port), ChunkedHandler)
    print(f"serving chunked test server on http://{host}:{server.server_address[1]}/")
    server.serve_forever()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args(argv)
    serve(args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
