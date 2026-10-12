"""Batch orchestration: resume, budgets, exit codes. Single team entry point.

No parsing here; argv handling also lives here so `python -m ingest`
needs no extra layer.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import os
import queue
import re
import sys
import threading
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable, Generator, Sequence
from pathlib import Path
from typing import Protocol
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from shared import ensure_utf8_stdout, get_logger, now_vn_iso

from . import extract, quality
from .extract import load_profile, load_settings
from .fetch import BrowserSession, FetchResult, fetch_robots, make_fetcher
from .quality import BLOCKED, FETCH_FAIL, OK, PARSE_FAIL, departure_evidence, verify_record_fields

log = get_logger("pipeline")


class Fetcher(Protocol):
    """Transport interface shared by the guarded survey wrapper and crawler."""

    def fetch(self, url: str, origin_host: str = "",
              extra_headers: dict | None = None) -> FetchResult: ...

CSV_COLUMNS = ["url", "observed_at", "profile", "status", "title",
               "departures", "verified", "notes_keys", "record_evidence", "error"]


def _fetch_sitemap(fetcher: Fetcher, sitemap: str, attempts: int = 2,
                   origin_host: str = "", gaps: list[str] | None = None) -> bytes | None:
    """Retry `attempts` times; None when all fail (logged once)."""
    last_error: object = "unknown"
    for _ in range(max(1, attempts)):
        result = fetcher.fetch(sitemap, origin_host)
        if result.status_code == 200 and not result.error:
            if sitemap.lower().endswith(".gz"):
                try:
                    with gzip.GzipFile(fileobj=io.BytesIO(result.body)) as stream:
                        body = stream.read(2_000_001)
                except (OSError, EOFError) as exc:
                    log.warning("sitemap gzip invalid %s %s", sitemap, exc)
                    if gaps is not None:
                        gaps.append(f"sitemap_decompress_failed:{sitemap}")
                    return None
                if len(body) > 2_000_000:
                    if gaps is not None:
                        gaps.append(f"sitemap_decompressed_over_2mb:{sitemap}")
                    return None
                return body
            return result.body
        last_error = result.error or result.status_code
    log.warning("sitemap failed %s %s", sitemap, last_error)
    return None


def _urlset_entries(body: bytes, patterns: list[str]) -> list[tuple[str, str]]:
    """(url, lastmod) pairs from one urlset document; lastmod may be empty."""
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return []
    out: list[tuple[str, str]] = []
    for url_node in root.iter():
        if url_node.tag.rsplit("}", 1)[-1] != "url":
            continue
        loc = ""
        lastmod = ""
        for child in url_node:
            tag = child.tag.rsplit("}", 1)[-1]
            if tag == "loc" and child.text:
                loc = child.text.strip()
            elif tag == "lastmod" and child.text:
                lastmod = child.text.strip()
        if loc and any(pat in loc for pat in patterns):
            out.append((loc, lastmod))
    if not out:
        for node in root.iter():
            if node.tag.rsplit("}", 1)[-1] == "loc" and node.text:
                url = node.text.strip()
                if any(pat in url for pat in patterns):
                    out.append((url, ""))
    return out


def sitemap_urls(fetcher: Fetcher, sitemaps: list[str],
                 patterns: list[str], min_lastmod: str = "",
                 attempts: int = 2, gaps: list[str] | None = None) -> list[str]:
    """Tour URLs from same-origin sitemaps, recursively following indexes.

    Freshest first (by sitemap lastmod, ISO strings compare directly);
    `min_lastmod` drops anything older. Lastmod is a crawl-ordering hint
    only, never published as tour data.
    """
    stamped: dict[str, str] = {}
    seed = next((url for url in sitemaps if urlsplit(url).hostname), "")
    origin_host = (urlsplit(seed).hostname or "").lower()
    queue = list(dict.fromkeys(sitemaps))
    seen_sitemaps: set[str] = set()
    while queue:
        sitemap = queue.pop(0)
        if sitemap in seen_sitemaps:
            continue
        seen_sitemaps.add(sitemap)
        if (urlsplit(sitemap).hostname or "").lower() != origin_host:
            if gaps is not None:
                gaps.append(f"cross_origin_sitemap:{sitemap}")
            continue
        body = _fetch_sitemap(fetcher, sitemap, attempts, origin_host, gaps)
        if body is None:
            if gaps is not None:
                gaps.append(f"sitemap_fetch_failed:{sitemap}")
            continue
        try:
            root = ET.fromstring(body)
        except ET.ParseError:
            log.warning("sitemap unparseable %s", sitemap)
            if gaps is not None:
                gaps.append(f"sitemap_parse_failed:{sitemap}")
            continue
        if root.tag.rsplit("}", 1)[-1] == "sitemapindex":
            for node in root.iter():
                if node.tag.rsplit("}", 1)[-1] == "loc" and node.text:
                    child = node.text.strip()
                    if child and child not in seen_sitemaps:
                        queue.append(child)
            continue
        for url, lastmod in _urlset_entries(body, patterns):
            if (urlsplit(url).hostname or "").lower() != origin_host:
                if gaps is not None:
                    gaps.append(f"cross_origin_tour_url:{url}")
                continue
            if url not in stamped or (lastmod and lastmod > stamped[url]):
                stamped[url] = lastmod
    if min_lastmod:
        stamped = {url: stamp for url, stamp in stamped.items() if stamp >= min_lastmod}
    ordered = sorted(stamped, key=lambda url: (stamped[url], url), reverse=True)
    log.info("sitemap urls: %d tours from %d sitemaps", len(ordered), len(seen_sitemaps))
    return ordered


def _page_url(entry: str, page_param: str, per_page_param: str,
              per_page: int, page: int) -> str:
    """Entry URL with the page number (and page size) set, rest preserved."""
    parts = urlsplit(entry)
    query = [(k, v) for k, v in parse_qsl(parts.query) if k != page_param]
    query.append((page_param, str(page)))
    if per_page_param and per_page and all(k != per_page_param for k, _ in query):
        query.append((per_page_param, str(per_page)))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


_HREF_RE = re.compile(r'href="([^"]+)"|href=\'([^\']+)\'', re.I)


def _listing_links(body: bytes, entry: str, patterns: list[str]) -> list[str]:
    """Tour hrefs from one SSR list page, made absolute, same-origin only."""
    html = body.decode("utf-8", errors="replace")
    base = urlsplit(entry)
    out: list[str] = []
    for double_quoted, single_quoted in _HREF_RE.findall(html):
        href = (double_quoted or single_quoted).strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        href = urljoin(entry, href)
        parts = urlsplit(href)
        if parts.scheme != base.scheme or parts.netloc.lower() != base.netloc.lower():
            continue
        if any(pat in parts.path for pat in patterns):
            out.append(href)
    return out


def _listing_max_page(body: bytes, page_param: str, cap: int) -> int:
    """Highest ?page=N seen in paging links, capped; at least 1."""
    html = body.decode("utf-8", errors="replace")
    best = 1
    for double_quoted, single_quoted in _HREF_RE.findall(html):
        href = double_quoted or single_quoted
        for key, value in parse_qsl(urlsplit(href).query):
            if key == page_param and value.isdigit():
                best = max(best, int(value))
    return max(1, min(best, cap))


def _fetch_listing_page(page: int, entry: str, page_param: str, per_page_param: str,
                        per_page: int, attempts: int, fetcher: Fetcher,
                        factory: Callable[[], Fetcher] | None) -> bytes | None:
    worker = factory() if factory is not None else fetcher
    return _fetch_sitemap(worker, _page_url(entry, page_param, per_page_param, per_page, page),
                          attempts)


def search_page_urls(fetcher: Fetcher, discovery: dict,
                     patterns: list[str], attempts: int = 2, workers: int = 1,
                     limit: int = 0,
                     on_page: Callable[[int, list[str]], None] | None = None,
                     fetcher_factory: Callable[[], Fetcher] | None = None,
                     gaps: list[str] | None = None) -> list[str]:
    """Unique tour slugs from SSR paginated lists (one card link per departure).

    Page 1 reveals the real last page via its paging links; iteration stops
    there, at `max_pages`, or as soon as `limit` unique slugs are collected.
    Pages after the first go out in waves of `workers` (each wave processed in
    page order, so dedupe order is deterministic); `on_page` fires per page
    with that page's fresh slugs so callers can persist incrementally.
    `strip_query` drops per-departure params (?startday=...) so tour x N dates
    dedupes to one slug.
    """
    entry = discovery.get("entry", "")
    page_param = discovery.get("page_param", "page")
    per_page_param = discovery.get("per_page_param", "")
    per_page = int(discovery.get("per_page") or 0)
    cap = max(1, int(discovery.get("max_pages") or 1))
    strip = bool(discovery.get("strip_query", True))
    seen: dict[str, None] = {}
    raw = 0

    def harvest(body: bytes) -> list[str]:
        nonlocal raw
        fresh: list[str] = []
        for href in _listing_links(body, entry, patterns):
            raw += 1
            parts = urlsplit(href)
            key = (urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
                   if strip else href.split("#")[0])
            if key not in seen:
                seen[key] = None
                fresh.append(key)
        return fresh

    origin_host = (urlsplit(entry).hostname or "").lower()
    if not origin_host:
        if gaps is not None:
            gaps.append("invalid_listing_origin")
        return []
    first = _fetch_sitemap(fetcher, _page_url(entry, page_param, per_page_param, per_page, 1),
                           attempts, origin_host)
    if first is None:
        if gaps is not None:
            gaps.append(f"listing_fetch_failed:page=1:{entry}")
        return []
    if on_page is not None:
        on_page(1, harvest(first))
    else:
        harvest(first)
    if limit > 0 and len(seen) >= limit:
        ordered = list(seen)[:limit]
        log.info("search pages: %d unique tours from %d raw links over 1 page (limit hit)",
                 len(ordered), raw)
        return ordered
    detected_pages = _listing_max_page(first, page_param, max(cap, 2**31 - 1))
    if detected_pages > cap and gaps is not None:
        gaps.append(f"listing_page_cap:{detected_pages}>{cap}")
    pages = min(detected_pages, cap)
    log.info("search pages: walking %d pages", pages)
    width = 1 if workers <= 1 else max(2, workers * 2)
    for start in range(2, pages + 1, width):
        chunk = list(range(start, min(start + width, pages + 1)))
        wave_stop = threading.Event()
        drain = _map_ordered(
            lambda page, _e=entry, _pp=page_param, _ppp=per_page_param,
            _n=per_page, _a=attempts, _f=fetcher, _ff=fetcher_factory:
            _fetch_listing_page(page, _e, _pp, _ppp, _n, _a, _f, _ff),
            chunk, workers, wave_stop)
        stopped = False
        for index, outcome in drain:
            page = chunk[index]
            if isinstance(outcome, BaseException):
                if not isinstance(outcome, Exception):
                    drain.close()
                    raise outcome
                log.warning("search page %d failed %s", page, outcome)
                if gaps is not None:
                    gaps.append(f"listing_fetch_failed:page={page}:{outcome}")
                continue
            body = outcome
            if body is None:
                if gaps is not None:
                    gaps.append(f"listing_fetch_failed:page={page}")
                continue
            fresh = harvest(body)
            if on_page is not None:
                on_page(page, fresh)
            if limit > 0 and len(seen) >= limit:
                stopped = True
                break
        drain.close()
        if stopped:
            break
    ordered = list(seen)[:limit] if limit > 0 else list(seen)
    log.info("search pages: %d unique tours from %d raw links over %d pages",
             len(ordered), raw, pages)
    return ordered


def discover_urls(fetcher: Fetcher, profile: dict,
                  patterns: list[str], min_lastmod: str = "",
                  attempts: int = 2, workers: int = 1, limit: int = 0,
                  on_page: Callable[[int, list[str]], None] | None = None,
                  fetcher_factory: Callable[[], Fetcher] | None = None,
                  gaps: list[str] | None = None) -> list[str]:
    """Enumerate tour URLs via the profile's declared discovery method."""
    discovery = profile.get("discovery") or {"method": "sitemap"}
    if discovery.get("method") == "search_pages" and discovery.get("entry"):
        return search_page_urls(fetcher, discovery, patterns, attempts, workers,
                                limit, on_page, fetcher_factory, gaps)
    return sitemap_urls(fetcher, profile.get("sitemaps", []), patterns,
                        min_lastmod=min_lastmod, attempts=attempts, gaps=gaps)


