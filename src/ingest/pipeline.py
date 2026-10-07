"""Batch orchestration: resume, budgets, exit codes. Single team entry point.

No parsing here; argv handling also lives here so `python -m ingest`
needs no extra layer.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from shared import get_logger

from . import extract, quality
from .extract import load_profile, load_settings
from .fetch import BrowserSession, RateLimiter, SafeFetcher, fetch_robots
from .quality import BLOCKED, FETCH_FAIL, OK, PARSE_FAIL, departure_evidence

log = get_logger("pipeline")

CSV_COLUMNS = ["url", "observed_at", "profile", "status", "title",
               "departures", "verified", "notes_keys", "error"]


def sitemap_urls(fetcher: SafeFetcher, sitemaps: list[str],
                 patterns: list[str]) -> list[str]:
    found: set[str] = set()
    for sitemap in sitemaps:
        result = fetcher.fetch(sitemap)
        if result.status_code != 200 or result.error:
            log.warning("sitemap failed %s %s", sitemap, result.error or result.status_code)
            continue
        try:
            root = ET.fromstring(result.body)
        except ET.ParseError:
            continue
        for node in root.iter():
            if node.tag.rsplit("}", 1)[-1] == "loc" and node.text:
                url = node.text.strip()
                if any(pat in url for pat in patterns):
                    found.add(url)
    return sorted(found)


def _read_done(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open(encoding="utf-8-sig") as handle:
        return {row["url"] for row in csv.DictReader(handle) if row.get("url")}


def run_tour(url: str, profile: dict, settings: dict, out_dir: Path) -> dict:
    """One tour end-to-end. Returns a status-tagged result dict."""
    fetch_cfg = settings.get("fetch", {})
    limiter = RateLimiter(float(fetch_cfg.get("delay_s", 1.0)))
    fetcher = SafeFetcher(
        timeout=float(fetch_cfg.get("timeout_s", 20)),
        max_bytes=int(fetch_cfg.get("max_bytes", 2_000_000)),
        user_agent=str(fetch_cfg.get("user_agent", "MLAITourSourceAuditor/0.1")),
        limiter=limiter,
    )
    origin = (urlsplit(url).hostname or "").lower()
    site_base = f"{urlsplit(url).scheme}://{origin}"
    observed = datetime.now(UTC).isoformat(timespec="seconds")

    robots = fetch_robots(fetcher, site_base, origin)
    if robots is not None and not robots.can_fetch(fetcher.user_agent, url):
        return {"url": url, "status": BLOCKED, "error": "robots.txt disallows URL"}

    page = fetcher.fetch(url, origin)
    if page.error or page.status_code != 200:
        return {"url": url, "status": FETCH_FAIL,
                "error": page.error or f"HTTP {page.status_code}"}
    html = page.body.decode("utf-8", errors="replace")

    clean_cfg = settings.get("clean", {})
    merged: dict = {
        "url": page.url,
        "fetched_at_utc": observed,
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
        merged["record"] = extract.crawl_fields(
            html, profile, extract.same_origin_getter(page.url, fetcher))

    browser_error = ""
    rendered_text = ""
    if "browser" in profile.get("flows", []) or "combo_api_browser" in profile.get("flows", []):
        try:
            with BrowserSession(user_agent=fetcher.user_agent) as session:
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
                "fetched_at_utc": observed,
            }
        except Exception as exc:
            browser_error = f"{type(exc).__name__}: {exc}"[:200]
            log.warning("browser flow failed %s %s", url, browser_error)

    out_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", page.url.lower()).strip("-")[:80]
    detail_path = out_dir / f"tour_{slug[:60]}.json"
    detail_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    departures = (merged["departure_schedule"] or {}).get("departures", [])
    notes = (merged["departure_schedule"] or {}).get("notes", {})
    verified = sum(1 for dep in departures if dep.get("evidence") == "verified")
    status = OK if (merged["title"] or departures) else PARSE_FAIL
    error = "" if status == OK else (browser_error or "empty result")
    return {"url": page.url, "observed_at": observed, "profile": merged["profile"],
            "status": status, "title": merged["title"], "departures": len(departures),
            "verified": verified, "notes_keys": ",".join(sorted(notes.keys())), "error": error,
            "detail_file": str(detail_path)}


def run_batch(urls: list[str], profile: dict, settings: dict, output: Path,
              out_dir: Path | None = None) -> int:
    """Append one CSV row per tour; resume by URL. Returns process exit code."""
    batch_cfg = settings.get("batch", {})
    max_fails = int(batch_cfg.get("max_consecutive_failures", 10))
    gap = float(batch_cfg.get("delay_s", 1.0))
    if out_dir is None:
        out_dir = Path(settings.get("output", {}).get("dir", ".local")) / "tours"
    done = _read_done(output)
    todo = [url for url in urls if url not in done]
    log.info("batch: %d urls (%d skipped)", len(todo), len(urls) - len(todo))

    output.parent.mkdir(parents=True, exist_ok=True)
    new_file = not output.exists()
    fails = 0
    with output.open("a", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        if new_file:
            writer.writeheader()
        for index, url in enumerate(todo, 1):
            log.info("tour %d/%d %s", index, len(todo), url)
            try:
                row = run_tour(url, profile, settings, out_dir)
            except Exception as exc:
                row = {"url": url, "status": FETCH_FAIL, "error": f"{type(exc).__name__}"}
            writer.writerow({k: row.get(k, "") for k in CSV_COLUMNS})
            handle.flush()
            if row.get("status") in (FETCH_FAIL, BLOCKED):
                fails += 1
                if fails >= max_fails:
                    log.error("failure budget exhausted (%d)", fails)
                    return 1
            else:
                fails = 0
            if index < len(todo):
                time.sleep(gap)
    log.info("batch done: wrote %s", output)
    return 0


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
    parser.add_argument("--profile", "-p", default="vietravel", help="source profile name")
    parser.add_argument("--batch", type=Path, help="CSV file with a url column")
    parser.add_argument("--sitemap", action="store_true", help="enumerate profile sitemaps instead")
    parser.add_argument("--limit", type=int, default=0, help="max tours (0 = all)")
    parser.add_argument("--output", "-o", type=Path, default=None, help="CSV output path")
    parser.add_argument("--out-dir", type=Path, default=None, help="JSON detail directory")
    parser.add_argument("--no-browser", action="store_true", help="skip browser flow")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = _parse_args(argv)
    _load_dotenv()
    os.environ.setdefault("LOG_LEVEL", "INFO")

    try:
        settings = load_settings()
        profile = load_profile(args.profile)
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"Invalid config: {exc}", file=sys.stderr)
        return 2
    if args.no_browser:
        profile = {**profile, "flows": [flow for flow in profile.get("flows", []) if "browser" not in flow]}

    if args.batch:
        with args.batch.open(encoding="utf-8-sig") as handle:
            urls = [row["url"] for row in csv.DictReader(handle) if row.get("url")]
    elif args.sitemap:
        fetch_cfg = settings.get("fetch", {})
        fetcher = SafeFetcher(
            timeout=float(fetch_cfg.get("timeout_s", 20)),
            max_bytes=int(fetch_cfg.get("max_bytes", 2_000_000)),
            user_agent=str(fetch_cfg.get("user_agent", "MLAITourSourceAuditor/0.1")),
            limiter=RateLimiter(float(fetch_cfg.get("delay_s", 1.0))),
        )
        urls = sitemap_urls(fetcher, profile.get("sitemaps", []), profile.get("tour_url_patterns", []))
        print(f"sitemap urls: {len(urls)}")
    elif args.url:
        urls = [args.url]
    else:
        print("Provide a URL, --batch, or --sitemap.", file=sys.stderr)
        return 2
    if args.limit > 0:
        urls = urls[: args.limit]

    out_dir = args.out_dir or (Path(settings.get("output", {}).get("dir", ".local")) / "tours")
    if len(urls) == 1 and not args.batch and not args.sitemap:
        try:
            row = run_tour(urls[0], profile, settings, out_dir)
        except Exception as exc:
            print(f"Tour failed: {type(exc).__name__}", file=sys.stderr)
            return 1
        print(f"status={row['status']} title={row.get('title', '')[:80]} "
              f"departures={row.get('departures', 0)} error={row.get('error', '')}")
        return 0 if row["status"] not in (BLOCKED, FETCH_FAIL) else 1

    output = args.output or (Path(settings.get("output", {}).get("dir", ".local")) / "tours.csv")
    out_dir = args.out_dir or (Path(settings.get("output", {}).get("dir", ".local")) / "tours")
    return run_batch(urls, profile, settings, output, out_dir)
