"""Crawl tours driven by an agent-survey profile. Generic: no per-source code.

Reads artifacts/agent_surveys/<source>/profile.yaml, fetches tour URLs
from its sitemaps, extracts the 12 canonical fields via aliases
(JSON keys first, visible labels second), writes one CSV row per tour.

Usage:
    uv run python scripts/crawl_with_profile.py --source pys --limit 3
    uv run python scripts/crawl_with_profile.py --source pys --limit 3 --output artifacts/pys_tours.csv
"""

from __future__ import annotations

import argparse
import csv
import ipaddress
import json
import re
import socket
import sys
import time
import unicodedata
import urllib.robotparser
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, build_opener

FIELDS = ["tour_name", "tour_code", "duration", "price", "currency",
          "departure_city", "destination", "departure_dates", "itinerary",
          "inclusions", "exclusions", "cancellation_policy"]
EXTRA_COLUMNS = ["availability_status"]
TIMEOUT = 20
MAX_BYTES = 2_000_000
DELAY = 1.5
CELL_LIMIT = 800


def _nfc(text: str) -> str:
    """NFC-normalize: Vietnamese pages mix precomposed + combining marks."""
    return unicodedata.normalize("NFC", text)


def _public_host(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_global
    except ValueError:
        pass
    try:
        records = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError:
        return False
    addrs = []
    for record in records:
        try:
            addrs.append(ipaddress.ip_address(record[4][0]))
        except ValueError:
            continue
    return bool(addrs) and all(a.is_global for a in addrs)


def _get(url: str, origin: str, ua: str) -> bytes:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme not in {"http", "https"} or host != origin or not _public_host(host):
        raise ValueError(f"out of scope: {url}")
    req = Request(url, headers={"User-Agent": ua})
    with build_opener().open(req, timeout=TIMEOUT) as resp:
        body = resp.read(MAX_BYTES + 1)
        if resp.status != 200 or len(body) > MAX_BYTES:
            raise ValueError(f"fetch failed: status={resp.status}")
        return body


def _walk_json(node, found: dict) -> None:
    """Collect leaf string/number values keyed by dotted JSON path."""
    def walk(obj, path):
        if isinstance(obj, dict):
            for key, value in obj.items():
                walk(value, f"{path}.{key}" if path else str(key))
        elif isinstance(obj, list):
            for value in obj:
                walk(value, path)
        elif isinstance(obj, (str, int, float)) and path:
            found.setdefault(path, []).append(_nfc(str(obj)) if isinstance(obj, str) else obj)
    walk(node, "")


def _json_blobs(html: str) -> list:
    blobs = []
    for match in re.finditer(
            r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S | re.I):
        try:
            data = json.loads(match.group(1))
            blobs.extend(data if isinstance(data, list) else [data])
        except (ValueError, TypeError):
            continue
    return blobs


def _main_block(blobs: list, page_url: str):
    """Prefer the JSON-LD node describing this page (url match); else first
    Product/TouristTrip; else first block. Related-tour cards share the page
    but must not outrank the main entity."""
    norm_page = page_url.rstrip("/").lower()
    for blob in blobs:
        if isinstance(blob, dict) and str(blob.get("url", "")).rstrip("/").lower() == norm_page:
            return blob
    for blob in blobs:
        types = blob.get("@type") if isinstance(blob, dict) else None
        types = [types] if isinstance(types, str) else (types or [])
        if isinstance(blob, dict) and any(t in ("Product", "TouristTrip", "Tour") for t in types):
            return blob
    return blobs[0] if blobs else {}


def _visible_text(html: str) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "nav", "footer",
                     "aside", "form"]):
        tag.extract()
    for tag in soup.select('[role="tab"]'):
        tag.extract()
    return _nfc(soup.get_text("\n", strip=False))


def _from_aliases(aliases: list[str], flat_json: dict, text: str, stops: list[str] = ()):
    for raw_alias in aliases:
        alias = _nfc(raw_alias)
        if "." in alias or alias in ("name", "title", "description", "duration",
                                     "price", "priceCurrency", "category"):
            for path, values in flat_json.items():
                last = path.rsplit(".", 1)[-1]
                if last == alias or path == alias:
                    vals = [str(v).strip() for v in values if str(v).strip()]
                    if vals:
                        return vals
        else:
            best = ""
            start = 0
            while True:
                idx = text.find(alias, start)
                if idx < 0:
                    break
                snippet = re.sub(r"\s+", " ", text[idx:idx + 600]).strip()
                snippet = re.sub(r"^.*?" + re.escape(alias) + r"\s*[:\-]?\s*", "", snippet)
                cut = len(snippet)
                for stop in stops:
                    if stop != alias:
                        pos = snippet.find(stop)
                        if 40 < pos < cut:
                            cut = pos
                snippet = re.sub(r"\s+", " ", snippet[:cut]).strip()
                if len(snippet) > len(best):
                    best = snippet
                start = idx + len(alias)
            if best:
                return [best]
    return []


def _flatten(values) -> str:
    if isinstance(values, list):
        seen, out = set(), []
        for value in values:
            text = str(value).strip()
            if text and text not in seen:
                seen.add(text)
                out.append(text)
        joined = " | ".join(out)
    else:
        joined = str(values).strip() if values else ""
    if len(joined) <= CELL_LIMIT:
        return joined
    cut = joined.rfind(" ", 0, CELL_LIMIT)
    return joined[: cut if cut > 0 else CELL_LIMIT].rstrip()