def _save_discovered(urls: list[str], path: Path) -> Path:
    """Persist a discovery URL list for --batch (one `url` column)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["url"])
        writer.writeheader()
        for url in urls:
            writer.writerow({"url": url})
    return path


def _read_done(path: Path) -> set[str]:
    """URLs already settled; fetch failures are NOT done (retried next run)."""
    if not path.exists():
        return set()
    with path.open(encoding="utf-8-sig") as handle:
        return {row["url"] for row in csv.DictReader(handle)
                if row.get("url") and row.get("status") not in (FETCH_FAIL, BLOCKED)}


def _map_ordered(func: Callable, items: Sequence, workers: int,
                 stop: threading.Event) -> Generator:
    """Run func(item) on daemon threads; yield (index, outcome) in submit order.

    Threads are daemon so Ctrl+C (FastExit/KeyboardInterrupt via run_cli)
    returns within one poll tick (~0.2s) instead of waiting for in-flight
    network calls; the caller must flush its own progress (CSV/_state) on
    early exit. func exceptions arrive as values for the caller to handle.
    Breaking out of the iteration stops the pool.
    """
    inbox: queue.Queue = queue.Queue()
    outbox: queue.Queue = queue.Queue()
    jobs = list(items)
    for index, item in enumerate(jobs):
        inbox.put((index, item))
    for _ in range(max(1, workers)):
        inbox.put(None)

    def _worker() -> None:
        while not stop.is_set():
            try:
                job = inbox.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                if job is None:
                    return
                index, item = job
                try:
                    outbox.put((index, func(item)))
                except BaseException as exc:  # never strand the ordered drain
                    outbox.put((index, exc))
            finally:
                inbox.task_done()

    for number in range(max(1, workers)):
        thread = threading.Thread(target=_worker, name=f"ingest-pool-{number}", daemon=True)
        thread.start()
    try:
        buffered: dict[int, object] = {}
        next_index = 0
        yielded = 0
        while yielded < len(jobs):
            if stop.is_set():
                return
            try:
                index, outcome = outbox.get(timeout=0.2)
            except queue.Empty:
                continue
            buffered[index] = outcome
            while next_index in buffered:
                yield next_index, buffered.pop(next_index)
                next_index += 1
                yielded += 1
    finally:
        stop.set()


def run_tour(url: str, profile: dict, settings: dict, out_dir: Path,
             robots_cache: dict | None = None,
             conditional: dict | None = None) -> dict:
    """One tour end-to-end. Returns a status-tagged result dict.

    Pass a shared `robots_cache` dict from batch runs so robots.txt is
    fetched once per origin; single calls without it behave as before.
    Pass `conditional` (etag/last_modified/hash from a previous snapshot)
    to skip parsing when the page is unchanged; the row then carries
    status `not_modified` plus a `_state_entry` for the caller to persist
    (CSV writer ignores the private key).
    """
    fetcher = make_fetcher(settings)
    origin = (urlsplit(url).hostname or "").lower()
    site_base = f"{urlsplit(url).scheme}://{origin}"
    observed = now_vn_iso()

    if robots_cache is not None and site_base in robots_cache:
        robots = robots_cache[site_base]
    else:
        robots = fetch_robots(fetcher, site_base, origin)
        if robots_cache is not None:
            robots_cache[site_base] = robots
    if robots is not None and not robots.can_fetch(fetcher.user_agent, url):
        return {"url": url, "status": BLOCKED, "error": "robots.txt disallows URL"}

    extra_headers: dict = {}
    if conditional:
        if conditional.get("etag"):
            extra_headers["If-None-Match"] = conditional["etag"]
        if conditional.get("last_modified"):
            extra_headers["If-Modified-Since"] = conditional["last_modified"]
    page = fetcher.fetch(url, origin, extra_headers or None)
    if page.error or page.status_code not in (200, 304):
        return {"url": url, "status": FETCH_FAIL,
                "error": page.error or f"HTTP {page.status_code}"}
    if page.status_code == 304:
        prior = conditional or {}
        return {"url": url, "observed_at": observed, "profile": profile.get("name", ""),
                "status": "not_modified", "title": "", "departures": 0,
                "verified": 0, "notes_keys": "", "error": "",
                "_state_entry": {"etag": page.headers.get("ETag", prior.get("etag", "")),
                                 "last_modified": page.headers.get("Last-Modified", prior.get("last_modified", "")),
                                 "hash": prior.get("hash", ""),
                                 "observed_at": observed}}
    body_hash = hashlib.sha256(page.body).hexdigest()
    if conditional and conditional.get("hash") == body_hash:
        return {"url": url, "observed_at": observed, "profile": profile.get("name", ""),
                "status": "not_modified", "title": "", "departures": 0,
                "verified": 0, "notes_keys": "", "error": "",
                "_state_entry": {"etag": page.headers.get("ETag", ""),
                                 "last_modified": page.headers.get("Last-Modified", ""),
                                 "hash": body_hash, "observed_at": observed}}
    html = page.body.decode("utf-8", errors="replace")
    fresh_state = {"etag": page.headers.get("ETag", ""),
                   "last_modified": page.headers.get("Last-Modified", ""),
                   "hash": body_hash, "observed_at": observed}

    clean_cfg = settings.get("clean", {})
    merged: dict = {
        "url": page.url,
        "fetched_at": observed,
        "profile": profile.get("name", ""),
        "title": "",
        "json_ld": extract.parse_json_ld(html),
        "page_prose": "",
        "departure_schedule": None,
    }
    title = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
    if title:
        merged["title"] = re.sub(r"\s+", " ", title.group(1)).strip()[:200]

    merged["page_prose"] = extract.page_prose(html)

    if profile.get("fields"):
        record, record_raw, extraction_states = extract.crawl_fields_detailed(
            html, profile, extract.same_origin_getter(page.url, fetcher, robots))
        merged["record"] = record
        merged["record_raw"] = record_raw
        verdict, missing, field_checks = verify_record_fields(
            record, record_raw, html, profile, extraction_states, merged["json_ld"])
        merged["record_evidence"] = verdict
        merged["record_missing"] = missing
        merged["record_field_checks"] = field_checks

    browser_error = ""
    rendered_text = ""
    if "browser" in profile.get("flows", []) or "combo_api_browser" in profile.get("flows", []):
        try:
            with BrowserSession(user_agent=fetcher.user_agent,
                                timeout_ms=int(settings.get("browser", {}).get("timeout_ms", 60000))
                                ) as session:
                traffic = session.capture(url, profile, settings)
            departures: list = []
            for payload in traffic.payloads:
                extract.walk_departures(payload["data"], departures)
            merged_deps: dict = {}
            for dep in departures:
                key = (dep.get("departureDate"), dep.get("tourCode"))
                entry = merged_deps.setdefault(key, {})
                for field, value in dep.items():
                    if entry.get(field) in (None, "", [], {}):
                        entry[field] = value
            unique = list(merged_deps.values())
            notes_pat = profile.get("notes_key_pattern", "")
            notes = quality.extract_notes(
                [p["data"] for p in traffic.payloads], notes_pat,
                int(clean_cfg.get("min_visible_chars", 40))) if notes_pat else {}
            rendered_text = extract.page_text_only(
                "\n".join(html for _, html in traffic.snapshots))
            for dep in unique:
                dep["detail_status"] = "api-only"
            presentation = set(profile.get("junk_presentation_keys", []) or [])
            keep = quality.compile_keep(profile.get("keep_patterns", []))
            unique = [quality.filter_dep(dep, presentation, keep,
                                       int(clean_cfg.get("min_visible_chars", 40)))
                      for dep in unique]
            unique, shared = quality.dedupe_departures(unique)
            unique = [quality.normalize_offer(dep) for dep in unique]
            unique = quality.sort_offers(unique)
            context = rendered_text + "\n" + merged["page_prose"] + "\n" + json.dumps(
                unique, ensure_ascii=False)
            for dep in unique:
                dep["evidence"] = departure_evidence(dep, context)
            merged["departure_schedule"] = {
                "source": "schedule-api-via-browser",
                "departures": unique,
                "shared": shared,
                "notes": notes,
                "interactions": traffic.interactions,
                "rendered_text": rendered_text,
        "fetched_at": observed,
            }
        except Exception as exc:
            browser_error = f"{type(exc).__name__}: {exc}"[:200]
            log.warning("browser flow failed %s %s", url, browser_error)

    out_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", page.url.lower()).strip("-")[:50]
    digest = hashlib.sha256(page.url.encode("utf-8")).hexdigest()[:12]
    detail_path = out_dir / f"tour_{slug}-{digest}.json"
    tmp_path = detail_path.with_name(detail_path.name + ".tmp")
    tmp_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp_path, detail_path)

    departures = (merged["departure_schedule"] or {}).get("departures", [])
    notes = (merged["departure_schedule"] or {}).get("notes", {})
    verified = sum(1 for dep in departures if dep.get("evidence") == "verified")
    status = OK if (merged["title"] or departures) else PARSE_FAIL
    error = "" if status == OK else (browser_error or "empty result")
    return {"url": page.url, "observed_at": observed, "profile": merged["profile"],
            "status": status, "title": merged["title"], "departures": len(departures),
            "verified": verified, "notes_keys": ",".join(sorted(notes.keys())),
            "record_evidence": merged.get("record_evidence", ""), "error": error,
            "detail_file": str(detail_path), "_state_entry": fresh_state}


def _state_path(settings: dict) -> Path:
    """Snapshot state lives beside the output dir so re-snapshots skip unchanged pages.

    Shared across sources on purpose: keys are full tour URLs, so entries
    never collide between sources.
    """
    return Path(settings.get("output", {}).get("dir", ".local")) / "_state.json"


def _source_dir(settings: dict, source: str) -> Path:
    """Per-source output root: <output.dir>/<source>/ (multi-source safe)."""
    return Path(settings.get("output", {}).get("dir", ".local")) / source


def _load_state(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def _write_quality(settings: dict, profile: dict, detail_paths: Sequence[str]) -> dict:
    """Per-run quality snapshot plus warn-only drift against the previous run."""
    source = str(profile.get("name", "default"))
    path = _source_dir(settings, source) / "quality.json"
    cfg = settings.get("quality", {})
    fill_fields = list(cfg.get("fill_fields", ["tour_name", "departure_city",
                        "destinations", "duration_days", "price", "currency",
                        "itinerary", "inclusions", "exclusions"]))
    details = []
    for name in detail_paths:
        try:
            details.append(json.loads(Path(name).read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    current = quality.summarize_details(details, fill_fields)
    try:
        previous = json.loads(path.read_text(encoding="utf-8")).get("summary", {})
    except (OSError, ValueError):
        previous = {}
    if not isinstance(previous, dict):
        previous = {}
    warnings = quality.compare_quality(current, previous, cfg) if previous else []
    for warning in warnings:
        log.warning("quality drift %s", warning)
    path.parent.mkdir(parents=True, exist_ok=True)
    snapshot = {"observed_at": now_vn_iso(), "summary": current, "warnings": warnings}
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return snapshot


def run_batch(urls: list[str], profile: dict, settings: dict, output: Path,
              out_dir: Path | None = None) -> int:
    """Append one CSV row per tour; resume by URL. Returns process exit code."""
    batch_cfg = settings.get("batch", {})
    max_fails = int(batch_cfg.get("max_consecutive_failures", 10))
    gap = float(batch_cfg.get("delay_s", 1.0))
    if out_dir is None:
        out_dir = _source_dir(settings, str(profile.get("name", "default"))) / "tours"
    done = _read_done(output)
    state_path = _state_path(settings)
    state = _load_state(state_path)
    todo = [url for url in urls if url not in done]
    log.info("batch: %d urls (%d skipped)", len(todo), len(urls) - len(todo))

    output.parent.mkdir(parents=True, exist_ok=True)
    new_file = not output.exists()
    fails = 0
    robots_cache: dict = {}
    detail_paths: list[str] = []
    workers = max(1, int(batch_cfg.get("workers", 4)))
    needs_browser = "browser" in profile.get("flows", []) or "combo_api_browser" in profile.get("flows", [])
    if workers == 1 or needs_browser:
        if needs_browser and workers > 1:
            log.info("browser flow runs sequentially; workers=%d applies to static tours", workers)
        with output.open("a", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
            if new_file:
                writer.writeheader()
            try:
                for index, url in enumerate(todo, 1):
                    log.info("tour %d/%d %s", index, len(todo), url)
                    try:
                        row = run_tour(url, profile, settings, out_dir, robots_cache,
                                       state.get(url))
                    except Exception as exc:
                        row = {"url": url, "status": FETCH_FAIL, "error": f"{type(exc).__name__}"}
                    if "_state_entry" in row:
                        state[url] = row.pop("_state_entry")
                    if row.get("detail_file"):
                        detail_paths.append(row["detail_file"])
                    writer.writerow({k: row.get(k, "") for k in CSV_COLUMNS})
                    handle.flush()
                    if index % 10 == 0:
                        _save_state(state_path, state)
                    if row.get("status") in (FETCH_FAIL, BLOCKED):
                        fails += 1
                        if fails >= max_fails:
                            log.error("failure budget exhausted (%d)", fails)
                            _save_state(state_path, state)
                            return 1
                    else:
                        fails = 0
                    if index < len(todo):
                        time.sleep(gap)
            except BaseException:
                _save_state(state_path, state)
                raise
        _save_state(state_path, state)
        _write_quality(settings, profile, detail_paths)
        log.info("batch done: wrote %s", output)
        return 0

    _prime_robots_cache(todo, settings, robots_cache)
    polite_gap = max(float(batch_cfg.get("delay_s", 1.0)),
                     float(settings.get("fetch", {}).get("delay_s", 1.0)))
    origin_next: dict[str, float] = {}
    polite_guard = threading.Lock()

    def _polite_wait(origin: str) -> None:
        """Space request starts per origin; parse stays parallel.

        The old per-origin mutex held the whole tour (fetch+parse+sleep),
        serializing single-source batches to 1 worker. Spacing only the
        start keeps the politeness knob while letting workers overlap.
        """
        wait_for = 0.0
        now = time.monotonic()
        with polite_guard:
            start_at = max(now, origin_next.get(origin, now))
            origin_next[origin] = start_at + polite_gap
            wait_for = start_at - now
        if wait_for > 0:
            time.sleep(wait_for)

    def crawl_one(url: str) -> dict:
        _polite_wait((urlsplit(url).hostname or "").lower())
        try:
            row = run_tour(url, profile, settings, out_dir, robots_cache,
                           state.get(url))
        except Exception as exc:
            row = {"url": url, "status": FETCH_FAIL, "error": f"{type(exc).__name__}"}
        return row

    with output.open("a", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        if new_file:
            writer.writeheader()
        stop = threading.Event()
        drain = _map_ordered(crawl_one, todo, workers, stop)
        try:
            for position, outcome in drain:
                url = todo[position]
                index = position + 1
                log.info("tour %d/%d %s", index, len(todo), url)
                if isinstance(outcome, BaseException):
                    raise outcome
                row = outcome
                if "_state_entry" in row:
                    state[url] = row.pop("_state_entry")
                if row.get("detail_file"):
                    detail_paths.append(row["detail_file"])
                writer.writerow({k: row.get(k, "") for k in CSV_COLUMNS})
                handle.flush()
                if index % 10 == 0:
                    _save_state(state_path, state)
                if row.get("status") in (FETCH_FAIL, BLOCKED):
                    fails += 1
                    if fails >= max_fails:
                        log.error("failure budget exhausted (%d)", fails)
                        stop.set()
                        drain.close()
                        _save_state(state_path, state)
                        return 1
                else:
                    fails = 0
        except BaseException:
            stop.set()
            drain.close()
            _save_state(state_path, state)
            raise
    _save_state(state_path, state)
    _write_quality(settings, profile, detail_paths)
    log.info("batch done: wrote %s", output)
    return 0


def _prime_robots_cache(urls: list[str], settings: dict, robots_cache: dict) -> None:
    """Fetch robots.txt once per origin up front; workers only read the cache."""
    fetcher = make_fetcher(settings)
    for url in urls:
        origin = (urlsplit(url).hostname or "").lower()
        site_base = f"{urlsplit(url).scheme}://{origin}"
        if site_base not in robots_cache:
            robots_cache[site_base] = fetch_robots(fetcher, site_base, origin)


def _load_dotenv() -> None:
    try:
        text = Path(".env").read_text(encoding="utf-8")
    except OSError:
        return
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip("'\"")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="tour-crawl", description="Crawl tour data by source profile.")
    parser.add_argument("url", nargs="?", help="single tour URL")
    parser.add_argument("--profile", "-p", default=None,
                        help="source profile name (default: all profiles, or inferred from URL)")
    parser.add_argument("--batch", nargs="?", const="", default=None, metavar="CSV",
                        help="crawl URLs from a CSV file with a url column "
                             "(default: <output.dir>/<source>/discovered.csv)")
    parser.add_argument("--sitemap", action="store_true", help="enumerate profile sitemaps instead")
    parser.add_argument("--discover", action="store_true",
                        help="enumerate via the profile discovery block (search_pages or sitemap)")
    parser.add_argument("--limit", type=int, default=0, help="max tours (0 = all)")
    parser.add_argument("--since", default="", help="only sitemap urls with lastmod >= YYYY[-MM[-DD]]")
    parser.add_argument("--output", "-o", type=Path, default=None, help="CSV output path")
    parser.add_argument("--out-dir", type=Path, default=None, help="JSON detail directory")
    parser.add_argument("--no-browser", action="store_true", help="skip browser flow")
    parser.add_argument("--migrate", action="store_true", help="apply SQL migrations to the tour database and exit")
    parser.add_argument("--publish", nargs="?", const="", default=None, metavar="DIR",
                        help="publish detail JSONs to the tour database "
                             "(default DIR: <output.dir>/tours)")
    return parser.parse_args(argv)


def _migrations_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "migrations"


def tour_db_url() -> str:
    _load_dotenv()
    url = os.getenv("SUPABASE_TOUR_DB_URL")
    if not url:
        raise RuntimeError("SUPABASE_TOUR_DB_URL is required; set it in .env")
    return url


def migrate_db(url: str | None = None) -> int:
    """Apply pending SQL migrations once each; returns the count applied."""
    import psycopg
    from psycopg import sql

    applied = 0
    with psycopg.connect(url or tour_db_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"
            )
            for path in sorted(_migrations_dir().glob("*.sql")):
                cursor.execute("SELECT 1 FROM schema_migrations WHERE version = %s", (path.name,))
                if cursor.fetchone():
                    continue
                # Trusted input: version-controlled migration files, not user data.
                cursor.execute(sql.SQL(path.read_text(encoding="utf-8")))  # pyright: ignore[reportArgumentType]
                cursor.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (path.name,))
                applied += 1
                log.info("applied migration %s", path.name)
        connection.commit()
    return applied


def _int_or_none(value: object) -> int | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    if not isinstance(value, (int, float, str)):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _key(*parts: object) -> str:
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False).encode("utf-8")).hexdigest()


def _field_meta(record: dict, record_raw: dict, missing: list,
                tour_url: str, observed_at: str,
                checks: dict | None = None) -> dict:
    """Per-field wrapper for the contract: flat columns stay for filtering,
    this JSON keeps {status, raw_value, evidence[]} so UI/audit can trace."""
    missing_set = set(missing or [])
    meta: dict = {}
    for field, value in record.items():
        if field == "offers":
            continue
        empty = value in (None, "", [], {})
        check = checks.get(field, {}) if isinstance(checks, dict) else {}
        check_status = check.get("status", "") if isinstance(check, dict) else ""
        if check_status == "not_observed" or (empty and not check_status):
            status = "not_observed"
        elif field in missing_set or check_status in {"failed", "unverified"}:
            status = "partial"
        else:
            status = "observed"
        raw = record_raw.get(field, "") if isinstance(record_raw, dict) else ""
        if isinstance(raw, str) and len(raw) > 500:
            raw = raw[:500]
        meta[str(field)] = {
            "status": status,
            "check_status": check_status,
            "check_reason": check.get("reason", "") if isinstance(check, dict) else "",
            "source_coordinate": check.get("source", {}) if isinstance(check, dict) else {},
            "raw_value": raw,
            "evidence": [{
                "source_url": tour_url,
                "observed_at": observed_at,
                "extraction_method": "profile_dsl",
                "verification_status": "provider_claimed",
            }],
        }
    return meta


def publish_snapshot(out_dir: str | Path, profile_name: str,
                     url: str | None = None) -> dict[str, int]:
    """Upsert detail JSONs into providers/tours/offers. Returns row counts."""
    import psycopg

    profile = load_profile(profile_name)
    origin = profile.get("origin", "")
    counts = {"tours": 0, "offers": 0, "skipped": 0}
    with psycopg.connect(url or tour_db_url()) as connection:
        with connection.cursor() as cursor:
            provider_key = _key("provider", origin)
            cursor.execute(
                """INSERT INTO providers (source_key, display_name, website, observed_at)
                   VALUES (%s, %s, %s, NOW())
                   ON CONFLICT (source_key) DO UPDATE SET observed_at = NOW()
                   RETURNING id""",
                (provider_key, profile_name, f"https://{origin}"),
            )
            row = cursor.fetchone()
            provider_id = row[0] if row else None
            if provider_id is None:
                cursor.execute("SELECT id FROM providers WHERE source_key = %s", (provider_key,))
                selected = cursor.fetchone()
                if selected is None:
                    raise RuntimeError(f"provider row missing for {provider_key}")
                provider_id = selected[0]
            for index, path in enumerate(sorted(Path(out_dir).glob("tour_*.json")), 1):
                try:
                    detail = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    counts["skipped"] += 1
                    continue
                record = detail.get("record") or {}
                if not isinstance(record, dict) or not detail.get("url"):
                    counts["skipped"] += 1
                    continue
                tour_url = detail["url"]
                tour_key = _key("tour", tour_url)
                observed = detail.get("fetched_at", "")
                record_raw = detail.get("record_raw") if isinstance(detail.get("record_raw"), dict) else {}
                record_missing = detail.get("record_missing") or []
                field_meta = _field_meta(record, record_raw, record_missing, tour_url, observed,
                                         detail.get("record_field_checks"))
                cursor.execute(
                    """INSERT INTO tours (record_key, provider_id, url, observed_at,
                           tour_name, departure_city, destinations, route, transport,
                           accommodation, duration_days, duration_nights, price, currency,
                           price_type, departure_pattern, itinerary, inclusions, exclusions,
                           cancellation_policy, surcharges, child_policy,
                           verification_status, source_url, evidence, field_meta)
                       VALUES (%s, %s, %s, %s,
                           %s, %s, %s, %s, %s,
                           %s, %s, %s, %s, %s,
                           %s, %s, %s, %s, %s,
                           %s, %s, %s,
                           'provider_claimed', %s, %s, %s)
                       ON CONFLICT (record_key) DO UPDATE SET
                           observed_at = EXCLUDED.observed_at, tour_name = EXCLUDED.tour_name,
                           departure_city = EXCLUDED.departure_city, destinations = EXCLUDED.destinations,
                           route = EXCLUDED.route, transport = EXCLUDED.transport,
                           accommodation = EXCLUDED.accommodation, duration_days = EXCLUDED.duration_days,
                           duration_nights = EXCLUDED.duration_nights, price = EXCLUDED.price,
                           currency = EXCLUDED.currency, price_type = EXCLUDED.price_type,
                           departure_pattern = EXCLUDED.departure_pattern, itinerary = EXCLUDED.itinerary,
                           inclusions = EXCLUDED.inclusions, exclusions = EXCLUDED.exclusions,
                           cancellation_policy = EXCLUDED.cancellation_policy, surcharges = EXCLUDED.surcharges,
                           child_policy = EXCLUDED.child_policy, evidence = EXCLUDED.evidence,
                           field_meta = EXCLUDED.field_meta,
                           updated_at = NOW()
                       RETURNING id""",
                    (tour_key, provider_id, tour_url, detail.get("fetched_at"),
                     str(record.get("tour_name", ""))[:500], str(record.get("departure_city", ""))[:200],
                     json.dumps(record.get("destinations") or []),
                     json.dumps(record.get("route") or []),
                     str(record.get("transport", ""))[:20] or "",
                     str(record.get("accommodation", ""))[:50],
                     _int_or_none(record.get("duration_days")), _int_or_none(record.get("duration_nights")),
                     _int_or_none(record.get("price")), str(record.get("currency", "VND"))[:10],
                     str(record.get("price_type", ""))[:20] or "",
                     str(record.get("departure_pattern", ""))[:500],
                     str(record.get("itinerary", "")), str(record.get("inclusions", "")),
                     str(record.get("exclusions", "")), str(record.get("cancellation_policy", "")),
                     str(record.get("surcharges", "")), str(record.get("child_policy", "")),
                     tour_url,
                     json.dumps({"record_evidence": detail.get("record_evidence", ""),
                                 "record_missing": detail.get("record_missing", []),
                                 "record_field_checks": detail.get("record_field_checks", {}),
                                 "observed_at": detail.get("fetched_at", "")}),
                     json.dumps(field_meta, ensure_ascii=False)),
                )
                fetched = cursor.fetchone()
                tour_id = fetched[0] if fetched else None
                if tour_id is None:
                    cursor.execute("SELECT id FROM tours WHERE record_key = %s", (tour_key,))
                    selected = cursor.fetchone()
                    if selected is None:
                        raise RuntimeError(f"tour row missing for {tour_key}")
                    tour_id = selected[0]
                counts["tours"] += 1
                offers = record.get("offers") or []
                if not isinstance(offers, list):
                    offers = []
                seen_keys = []
                for offer in offers:
                    if not isinstance(offer, dict):
                        continue
                    date = str(offer.get("departure_date", "")) or None
                    price = _int_or_none(offer.get("price"))
                    offer_key = _key("offer", tour_key, date, price)
                    seen_keys.append(offer_key)
                    cursor.execute(
                        """INSERT INTO offers (record_key, tour_id, departure_date, price,
                               availability, tour_code, price_by_age, single_supplement,
                               flights, pickup_point, hotel_location, conditions,
                               observed_at, evidence, field_meta)
                           VALUES (%s, %s, %s, %s,
                               %s, %s, %s, %s,
                               %s, %s, %s, %s,
                               %s, %s, %s)
                           ON CONFLICT (record_key) DO UPDATE SET
                               price = EXCLUDED.price, availability = EXCLUDED.availability,
                               observed_at = EXCLUDED.observed_at, evidence = EXCLUDED.evidence,
                               field_meta = EXCLUDED.field_meta,
                               updated_at = NOW()""",
                        (offer_key, tour_id, date, price,
                         str(offer.get("availability", "unknown"))[:20] or "unknown",
                         str(offer.get("tour_code", ""))[:100],
                         json.dumps(offer.get("price_by_age")) if offer.get("price_by_age") is not None else None,
                         _int_or_none(offer.get("single_supplement")),
                         json.dumps(offer.get("flights")) if offer.get("flights") is not None else None,
                         str(offer.get("pickup_point", ""))[:500], str(offer.get("hotel_location", ""))[:500],
                         str(offer.get("conditions", ""))[:2000],
                         detail.get("fetched_at"),
                         json.dumps({"observed_at": detail.get("fetched_at", "")}),
                         json.dumps({"source_url": tour_url, "observed_at": observed,
                                     "verification_status": "provider_claimed"}, ensure_ascii=False)),
                    )
                    counts["offers"] += 1
                if seen_keys:
                    cursor.execute("DELETE FROM offers WHERE tour_id = %s AND NOT (record_key = ANY(%s))",
                                   (tour_id, seen_keys))
                if index % 25 == 0:
                    log.info("publish %d tours (%d offers)", counts["tours"], counts["offers"])
        connection.commit()
    return counts


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdout()
    args = _parse_args(argv)
    _load_dotenv()
    os.environ.setdefault("LOG_LEVEL", "INFO")

    if args.migrate:
        print(f"migrations applied={migrate_db()}")
        return 0

    try:
        settings = load_settings()
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"Invalid config: {exc}", file=sys.stderr)
        return 2

    if args.profile:
        targets = [args.profile]
    elif args.url:
        try:
            targets = [infer_profile_for_url(args.url)]
        except ValueError as exc:
            print(f"Invalid config: {exc}", file=sys.stderr)
            return 2
    else:
        try:
            targets = list_profiles()
        except (ValueError, OSError) as exc:
            print(f"Invalid config: {exc}", file=sys.stderr)
            return 2
    if not targets:
        print("No profiles in configs/profiles/; survey a source first.", file=sys.stderr)
        return 2
    if len(targets) > 1 and (args.output or args.out_dir):
        print("--output/--out-dir need a single --profile; rerun per profile.", file=sys.stderr)
        return 2
    if len(targets) > 1 and args.batch is not None and args.batch != "" and args.publish is not None:
        print("--batch <csv> needs a single --profile; rerun per profile.", file=sys.stderr)
        return 2
    if len(targets) > 1 and args.publish not in (None, ""):
        print("--publish <dir> needs a single --profile; rerun per profile.", file=sys.stderr)
        return 2

    worst = 0
    for name in targets:
        if len(targets) > 1:
            print(f"=== ingest: {name} ===", flush=True)
        try:
            profile = load_profile(name)
        except (ValueError, RuntimeError, OSError) as exc:
            print(f"Invalid config: {exc}", file=sys.stderr)
            return 2
        code = _run_profile(args, settings, profile, name)
        if code != 0:
            print(f"ingest {name} exit {code}", file=sys.stderr)
            worst = worst or code
    return worst


def list_profiles(profiles_dir: str | Path | None = None) -> list[str]:
    """All profile names in scope order (default when --profile is omitted)."""
    from .extract import DEFAULT_PROFILES, _resolve

    root = Path(profiles_dir) if profiles_dir is not None else _resolve(DEFAULT_PROFILES)
    if not root.is_dir():
        raise ValueError(f"profiles dir not found: {root}")
    return sorted(path.stem for path in root.glob("*.yaml"))


def infer_profile_for_url(url: str, profiles_dir: str | Path | None = None) -> str:
    """Profile whose origin matches a single tour URL (www-tolerant)."""
    from .extract import load_profile

    host = (urlsplit(url).hostname or "").lower()
    host = host[4:] if host.startswith("www.") else host
    if not host:
        raise ValueError(f"not an absolute URL: {url}")
    hits = []
    for name in list_profiles(profiles_dir):
        try:
            origin = str(load_profile(name, profiles_dir).get("origin", "")).lower()
        except (ValueError, RuntimeError, OSError):
            continue
        origin = origin[4:] if origin.startswith("www.") else origin
        if origin and host == origin:
            hits.append(name)
    if len(hits) != 1:
        raise ValueError(f"url {url!r} must match exactly one profile (found {hits})")
    return hits[0]


def _run_profile(args: argparse.Namespace, settings: dict, profile: dict, name: str) -> int:
    source = str(profile.get("name") or name)
    if args.no_browser:
        profile = {**profile, "flows": [flow for flow in profile.get("flows", []) if "browser" not in flow]}

    if args.publish is not None:
        publish_dir = (Path(args.publish) if args.publish
                       else _source_dir(settings, source) / "tours")
        counts = publish_snapshot(publish_dir, name)
        print(f"published={counts}")
        return 0

    if args.batch is not None:
        batch_path = (Path(args.batch) if args.batch
                      else _source_dir(settings, source) / "discovered.csv")
        if not batch_path.exists():
            print(f"No batch file: {batch_path} not found; run --discover first or pass --batch <csv>.",
                  file=sys.stderr)
            return 2
        with batch_path.open(encoding="utf-8-sig") as handle:
            urls = [row["url"] for row in csv.DictReader(handle) if row.get("url")]
    elif args.sitemap:
        fetcher = make_fetcher(settings)
        urls = sitemap_urls(fetcher, profile.get("sitemaps", []), profile.get("tour_url_patterns", []),
                              min_lastmod=args.since,
                              attempts=int(settings.get("sitemap", {}).get("attempts", 2)))
        print(f"sitemap urls: {len(urls)}")
    elif args.discover:
        fetcher = make_fetcher(settings)
        batch_cfg = settings.get("batch", {})
        list_path = (args.output or
                     (_source_dir(settings, source) / "discovered.csv"))
        _save_discovered([], list_path)
        handed = 0

        def on_page(page: int, fresh: list[str], _path: Path = list_path) -> None:
            """Append each page's fresh slugs immediately; a killed run keeps them."""
            nonlocal handed
            if fresh:
                with _path.open("a", encoding="utf-8-sig", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=["url"])
                    for url in fresh:
                        writer.writerow({"url": url})
                        handed += 1
            if page % 10 == 0:
                log.info("search pages: %d slugs saved", handed)

        urls = discover_urls(fetcher, profile, profile.get("tour_url_patterns", []),
                             min_lastmod=args.since,
                             attempts=int(settings.get("sitemap", {}).get("attempts", 2)),
                             workers=max(1, int(batch_cfg.get("workers", 4))),
                             limit=args.limit,
                             on_page=on_page,
                             fetcher_factory=lambda: make_fetcher(settings))
        if handed == 0 and urls:
            capped = urls[: args.limit] if args.limit > 0 else urls
            _save_discovered(capped, list_path)
            urls = capped
        print(f"discovered urls: {len(urls)}")
        print(f"discovered list: {list_path}")
        return 0
    elif args.url:
        urls = [args.url]
    else:
        print("Provide a URL, --batch, or --sitemap.", file=sys.stderr)
        return 2
    if args.limit > 0:
        urls = urls[: args.limit]

    out_dir = args.out_dir or (_source_dir(settings, source) / "tours")
    if len(urls) == 1 and args.batch is None and not args.sitemap:
        try:
            row = run_tour(urls[0], profile, settings, out_dir)
        except Exception as exc:
            print(f"Tour failed: {type(exc).__name__}", file=sys.stderr)
            return 1
        print(f"status={row['status']} title={row.get('title', '')[:80]} "
              f"departures={row.get('departures', 0)} error={row.get('error', '')}")
        return 0 if row["status"] not in (BLOCKED, FETCH_FAIL) else 1

    output = args.output or (_source_dir(settings, source) / "tours.csv")
    out_dir = args.out_dir or (_source_dir(settings, source) / "tours")
    return run_batch(urls, profile, settings, output, out_dir)
