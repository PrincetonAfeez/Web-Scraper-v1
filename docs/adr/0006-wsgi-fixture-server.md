# ADR 0006: WSGI Fixture Server

The fixture server is a deterministic local target that exercises HTTP behavior without crawling real sites.

It demonstrates the WSGI contract: the app receives `environ`, calls `start_response`, and returns an iterable of bytes. Chunked transfer encoding is tested with a separate raw socket test server because WSGI apps should not manually emit chunked framing.
