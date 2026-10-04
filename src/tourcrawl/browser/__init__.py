"""Real-visitor browser: generic interaction, XHR capture, per-step snapshots."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from shared import get_logger

if TYPE_CHECKING:
    from playwright.sync_api import Page

log = get_logger("browser")


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
            from playwright.sync_api import sync_playwright
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
            raise RuntimeError("BrowserSession not started; use 'with BrowserSession(...)'.")
        traffic = CapturedTraffic()
        browser_cfg = settings.get("browser", {})

        def on_response(response):
            try:
                ctype = response.headers.get("content-type", "").lower()
                if response.request.method != "GET" or "json" not in ctype:
                    return
                body = response.body()
                if len(body) > 2_000_000:
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
                if not re.fullmatch(r"\d{2}/\d{2}/20\d{2}", text):
                    continue
                if text in expanded:
                    continue
                return candidate, text
            except Exception:
                continue
        return None
