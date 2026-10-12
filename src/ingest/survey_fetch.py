"""Complete, polite URL discovery and cached tour-page fetch for surveys."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import urllib.robotparser
from pathlib import Path
from urllib.parse import urlsplit

import yaml

from shared import ensure_utf8_stdout

from .fetch import FetchResult, RateLimiter, SafeFetcher
from .pipeline import search_page_urls, sitemap_urls


class ScopedFetcher:
    """Apply origin and robots policy before delegating to SafeFetcher."""

    def __init__(self, fetcher: SafeFetcher, origin_host: str,
                 robots: urllib.robotparser.RobotFileParser, capture_dir: Path | None = None):
        self.fetcher = fetcher
        self.origin_host = origin_host.lower()
        self.robots = robots
        self.user_agent = fetcher.user_agent
        self.origin_url = ""
        self.capture_dir = capture_dir
        self.capture_enabled = True
        self.use_cache = True
        self.browser_gaps: list[str] = []
        self._discovery_cache_path = (capture_dir / "discovery-cache.json"
                                      if capture_dir is not None else None)
        self._discovery_cache: dict[str, dict[str, str]] = {}
        if self._discovery_cache_path is not None and self._discovery_cache_path.exists():
            try:
                loaded = json.loads(self._discovery_cache_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self._discovery_cache = {
                        str(url): value for url, value in loaded.items()
                        if isinstance(value, dict) and isinstance(value.get("file"), str)
                    }
            except (OSError, ValueError):
                self._discovery_cache = {}

    @staticmethod
    def _origin_key(url: str) -> tuple[str, str, int]:
        parts = urlsplit(url)
        port = parts.port or (443 if parts.scheme == "https" else 80)
        return parts.scheme, (parts.hostname or "").lower(), port

    def _cached(self, url: str) -> FetchResult | None:
        if not self.use_cache or self.capture_dir is None:
            return None
        entry = self._discovery_cache.get(url)
        if entry is None:
            return None
        name = entry.get("file", "")
        if not name or Path(name).name != name:
            return None
        path = (self.capture_dir / name).resolve()
        if self.capture_dir.resolve() not in path.parents or not path.is_file():
            return None
        try:
            if path.stat().st_size > 2_000_000:
                return None
            body = path.read_bytes()
        except OSError:
            return None
        return FetchResult(url, 200, entry.get("content_type", ""), body)

    def _save_discovery_cache(self, url: str, result: FetchResult) -> None:
        if self.capture_dir is None or self._discovery_cache_path is None:
            return
        suffix = "html" if "html" in result.content_type.lower() else "xml"
        name = _safe_name("discovery", url, suffix)
        target = self.capture_dir / name
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_bytes(result.body)
        temporary.replace(target)
        self._discovery_cache[url] = {"file": name, "content_type": result.content_type}
        temporary_index = self._discovery_cache_path.with_suffix(".json.tmp")
        temporary_index.write_text(json.dumps(self._discovery_cache, ensure_ascii=False,
                                              indent=2) + "\n", encoding="utf-8")
        temporary_index.replace(self._discovery_cache_path)

    def fetch(self, url: str, origin_host: str = "", extra_headers: dict | None = None) -> FetchResult:
        host = (urlsplit(url).hostname or "").lower()
        if host != self.origin_host:
            return FetchResult(url, 0, "", error="Cross-origin URL is outside the survey scope")
        if self.origin_url and self._origin_key(url) != self._origin_key(self.origin_url):
            return FetchResult(url, 0, "", error="Cross-origin URL is outside the survey scope")
        if not self.robots.can_fetch(self.user_agent, url):
            return FetchResult(url, 0, "", error="robots.txt disallows URL")
        cached = self._cached(url) if self.capture_enabled else None
        if cached is not None:
            return cached
        # Keep scheme and port in scope through redirect validation.
        result = self.fetcher.fetch(url, self.origin_url or self.origin_host, extra_headers)
        if (self.capture_enabled and self.capture_dir is not None and
                result.status_code == 200 and not result.error):
            self._save_discovery_cache(url, result)
        return result


class SafeBrowserRenderer:
    """Render through a route that re-fetches every resource safely."""

    def __init__(self, fetcher: ScopedFetcher, origin_url: str, raw_dir: Path):
        self.fetcher = fetcher
        self.origin_url = origin_url
        self.raw_dir = raw_dir
        self._stack = None
        self._browser = None
        self._page = None
        self._cache: dict[str, FetchResult] = {}
        self._network: list[dict[str, object]] = []

    def __enter__(self):
        from importlib import import_module

        sync_playwright = import_module("playwright.sync_api").sync_playwright
        self._stack = sync_playwright()
        playwright = self._stack.__enter__()
        self._browser = playwright.chromium.launch(headless=True)
        context = self._browser.new_context(user_agent=self.fetcher.user_agent,
                                            service_workers="block")
        self._page = context.new_page()
        self._page.route("**/*", self._route)
        return self

    def __exit__(self, *_args):
        try:
            if self._browser is not None:
                self._browser.close()
        finally:
            if self._stack is not None:
                self._stack.__exit__(None, None, None)
        target = self.raw_dir / "browser-api"
        target.mkdir(parents=True, exist_ok=True)
        (target / "network.json").write_text(
            json.dumps(self._network, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def _origin_key(url: str) -> tuple[str, str, int]:
        parts = urlsplit(url)
        port = parts.port or (443 if parts.scheme == "https" else 80)
        return parts.scheme, (parts.hostname or "").lower(), port

    def _route(self, route):
        request = route.request
        url = request.url
        essential = request.resource_type in {"document", "xhr", "fetch", "script", "stylesheet"}
        try:
            if request.method != "GET":
                raise OSError(f"blocked_non_get:{request.method}:{url}")
            if self._origin_key(url) != self._origin_key(self.origin_url):
                raise OSError(f"blocked_cross_origin:{url}")
            if not self.fetcher.robots.can_fetch(self.fetcher.user_agent, url):
                raise OSError(f"robots_disallow:{url}")
            result = self._cache.get(url)
            if result is None:
                result = self.fetcher.fetch(url, self.fetcher.origin_host)
                self._cache[url] = result
            if result.error or result.status_code != 200:
                raise OSError(f"browser_resource_failed:{url}:{result.error or result.status_code}")
            if "json" in result.content_type.lower():
                target = self.raw_dir / "browser-api"
                target.mkdir(parents=True, exist_ok=True)
                filename = _safe_name("response", url, "json")
                response_path = target / filename
                if not response_path.exists():
                    response_path.write_bytes(result.body)
                    self._network.append({"url": url, "status": result.status_code,
                                          "content_type": result.content_type,
                                          "file": filename, "bytes": len(result.body)})
            route.fulfill(status=200,
                          headers={"content-type": result.content_type or "application/octet-stream"},
                          body=result.body)
        except Exception as exc:
            if essential:
                self.fetcher.browser_gaps.append(str(exc)[:300])
            try:
                route.abort()
            except Exception:
                pass

    def render(self, url: str) -> tuple[bytes, str | None]:
        if self._page is None:
            return b"", "browser_not_started"
        before = len(self.fetcher.browser_gaps)
        try:
            response = self._page.goto(url, wait_until="domcontentloaded", timeout=60000)
            if response is None or response.status != 200:
                return b"", f"render_navigation_failed:{response.status if response else 'no response'}"
            try:
                self._page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                # Polling pages are still checked by field-level self-test.
                pass
            body = self._page.content().encode("utf-8")
        except Exception as exc:
            return b"", f"render_failed:{type(exc).__name__}:{exc}"[:300]
        if len(body) > 2_000_000:
            return b"", "rendered_document_exceeds_2mb"
        if len(self.fetcher.browser_gaps) > before:
            return b"", ";".join(self.fetcher.browser_gaps[before:])[:500]
        return body, None


def _safe_name(prefix: str, url: str, suffix: str) -> str:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    path = re.sub(r"[^a-zA-Z0-9._-]+", "-", urlsplit(url).path.strip("/"))[-48:]
    return f"{prefix}-{path or 'root'}-{digest}.{suffix}"


def _unique_tour_urls(urls: list[str], strip_query: bool) -> list[str]:
    unique: dict[str, str] = {}
    for url in urls:
        parts = urlsplit(url)
        path = parts.path.rstrip("/") or "/"
        query = "" if strip_query else parts.query
        key = parts._replace(scheme=parts.scheme.lower(), netloc=parts.netloc.lower(),
                             path=path, query=query, fragment="").geturl()
        unique.setdefault(key, key)
    return list(unique.values())


def _read_robots(fetcher: SafeFetcher, base: str, host: str, raw_dir: Path):
    url = f"{base}/robots.txt"
    result = fetcher.fetch(url, base)
    if result.error and result.status_code not in (404, 410):
        raise RuntimeError(f"robots.txt unavailable: {result.error}")
    text = result.body.decode("utf-8", errors="replace") if result.status_code == 200 else ""
    (raw_dir / "robots.txt").write_text(text, encoding="utf-8")
    parser = urllib.robotparser.RobotFileParser(url)
    parser.parse(text.splitlines())
    return parser, text


def _fetch_tour_pages(urls: list[str], raw_dir: Path, scoped: ScopedFetcher,
                      *, render: bool, renderer: SafeBrowserRenderer | None = None,
                      refresh: bool = False
                      ) -> tuple[list[dict[str, str]], list[str]]:
    rows: list[dict[str, str]] = []
    gaps: list[str] = []
    prefix = "tour-rendered" if render else "tour"
    for index, url in enumerate(urls, 1):
        if not scoped.robots.can_fetch(scoped.user_agent, url):
            rows.append({"index": str(index), "url": url, "file": "",
                         "status": "blocked", "error": "robots.txt disallows URL"})
            gaps.append(f"tour_blocked:{url}")
            continue
        cached = raw_dir / _safe_name(prefix, url, "html")
        if not refresh and cached.exists() and cached.stat().st_size <= 2_000_000:
            rows.append({"index": str(index), "url": url, "file": cached.name,
                         "status": "cached", "error": ""})
            continue
        if render:
            if renderer is None:
                error = "playwright_renderer_unavailable"
                body = b""
            else:
                body, render_error = renderer.render(url)
                error = render_error or ""
        else:
            result = scoped.fetch(url, scoped.origin_host)
            body = result.body
            error = result.error or (f"HTTP {result.status_code}" if result.status_code != 200 else "")
        if error:
            rows.append({"index": str(index), "url": url, "file": "",
                         "status": "fetch_fail", "error": error})
            gaps.append(f"tour_fetch_failed:{url}:{error}")
            continue
        if len(body) > 2_000_000:
            error = "response_exceeds_2mb"
            rows.append({"index": str(index), "url": url, "file": "",
                         "status": "fetch_fail", "error": error})
            gaps.append(f"tour_fetch_failed:{url}:{error}")
            continue
        cached.write_bytes(body)
        rows.append({"index": str(index), "url": url, "file": cached.name,
                     "status": "ok", "error": ""})
    return rows, gaps


def fetch_all(profile_path: Path, raw_dir: Path, *, timeout_s: float = 20.0,
              retries: int = 2, delay_s: float = 1.0,
              refresh: bool = False) -> dict:
    profile_path = Path(profile_path)
    raw_dir = Path(raw_dir)
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}
    if not isinstance(profile, dict) or not profile.get("origin"):
        raise ValueError("profile must declare origin")
    patterns = [str(item) for item in profile.get("tour_url_patterns", []) if item]
    if not patterns:
        raise ValueError("profile must declare tour_url_patterns")
    origin = str(profile["origin"])
    parsed = urlsplit(origin if "://" in origin else f"https://{origin}")
    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError("profile origin is not an absolute host")
    base = f"{parsed.scheme}://{parsed.netloc}"
    raw_dir.mkdir(parents=True, exist_ok=True)

    fetcher = SafeFetcher(timeout=timeout_s, max_bytes=2_000_000,
                          user_agent="MLAITourSourceAuditor/0.1",
                          limiter=RateLimiter(max(1.0, delay_s)), retries=retries)
    try:
        robots, robots_text = _read_robots(fetcher, base, host, raw_dir)
    except RuntimeError as exc:
        (raw_dir / "tour_pages.csv").write_text("index,url,file,status,error\n", encoding="utf-8")
        report = {"origin": base, "discovered_sitemap": 0, "discovered_listing": 0,
                  "discovered_unique": 0, "fetched_or_cached": 0,
                  "gaps": [f"robots_unavailable:{exc}"],
                  "manifest": str(raw_dir / "tour_pages.csv")}
        (raw_dir / "tour_urls.txt").write_text("", encoding="utf-8")
        (raw_dir / "survey_fetch_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return report
    scoped = ScopedFetcher(fetcher, host, robots, raw_dir)
    scoped.origin_url = base
    scoped.use_cache = not refresh
    gaps: list[str] = []
    declared = [str(url) for url in profile.get("sitemaps", [])]
    from_robots = []
    for line in robots_text.splitlines():
        if line.lower().startswith("sitemap:"):
            sitemap = line.split(":", 1)[1].strip()
            if (urlsplit(sitemap).hostname or "").lower() == host:
                from_robots.append(sitemap)
    sitemap_candidates = list(dict.fromkeys([*declared, *from_robots]))
    sitemap_list = [url for url in sitemap_candidates
                    if (urlsplit(url).hostname or "").lower() == host]
    gaps.extend(f"cross_origin_sitemap:{url}" for url in sitemap_candidates
                if (urlsplit(url).hostname or "").lower() != host)
    discovery = profile.get("discovery") or {}
    if not sitemap_list and discovery.get("method") != "search_pages":
        sitemap_list = [f"{base}/sitemap.xml"]
    sitemap_tours = sitemap_urls(scoped, sitemap_list, patterns,
                                 attempts=retries, gaps=gaps)

    listing_tours: list[str] = []
    listing_configs: list[dict] = []
    if discovery.get("method") == "search_pages":
        listing_configs.append(discovery)
    elif isinstance(discovery.get("listing"), dict):
        listing_configs.append(discovery["listing"])
    extras = discovery.get("listings", [])
    if isinstance(extras, list):
        listing_configs.extend(item for item in extras if isinstance(item, dict))
    for listing in listing_configs:
        if not listing.get("entry"):
            gaps.append("listing_missing_entry_url")
            continue
        listing_tours.extend(search_page_urls(scoped, listing, patterns,
                                              attempts=retries, workers=1, gaps=gaps))
    scoped.capture_enabled = False
    # Include every discovery source available and normalize query variants.
    strip_query = bool(discovery.get("strip_query", True))
    sitemap_unique = _unique_tour_urls(sitemap_tours, strip_query)
    listing_unique = _unique_tour_urls(listing_tours, strip_query)
    sitemap_set = set(sitemap_unique)
    listing_set = set(listing_unique)
    urls = _unique_tour_urls([*sitemap_unique, *listing_unique], strip_query)
    (raw_dir / "tour_urls.txt").write_text("".join(f"{url}\n" for url in urls), encoding="utf-8")
    if not urls:
        gaps.append("no_tour_urls_discovered")

    manifest = raw_dir / "tour_pages.csv"
    fields = ["index", "url", "file", "status", "error"]
    render = bool(profile.get("render"))
    try:
        if render:
            with SafeBrowserRenderer(scoped, base, raw_dir) as renderer:
                rows, fetch_gaps = _fetch_tour_pages(urls, raw_dir, scoped,
                                                     render=True, renderer=renderer,
                                                     refresh=refresh)
        else:
            rows, fetch_gaps = _fetch_tour_pages(urls, raw_dir, scoped, render=False,
                                                 refresh=refresh)
    except Exception as exc:
        rows = [{"index": str(index), "url": url, "file": "",
                 "status": "fetch_fail", "error": f"renderer_unavailable:{exc}"}
                for index, url in enumerate(urls, 1)]
        fetch_gaps = [f"renderer_unavailable:{exc}"]
    gaps.extend(fetch_gaps)

    with manifest.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    report = {
        "origin": base,
        "discovered_sitemap": len(sitemap_unique),
        "discovered_listing": len(listing_unique),
        "discovered_unique": len(urls),
        "source_overlap": len(sitemap_set & listing_set),
        "sitemap_only": len(sitemap_set - listing_set),
        "listing_only": len(listing_set - sitemap_set),
        "fetched_or_cached": sum(row["status"] in {"ok", "cached"} for row in rows),
        "cache_mode": "refresh" if refresh else "reuse",
        "gaps": list(dict.fromkeys(gaps)),
        "manifest": str(manifest),
    }
    (raw_dir / "survey_fetch_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdout()
    parser = argparse.ArgumentParser(prog="ingest-survey-fetch")
    parser.add_argument("--profile", required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--timeout-s", type=float, default=20.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--delay-s", type=float, default=1.0)
    parser.add_argument("--refresh", action="store_true",
                        help="refetch discovery and tour pages instead of using raw-dir cache")
    args = parser.parse_args(argv)
    try:
        report = fetch_all(args.profile, args.raw_dir, timeout_s=args.timeout_s,
                           retries=args.retries, delay_s=args.delay_s, refresh=args.refresh)
    except (OSError, ValueError, RuntimeError, yaml.YAMLError) as exc:
        print(f"survey fetch failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not report["gaps"] and report["discovered_unique"] else 1


if __name__ == "__main__":
    from shared.runtime import run_cli

    raise SystemExit(run_cli(main))
