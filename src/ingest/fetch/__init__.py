from __future__ import annotations

import ipaddress
import socket
import time
import urllib.robotparser
from dataclasses import dataclass
from urllib.parse import urlsplit
from urllib.request import Request, build_opener


@dataclass(slots=True)
class FetchResult:
    url: str
    status_code: int
    content_type: str
    body: bytes = b""
    error: str | None = None


class UnsafeURLError(ValueError):
    """URL could reach a non-public or out-of-scope destination."""


class RateLimiter:
    """Shared polite delay between requests (thin OOP: stateful by design)."""

    def __init__(self, delay: float = 1.0):
        self.delay = delay
        self._last = 0.0

    def wait(self) -> None:
        wait_for = self.delay - (time.monotonic() - self._last)
        if wait_for > 0:
            time.sleep(wait_for)
        self._last = time.monotonic()


def validate_public_url(url: str, origin_host: str = "") -> str:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme not in {"http", "https"} or not host:
        raise UnsafeURLError("Only absolute HTTP(S) URLs are accepted")
    if origin_host and host != origin_host.lower():
        raise UnsafeURLError("Cross-origin URL is outside the crawl scope")
    try:
        ips = [ipaddress.ip_address(r[4][0]) for r in socket.getaddrinfo(host, 443)]
    except (OSError, ValueError) as exc:
        raise UnsafeURLError(f"Could not resolve host: {host}") from exc
    if not ips or any(not ip.is_global for ip in ips):
        raise UnsafeURLError("Local, private, reserved, and non-public IPs are blocked")
    path = parts.path or "/"
    return parts._replace(path=path, fragment="").geturl()


class SafeFetcher:
    """Bounded static fetcher; errors become FetchResult, never exceptions."""

    def __init__(self, timeout: float = 20.0, max_bytes: int = 2_000_000,
                 user_agent: str = "MLAITourSourceAuditor/0.1",
                 limiter: RateLimiter | None = None):
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.user_agent = user_agent
        self.limiter = limiter or RateLimiter()
        self.requests_made = 0

    def fetch(self, url: str, origin_host: str = "") -> FetchResult:
        try:
            safe = validate_public_url(url, origin_host)
        except UnsafeURLError as exc:
            return FetchResult(url, 0, "", b"", str(exc))
        self.limiter.wait()
        self.requests_made += 1
        try:
            with build_opener().open(
                Request(safe, headers={"User-Agent": self.user_agent}), timeout=self.timeout
            ) as resp:
                body = resp.read(self.max_bytes + 1)
        except Exception as exc:
            return FetchResult(safe, 0, "", b"", f"{type(exc).__name__}: {exc}"[:200])
        if resp.status != 200:
            return FetchResult(safe, resp.status, "", b"", f"HTTP {resp.status}")
        if len(body) > self.max_bytes:
            return FetchResult(safe, resp.status, "", b"", "Response exceeds byte limit")
        return FetchResult(safe, resp.status, resp.headers.get("Content-Type", ""), body)


def fetch_robots(fetcher: SafeFetcher, site_base: str, origin_host: str):
    """Robots parser or None when unavailable (fail closed upstream)."""
    result = fetcher.fetch(f"{site_base}/robots.txt", origin_host)
    if result.status_code != 200 or result.error:
        return None
    parser = urllib.robotparser.RobotFileParser(f"{site_base}/robots.txt")
    parser.parse(result.body.decode("utf-8", errors="replace").splitlines())
    return parser
