"""Strict profile-DSL field extraction (mechanical, no per-site heuristics).

Ported from the retired scripts runner into the main engine so static pages
follow the same path as everything else: coordinates declared in YAML,
values copied verbatim, cleaning only through reviewed `clean` expressions.
Profiles are reviewed artifacts; `clean` runs in a restricted namespace
(val, re, json, html) and nothing else.
"""

from __future__ import annotations

import html as _html
import json as _json
import re as _re
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

_EVAL_NAMES = {"val": None, "re": _re, "json": _json, "html": _html}


def apply_clean(rule: dict, val: object) -> object:
    """Run the profile's `clean` expression, falling back to `transform`."""
    if val is None:
        return None
    if code := rule.get("clean"):
        return eval(code, dict(_EVAL_NAMES, val=val))  # noqa: S307 - reviewed profiles only
    tr = rule.get("transform")
    if tr == "int":
        return int(_re.sub(r"\D", "", m.group(0))) if (m := _re.search(r"\d[\d.,]*", str(val))) else None
    if tr == "regex" and rule.get("pattern"):
        return m.group(1).strip() if (m := _re.search(rule["pattern"], str(val))) else None
    if tr == "split":
        return [s.strip() for s in _re.split(rule.get("delimiter", r"\s*[-\u2013]\s*"), str(val)) if s.strip()]
    return [str(val).strip()] if tr == "single_list" else (val if isinstance(val, (int, float, list, dict)) else str(val).strip())


def extract_field(soup: BeautifulSoup, json_ld: list, rule: dict) -> object:
    """One field from json_ld / css / label_sibling / section coordinates."""
    if not rule or rule.get("status") == "not_observed":
        return None
    val = None
    if (src := rule.get("source")) == "json_ld":
        for item in json_ld:
            if not rule.get("entity") or rule["entity"] in str(item.get("@type", "")):
                curr: Any = item
                for p in rule.get("path", "").split("."):
                    curr = curr.get(p) if isinstance(curr, dict) else None
                if curr is not None:
                    val = curr
                    break
    elif src == "css" and (el := soup.select_one(rule.get("selector", ""))):
        val = el.get_text(" ", strip=True) if rule.get("attr", "text") == "text" else el.get(rule["attr"])
    elif src == "label_sibling" and (tag := soup.find(string=_re.compile(_re.escape(rule.get("label", ""))))):
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
    return apply_clean(rule, val)


def extract_api_field(rule: dict, row: dict, fetch_json: Callable[[str], object]) -> object:
    """GET a public same-origin JSON endpoint declared in the profile.

    `{placeholders}` fill from fields extracted earlier. Origin check lives
    in the caller's fetch_json; failures mean not_observed, never guesses.
    """
    try:
        url = str(rule.get("url", "")).format(**{k: v for k, v in row.items() if isinstance(v, (str, int))})
    except (KeyError, IndexError, ValueError):
        return None
    try:
        data = fetch_json(url)
    except (OSError, ValueError):
        return None
    val = data
    if rule.get("path"):
        curr: Any = data
        for part in str(rule["path"]).split("."):
            curr = curr.get(part) if isinstance(curr, dict) else None
        val = curr
    if val is None:
        return None
    return apply_clean(rule, val)


def crawl_fields(html: str, profile: dict, fetch_json: Callable[[str], object] | None = None) -> dict:
    """Full canonical row from one page: static fields first, api fields after."""
    from .blocks import parse_json_ld

    soup = BeautifulSoup(html, "html.parser")
    json_ld = parse_json_ld(html)
    row: dict[str, object] = {}
    deferred: dict[str, dict] = {}
    for field, rule in (profile.get("fields") or {}).items():
        if rule and rule.get("source") == "api":
            deferred[str(field)] = rule
            continue
        v = extract_field(soup, json_ld, rule or {})
        row[str(field)] = v if v is not None else ""
    if fetch_json is not None:
        for field, rule in deferred.items():
            v = extract_api_field(rule, row, fetch_json)
            row[field] = v if v is not None else ""
    else:
        for field in deferred:
            row[field] = ""
    return row


def main(argv: list[str] | None = None) -> int:
    """Self-test entry: files (or URLs) + profile -> JSONL. Used by site surveys."""
    import argparse
    from pathlib import Path

    import yaml

    parser = argparse.ArgumentParser(prog="ingest-dsl", description=__doc__.splitlines()[0])
    parser.add_argument("targets", nargs="+")
    parser.add_argument("--profile", required=True)
    parser.add_argument("-o", "--output", default="tours.jsonl")
    args = parser.parse_args(argv)
    profile = yaml.safe_load(Path(args.profile).read_text(encoding="utf-8"))
    rows = []
    fetcher = None
    for target in args.targets:
        if target.startswith(("http://", "https://")):
            from .fetch import SafeFetcher

            fetcher = fetcher or SafeFetcher()
            result = fetcher.fetch(target)
            if result.error or result.status_code != 200:
                raise SystemExit(f"fetch failed {target}: {result.error or result.status_code}")
            html_text = result.body.decode("utf-8", errors="replace")
        else:
            html_text = Path(target).read_text(encoding="utf-8", errors="replace")
        rows.append(crawl_fields(html_text, profile))
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    import json as _json_mod

    out.write_text("\n".join(_json_mod.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    print(f"OK: wrote {len(rows)} tours to {out}")
    return 0


if __name__ == "__main__":
    from shared.runtime import run_cli

    raise SystemExit(run_cli(main))


def same_origin_getter(page_url: str, fetcher) -> Callable[[str], object]:
    """fetch_json callback that only allows same-origin GETs through the SafeFetcher."""
    origin = (urlsplit(page_url).hostname or "").lower()

    def fetch_json(url: str) -> object:
        if (urlsplit(url).hostname or "").lower() != origin:
            raise OSError(f"cross-origin api not allowed: {url}")
        result = fetcher.fetch(url, origin)
        if result.error or result.status_code != 200:
            raise OSError(result.error or f"HTTP {result.status_code}")
        return _json.loads(result.body.decode("utf-8", errors="replace"))

    return fetch_json
