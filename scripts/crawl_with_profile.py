"""Crawl tour fields using declarative profile coordinates (mechanical, no per-site heuristics)."""
from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


def extract_field(soup: BeautifulSoup, json_ld: list, rule: dict) -> object:
    if not rule or rule.get("status") == "not_observed":
        return None
    val = None
    if (src := rule.get("source")) == "json_ld":
        for item in json_ld:
            if not rule.get("entity") or rule["entity"] in str(item.get("@type", "")):
                curr = item
                for p in rule.get("path", "").split("."):
                    curr = curr.get(p) if isinstance(curr, dict) else None
                if curr is not None:
                    val = curr
                    break
    elif src == "css" and (el := soup.select_one(rule.get("selector", ""))):
        val = el.get_text(" ", strip=True) if rule.get("attr", "text") == "text" else el.get(rule["attr"])
    elif src == "label_sibling" and (tag := soup.find(string=re.compile(re.escape(rule.get("label", ""))))):
        sib = tag.parent.find_next_sibling() if tag.parent else None
        val = sib.get_text(" ", strip=True) if sib else (tag.parent.get_text(" ", strip=True).replace(rule["label"], "").strip() if tag.parent else "")
    elif src == "section" and (start := soup.find(lambda t: t.name in ("h1", "h2", "h3", "h4") and rule.get("start_label", "") in t.get_text())):
        parts = []
        for s in start.find_all_next():
            if s.name in ("h1", "h2", "h3", "h4") and any(k in s.get_text() for k in rule.get("stop_labels", [])):
                break
            txt = s.get_text(" ", strip=True) if s.name in ("p", "li", "dt", "dd") else (s.string or "").strip()
            if txt:
                parts.append(txt)
        val = "\n".join(dict.fromkeys(parts))

    if val is None:
        return None
    if code := rule.get("clean"):
        return eval(code, {"val": val, "re": re, "json": json, "html": html})
    tr = rule.get("transform")
    if tr == "int":
        return int(re.sub(r"\D", "", m.group(0))) if (m := re.search(r"\d[\d.,]*", str(val))) else None
    if tr == "regex" and rule.get("pattern"):
        return m.group(1).strip() if (m := re.search(rule["pattern"], str(val))) else None
    if tr == "split":
        return [s.strip() for s in re.split(rule.get("delimiter", r"\s*[-–]\s*"), str(val)) if s.strip()]
    return [str(val).strip()] if tr == "single_list" else (val if isinstance(val, (int, float, list, dict)) else str(val).strip())

def fetch_html(target: str, render: bool) -> str:
    if not target.startswith(("http://", "https://")):
        return Path(target).read_text(encoding="utf-8", errors="replace")
    if render:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            page = p.chromium.launch(headless=True).new_page()
            page.goto(target, wait_until="networkidle", timeout=30000)
            return page.content()
    return urlopen(Request(target, headers={"User-Agent": "TourCrawler/1.0"}), timeout=20).read().decode("utf-8", errors="replace")

def _walk_path(data: object, path: str) -> object:
    curr: object = data
    for part in path.split("."):
        if not isinstance(curr, dict) or (curr := curr.get(part)) is None:
            return None
    return curr


def extract_api_field(rule: dict, row: dict[str, object]) -> object:
    """GET a public same-origin JSON endpoint declared in the profile.

    `{placeholders}` in `url` are filled from fields extracted earlier
    (e.g. {tour_code}); failures mean not_observed, never guesses.
    """
    try:
        url = str(rule.get("url", "")).format(
            **{k: v for k, v in row.items() if isinstance(v, (str, int))})
    except (KeyError, IndexError, ValueError):
        return None
    try:
        req = Request(url, headers={"User-Agent": "TourCrawler/1.0"})
        data = json.loads(urlopen(req, timeout=20).read().decode("utf-8", errors="replace"))
    except (OSError, ValueError):
        return None
    val = _walk_path(data, str(rule.get("path", ""))) if rule.get("path") else data
    if val is None:
        return None
    if code := rule.get("clean"):
        return eval(code, {"val": val, "re": re, "json": json, "html": html})
    return val


def crawl_tour(target: str, profile: dict) -> dict:
    render = bool(profile.get("render") or "browser" in profile.get("flows", []))
    soup = BeautifulSoup(fetch_html(target, render), "html.parser")
    json_ld = []
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            json_ld.extend(d if isinstance((d := json.loads(s.string or s.text)), list) else [d])
        except (ValueError, TypeError):
            continue
    row: dict[str, object] = {"url": target}
    deferred: dict[str, dict] = {}
    for field, rule in profile.get("fields", {}).items():
        if rule and rule.get("source") == "api":
            deferred[str(field)] = rule
            continue
        v = extract_field(soup, json_ld, rule)
        row[str(field)] = v if v is not None else ""
    for field, rule in deferred.items():
        v = extract_api_field(rule, row)
        row[field] = v if v is not None else ""
    return row

def main(argv=None) -> int:
    import yaml
    p = argparse.ArgumentParser()
    p.add_argument("url", nargs="+")
    p.add_argument("--profile", required=True)
    p.add_argument("-o", "--output", default="tours.jsonl")
    args = p.parse_args(argv)
    profile = yaml.safe_load(Path(args.profile).read_text(encoding="utf-8"))
    rows = [crawl_tour(u, profile) for u in args.url]
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    print(f"OK: wrote {len(rows)} tours to {out}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
