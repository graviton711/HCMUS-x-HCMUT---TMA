"""Loopback-only tests for the pooled fetcher transport. No external network.

Covers gzip decoding, redirect following, retry on transient 503, and
connection reuse. Localhost is used; the SSRF guard is bypassed by stubbing
URL validation since 127.0.0.1 is non-public by design.
"""

from __future__ import annotations

import gzip
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from ingest.fetch import RateLimiter, SafeFetcher

BODY = "<html><head><title>Loopback Tour</title></head><body>hello</body></html>"


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    hits: dict[str, int] = {}

    def log_message(self, *args):
        pass

    def _send(self, status: int, body: bytes, extra: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self) -> None:
        type(self).hits[self.path] = type(self).hits.get(self.path, 0) + 1
        if self.path == "/tour":
            self._send(200, gzip.compress(BODY.encode()),
                       {"Content-Type": "text/html",
                        "Content-Encoding": "gzip"})
        elif self.path == "/redir":
            self._send(302, b"", {"Location": "/tour"})
        elif self.path == "/uredir":
            self._send(302, b"", {"Location": "/t%C3%B4ur"})
        elif self.path == "/t%C3%B4ur":
            self._send(200, BODY.encode(), {"Content-Type": "text/html"})
        elif self.path == "/flaky":
            if type(self).hits[self.path] < 2:
                self._send(503, b"try again")
            else:
                self._send(200, BODY.encode(), {"Content-Type": "text/html"})
        else:
            self._send(404, b"nope")


@pytest.fixture()
def loopback(monkeypatch):
    monkeypatch.setattr("ingest.fetch.validate_public_url",
                        lambda url, origin_host="", dns_ttl=None: url)
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    accepts: list = []
    orig = server.get_request

    def counting():
        conn, addr = orig()
        accepts.append(addr)
        return conn, addr

    server.get_request = counting  # type: ignore[method-assign]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", accepts
    finally:
        server.shutdown()
        thread.join(timeout=10)
        server.server_close()


def _fetcher(**overrides):
    args = {"timeout": 10.0, "limiter": RateLimiter(delay=0),
            "retries": 2, "retry_backoff_s": 0.01}
    args.update(overrides)
    return SafeFetcher(**args)


def test_gzip_body_is_decoded(loopback):
    base, _ = loopback
    result = _fetcher().fetch(f"{base}/tour")
    assert result.status_code == 200 and result.error is None
    assert result.body.decode() == BODY
    assert result.content_type == "text/html"


def test_redirect_is_followed(loopback):
    base, _ = loopback
    result = _fetcher().fetch(f"{base}/redir")
    assert result.status_code == 200 and result.error is None
    assert result.body.decode() == BODY


def test_unicode_redirect_target_is_quoted(loopback):
    base, _ = loopback
    result = _fetcher().fetch(f"{base}/uredir")
    assert result.status_code == 200 and result.error is None
    assert result.body.decode() == BODY


def test_retry_turns_flaky_503_into_200(loopback):
    base, _ = loopback
    _Handler.hits.clear()
    result = _fetcher(retries=2).fetch(f"{base}/flaky")
    assert result.status_code == 200 and result.body.decode() == BODY
    _Handler.hits.clear()
    result = _fetcher(retries=1).fetch(f"{base}/flaky")
    assert result.status_code == 503 and result.error == "HTTP 503"


def test_connection_is_reused(loopback):
    base, _ = loopback
    fetcher = _fetcher()
    for _ in range(3):
        result = fetcher.fetch(f"{base}/tour")
        assert result.status_code == 200
    _, accepts = loopback
    assert len(accepts) == 1