def _itinerary_days(text: str) -> list[str]:
    """Day-by-day blocks win over the generic 'Lịch trình' label (generic
    Vietnamese travel pattern, not site-specific)."""
    marker = re.compile(r"NGÀY\s+0?\d+\s*[:\-–]", re.I)
    heads = list(marker.finditer(text))
    if len(heads) < 2:
        return []
    days = []
    for index, match in enumerate(heads):
        end = heads[index + 1].start() if index + 1 < len(heads) else len(text)
        body = re.sub(r"\s+", " ", text[match.start():end]).strip()
        if body:
            days.append(body)
    return days


def _explicit_dates(text: str) -> list[str]:
    """Concrete dates, only near schedule keywords (generic travel-domain gate).

    Bare regexes match ratings/prices/versions, so dates count only inside a
    window around khởi hành/lịch/departure markers.
    """
    full = r"\b([0-2]?\d|3[01])/(0?[1-9]|1[0-2])/(20\d{2}|\d{2})\b"
    compact = r"\b\d{1,2}(?:[.,]\d{1,2})+/(0?[1-9]|1[0-2])(?:/(?:20\d{2}|\d{2}))?\b"
    zones = []
    for marker in re.finditer(r"khởi hành|lịch|departure|schedule", text, re.I):
        zones.append((max(0, marker.start() - 400), marker.start() + 600))
    found = []
    for start, end in zones:
        window = text[start:end]
        for match in re.finditer(f"{full}|{compact}", window):
            token = match.group(0)
            if token not in found:
                found.append(token)
    return found


def _weekly_schedule(text: str) -> list[str]:
    """Weekly patterns like 'Thứ 6 hàng tuần' when no explicit date list exists."""
    found = []
    for match in re.finditer(
            r"Thứ\s*[2-8]\s*hàng\s*tuần|hàng tuần|khởi hành hàng tuần", text, re.I):
        snippet = re.sub(r"\s+", " ", text[match.start():match.end() + 80]).strip()
        snippet = re.sub(r"^\d+\.\s*", "", snippet)
        if snippet and snippet not in found:
            found.append(snippet)
    return found


def _availability(text: str) -> str:
    if re.search(r"hết lịch|hết chỗ|ế chỗ|cháy vé|sold.?out", text, re.I):
        return "sold_out"
    if re.search(r"\d{1,2}/\d{1,2}(/\d{2,4})?|Còn \d+ chỗ|khởi hành hàng tuần", text, re.I):
        return "available"
    return "unknown"


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    import yaml

    parser = argparse.ArgumentParser(description="Profile-driven tour crawl to CSV.")
    parser.add_argument("--source", required=True)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    profile = yaml.safe_load(open(f"artifacts/agent_surveys/{args.source}/profile.yaml",
                                  encoding="utf-8"))
    origin = urlsplit(profile["origin"]).hostname.lower()
    ua = "MLAITourSourceAuditor/0.1"
    robots = urllib.robotparser.RobotFileParser(f"https://{origin}/robots.txt")
    robots_body = _get(f"https://{origin}/robots.txt", origin, ua)
    robots.parse(robots_body.decode("utf-8", errors="replace").splitlines())

    urls: set[str] = set()
    for sitemap in profile.get("sitemaps", []):
        try:
            root = ET.fromstring(_get(sitemap, origin, ua))
        except ValueError as exc:
            print(f"sitemap skip: {exc}", file=sys.stderr)
            continue
        for node in root.iter():
            if node.tag.rsplit("}", 1)[-1] == "loc" and node.text:
                link = node.text.strip()
                pats = profile.get("tour_url_patterns", [])
                if any(p in link for p in pats) and robots.can_fetch(ua, link):
                    urls.add(link)
        time.sleep(DELAY)
    todo = sorted(urls)[: args.limit if args.limit > 0 else len(urls)]
    print(f"tour urls: {len(urls)}; crawling: {len(todo)}")

    output = args.output or Path(f"artifacts/{args.source}_tours.csv")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["url", "observed_at"] + FIELDS
                                + EXTRA_COLUMNS)
        writer.writeheader()
        for index, url in enumerate(todo, 1):
            row: dict = {"url": url,
                         "observed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
            try:
                if not robots.can_fetch(ua, url):
                    raise ValueError("blocked by robots.txt")
                html = _get(url, origin, ua).decode("utf-8", errors="replace")
                blobs = _json_blobs(html)
                main = _main_block(blobs, url)
                flat, rest = {}, {}
                _walk_json(main, flat)
                for blob in blobs:
                    if blob is not main:
                        _walk_json(blob, rest)
                text = _visible_text(html)
                alias_map = profile.get("aliases", {})
                stops = [_nfc(a) for names in alias_map.values() for a in names
                         if "." not in a]
                for field_name in FIELDS:
                    if field_name == "departure_dates":
                        vals = _explicit_dates(text) or _weekly_schedule(text)
                    else:
                        vals = _from_aliases(alias_map.get(field_name, []),
                                             flat, text, stops)
                        if not vals:
                            vals = _from_aliases(alias_map.get(field_name, []),
                                                 rest, text, stops)
                    if field_name == "itinerary":
                        days = _itinerary_days(text)
                        if days:
                            vals = days
                    if field_name == "departure_dates" and not vals:
                        vals = _from_aliases(alias_map.get(field_name, []),
                                             flat, text, stops)
                    row[field_name] = _flatten(vals)
                row["availability_status"] = _availability(text)
                if row["availability_status"] == "sold_out":
                    row["departure_dates"] = ""
            except ValueError as exc:
                row.update({f: "" for f in FIELDS + EXTRA_COLUMNS})
                print(f"[{index}/{len(todo)}] SKIP {url} ({exc})", file=sys.stderr)
            else:
                filled = sum(1 for f in FIELDS if row[f])
                print(f"[{index}/{len(todo)}] {filled}/{len(FIELDS)} {url[:80]}")
            writer.writerow(row)
            time.sleep(DELAY)
    print(f"saved={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
