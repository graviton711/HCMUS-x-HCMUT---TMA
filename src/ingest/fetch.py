"""Transport layer: polite static fetch, render helper, browser capture.

Everything that touches the network lives here and nowhere else:
bounded static GETs with robots + rate limit + SSRF guard, single-page
rendering for agents, and real-visitor browser sessions for dynamic flows.
No parsing, no HTML inspection beyond content-type checks.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import socket
import time
import urllib.robotparser
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlsplit
from urllib.request import Request, build_opener

from shared import get_logger

if TYPE_CHECKING:
    from playwright.sync_api import Page  # pyright: ignore[reportMissingImports]

log = get_logger("fetch")

MAX_BODY_BYTES = 2_000_000


@dataclass(slots=True)
class FetchResult:
    url: str
    status_code: int
    content_type: str
    body: bytes = b""
    error: str | None = None
    headers: dict = field(default_factory=dict)


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

    def __init__(self, timeout: float = 20.0, max_bytes: int = MAX_BODY_BYTES,
                 user_agent: str = "MLAITourSourceAuditor/0.1",
                 limiter: RateLimiter | None = None):
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.user_agent = user_agent
        self.limiter = limiter or RateLimiter()
        self.requests_made = 0

    def fetch(self, url: str, origin_host: str = "",
              extra_headers: dict | None = None) -> FetchResult:
        try:
            safe = validate_public_url(url, origin_host)
        except UnsafeURLError as exc:
            return FetchResult(url, 0, "", b"", str(exc))
        self.limiter.wait()
        self.requests_made += 1
        headers = {"User-Agent": self.user_agent}
        headers.update(extra_headers or {})
        try:
            with build_opener().open(
                Request(safe, headers=headers), timeout=self.timeout
            ) as resp:
                if resp.status == 304:
                    return FetchResult(safe, 304, "", b"", None, self._validators(resp))
                body = resp.read(self.max_bytes + 1)
        except Exception as exc:
            return FetchResult(safe, 0, "", b"", f"{type(exc).__name__}: {exc}"[:200])
        if resp.status != 200:
            return FetchResult(safe, resp.status, "", b"", f"HTTP {resp.status}")
        if len(body) > self.max_bytes:
            return FetchResult(safe, resp.status, "", b"", "Response exceeds byte limit")
        return FetchResult(safe, resp.status, resp.headers.get("Content-Type", ""),
                           body, None, self._validators(resp))

    @staticmethod
    def _validators(resp) -> dict:
        """Only the headers conditional requests need; nothing else stored."""
        out = {}
        for name in ("ETag", "Last-Modified"):
            value = resp.headers.get(name)
            if value:
                out[name] = value
        return out


def make_fetcher(settings: dict) -> SafeFetcher:
    """Single construction site for settings-driven fetchers.

    Tunables live in configs/settings.yaml (`fetch`); literals below are
    fallbacks only, never the source of truth.
    """
    cfg = settings.get("fetch", {})
    return SafeFetcher(
        timeout=float(cfg.get("timeout_s", 20)),
        max_bytes=int(cfg.get("max_bytes", MAX_BODY_BYTES)),
        user_agent=str(cfg.get("user_agent", "MLAITourSourceAuditor/0.1")),
        limiter=RateLimiter(float(cfg.get("delay_s", 1.0))),
    )


def fetch_robots(fetcher: SafeFetcher, site_base: str, origin_host: str):
    """Robots parser or None when unavailable (fail closed upstream)."""
    result = fetcher.fetch(f"{site_base}/robots.txt", origin_host)
    if result.status_code != 200 or result.error:
        return None
    parser = urllib.robotparser.RobotFileParser(f"{site_base}/robots.txt")
    parser.parse(result.body.decode("utf-8", errors="replace").splitlines())
    return parser


def render_url(url: str, output_path: str | Path, timeout: int = 30000,
               capture_net: Path | None = None) -> list[dict[str, object]]:
    """Render one dynamic URL via headless Chromium; optionally capture JSON XHR."""
    from playwright.sync_api import sync_playwright  # pyright: ignore[reportMissingImports]

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    if capture_net is not None:
        capture_net.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, object]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        def on_response(response) -> None:
            ctype = response.headers.get("content-type", "")
            if "json" not in ctype.lower():
                return
            try:
                body = response.body()
                if len(body) > MAX_BODY_BYTES:
                    return
                json.loads(body.decode("utf-8", errors="strict"))
            except Exception:
                return
            base = re.sub(r"[^A-Za-z0-9._-]+", "_", urlsplit(response.url).path.strip("/"))[-60:] or "api"
            name = f"{hashlib.md5(response.url.encode()).hexdigest()[:8]}_{base}.json"
            if capture_net is not None:
                (capture_net / name).write_bytes(body)
            entries.append({"url": response.url, "status": response.status,
                            "content_type": ctype, "file": name, "bytes": len(body)})

        page.on("response", on_response)
        page.goto(url, wait_until="networkidle", timeout=timeout)
        page.wait_for_timeout(1000)
        html = page.content()
        browser.close()

    out.write_text(html, encoding="utf-8")
    if capture_net is not None:
        (capture_net / "network.json").write_text(
            json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Captured {len(entries)} JSON responses -> {capture_net / 'network.json'}")
    print(f"Rendered {url} -> {out} ({len(html)} bytes)")
    return entries


@dataclass(slots=True)
class CapturedTraffic:
    snapshots: list = field(default_factory=list)  # [(label, html)]
    payloads: list = field(default_factory=list)  # [{"url", "data"}]
    interactions: list = field(default_factory=list)  # human-readable log


class BrowserSession:
    """Headless Chromium session (thin OOP: lifecycle state by design).

    Usage:
        with BrowserSession(user_agent=...) as session:
            traffic = session.capture(url, profile)
    The browser attaches the site's own credential (if any); this code never
    reads, stores, or sends tokens/cookies itself.
    """

    def __init__(self, user_agent: str = "MLAITourSourceAuditor/0.1", timeout_ms: int = 60000):
        self.user_agent = user_agent
        self.timeout_ms = timeout_ms
        self._stack = None
        self._browser = None
        self.page: Page | None = None

    def __enter__(self) -> BrowserSession:
        try:
            from playwright.sync_api import sync_playwright  # pyright: ignore[reportMissingImports]
        except ImportError as exc:
            raise RuntimeError("Playwright is not installed; install the 'browser' extra.") from exc
        self._stack = sync_playwright()
        playwright = self._stack.__enter__()
        browser = playwright.chromium.launch(headless=True)
        self.page = browser.new_page(user_agent=self.user_agent)
        self._browser = browser
        return self

    def __exit__(self, *args) -> None:
        try:
            if self.page:
                self.page.close()
            if self._browser:
                self._browser.close()
        finally:
            if self._stack:
                self._stack.__exit__(*args)

    def capture(self, url: str, profile: dict, settings: dict) -> CapturedTraffic:
        page = self.page
        if page is None:
            raise RuntimeError("BrowserSession not started; use 'with BrowserSession()'.")
        traffic = CapturedTraffic()
        browser_cfg = settings.get("browser", {})

        def on_response(response):
            try:
                ctype = response.headers.get("content-type", "").lower()
                if response.request.method != "GET" or "json" not in ctype:
                    return
                body = response.body()
                if len(body) > MAX_BODY_BYTES:
                    return
                data = json.loads(body.decode("utf-8", errors="replace"))
                traffic.payloads.append({"url": response.url, "data": data})
            except Exception:
                pass

        page.on("response", on_response)
        log.info("browser goto %s", url)
        page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
        markers = profile.get("schedule_markers", {})
        heading = markers.get("heading", "")
        if heading:
            try:
                page.get_by_text(heading).first.wait_for(timeout=self.timeout_ms // 2)
                traffic.interactions.append("ready:heading")
            except Exception:
                traffic.interactions.append("ready:heading-timeout")
        tabs = self._find_tabs(page, markers)
        max_tabs = int(browser_cfg.get("max_tabs", 12))
        max_rows = int(browser_cfg.get("max_rows_per_tab", 12))
        wait_ms = int(browser_cfg.get("wait_response_ms", 3000))
        growth_ms = int(browser_cfg.get("tab_growth_wait_ms", 4000))
        for label, tab in tabs[:max_tabs]:
            traffic.interactions.append(f"tab:{label}")
            try:
                before = len(traffic.payloads)
                tab.click(timeout=5000)
                waited = 0
                while waited < growth_ms and len(traffic.payloads) <= before:
                    page.wait_for_timeout(500)
                    waited += 500
            except Exception:
                continue
            expanded: set = set()
            for _ in range(max_rows):
                target = self._next_row(page, markers, expanded)
                if target is None:
                    break
                element, date_text = target
                before = len(traffic.payloads)
                try:
                    element.scroll_into_view_if_needed(timeout=3000)
                    element.click(timeout=5000)
                    waited = 0
                    while waited < wait_ms and len(traffic.payloads) <= before:
                        page.wait_for_timeout(500)
                        waited += 500
                except Exception:
                    expanded.add(date_text)
                    continue
                expanded.add(date_text)
                if len(traffic.payloads) > before:
                    traffic.interactions.append(f"detail:{date_text}")
                    try:
                        traffic.snapshots.append((date_text, page.content()))
                    except Exception:
                        pass
        log.info("browser captured %d payloads, %d snapshots, %d interactions",
                 len(traffic.payloads), len(traffic.snapshots), len(traffic.interactions))
        return traffic

    @staticmethod
    def _find_tabs(page, markers: dict) -> list:
        month_pat = re.compile(markers.get("month_pattern") or r"(?!)")
        found = []
        try:
            for tab in page.get_by_role("tab").all():
                try:
                    if month_pat.search(tab.inner_text() or ""):
                        label = (tab.inner_text() or "").strip().splitlines()[0][:20]
                        found.append((label, tab))
                except Exception:
                    continue
        except Exception:
            pass
        if not found:
            try:
                for button in page.get_by_role("button").all():
                    try:
                        if month_pat.search(button.inner_text() or ""):
                            label = (button.inner_text() or "").strip().splitlines()[0][:20]
                            found.append((label, button))
                    except Exception:
                        continue
            except Exception:
                pass
        return found

    @staticmethod
    def _next_row(page, markers: dict, expanded: set):
        date_pat = re.compile(markers.get("date_pattern") or r"(?!)")
        try:
            candidates = page.get_by_text(date_pat).all()
        except Exception:
            return None
        for candidate in candidates:
            try:
                if not candidate.is_visible():
                    continue
                text = (candidate.inner_text() or "").strip()
                if not date_pat.fullmatch(text):
                    continue
                if text in expanded:
                    continue
                return candidate, text
            except Exception:
                continue
        return None
