"""Read layer: profile coordinates in, verbatim records out. No guessing.

Strict field extraction from agent-authored profiles, raw block
readers, and the profile/settings loader. Nothing here interprets content;
cleaning happens only through reviewed `clean` expressions in profiles.
"""

from __future__ import annotations

import html as _html
import json as _json
import re as _re
from collections.abc import Callable
from html.parser import HTMLParser
from pathlib import Path
from types import ModuleType
from typing import Any, Literal, overload
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from shared import get_logger

from .fetch import SafeFetcher

log = get_logger("extract")

DEFAULT_SETTINGS = Path("configs/settings.yaml")
DEFAULT_PROFILES = Path("configs/profiles")


def _resolve(path: Path) -> Path:
    """Find configs in a checkout or an installed deployment.

    Order: explicit path > package-relative configs/ (repo checkout) >
    current-directory configs/. Deployment ships configs/ alongside the
    code; it is data, not code.
    """
    candidates = [path]
    candidates.append(Path(__file__).resolve().parents[2] / path)
    candidates.append(Path.cwd() / path)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _yaml() -> ModuleType:
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("This package requires PyYAML (see pyproject dependencies).") from exc
    return yaml


def load_settings(path: str | Path | None = None) -> dict:
    yaml = _yaml()
    target = _resolve(Path(path) if path is not None else DEFAULT_SETTINGS)
    with target.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Settings must be a mapping: {target}")
    return data


def load_profile(name: str, profiles_dir: str | Path | None = None) -> dict:
    yaml = _yaml()
    if profiles_dir is not None:
        target = Path(profiles_dir) / f"{name}.yaml"
    else:
        target = _resolve(DEFAULT_PROFILES / f"{name}.yaml")
    if not target.exists():
        raise ValueError(f"Unknown profile: {name} ({target} not found)")
    with target.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict) or not data.get("origin") or not data.get("flows"):
        raise ValueError(f"Profile needs origin + flows: {target}")
    data["name"] = name
    return data


_LD_JSON_RE = _re.compile(
    r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', _re.S | _re.I
)


def parse_json_ld(html: str) -> list:
    """Every parseable JSON-LD node, in document order."""
    blocks = []
    for match in _LD_JSON_RE.finditer(html):
        try:
            data = _json.loads(match.group(1))
        except (_json.JSONDecodeError, ValueError):
            continue
        blocks.extend(data if isinstance(data, list) else [data])
    return blocks


class _TextCollector(HTMLParser):
    """Collects text chunks; ignores CSS visibility like a scraper should."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.chunks: list[str] = []

    def handle_data(self, data):
        text = data.strip()
        if text:
            self.chunks.append(text)


def _strip_scripts(html: str) -> str:
    return _re.sub(r"<(script|style|noscript)[\s>].*?</\1>", " ", html, flags=_re.S | _re.I)


def page_prose(html: str) -> str:
    """All visible text, unfiltered. Callers decide what counts as evidence."""
    parser = _TextCollector()
    parser.feed(_strip_scripts(html))
    return "\n".join(parser.chunks)


def script_texts(html: str) -> str:
    """Raw contents of script tags (structured blobs live here, not in prose)."""
    return "\n".join(
        match.group(1) for match in
        _re.finditer(r"<script[^>]*>(.*?)</script>", html, _re.S | _re.I))


def page_text_only(html: str) -> str:
    """All text incl. CSS-hidden nodes (parser ignores visibility)."""
    parser = _TextCollector()
    parser.feed(_strip_scripts(html))
    return _re.sub(r"[ \t]+", " ", "\n".join(parser.chunks))


def walk_departures(node, found: list) -> None:
    """Collect every dict carrying a departureDate, containers preserved."""
    if isinstance(node, dict):
        if isinstance(node.get("departureDate"), str):
            found.append(node)
        for value in node.values():
            walk_departures(value, found)
    elif isinstance(node, list):
        for value in node:
            walk_departures(value, found)


def iso_to_dmy(iso: object) -> str:
    """2026-10-25T08:00:00 -> 25/10/2026 (empty when unparseable)."""
    match = _re.match(r"(\d{4})-(\d{2})-(\d{2})", str(iso or ""))
    if not match:
        return ""
    return f"{match.group(3)}/{match.group(2)}/{match.group(1)}"


_EVAL_NAMES = {"val": None, "re": _re, "json": _json, "html": _html}


def research(pattern: str, text: object, group: int | str = 1, flags: int = 0) -> str:
    """Safe regex extract for profile `clean` code: "" when nothing matches.

    Never raises on bad input; a bad pattern itself also yields "".
    """
    try:
        match = _re.search(pattern, str(text), flags)
    except _re.error:
        return ""
    if not match:
        return ""
    try:
        hit = match.group(group)
    except (IndexError, AttributeError):
        return ""
    if hit is None:
        return ""
    return hit.strip() if isinstance(hit, str) else str(hit)


def refindall(pattern: str, text: object, flags: int = 0) -> list:
    """Safe regex find-all for profile `clean` code: [] when nothing matches."""
    try:
        return _re.findall(pattern, str(text), flags)
    except _re.error:
        return []


_EVAL_NAMES.update({"research": research, "refindall": refindall})


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


def extract_api_field(rule: dict, row: dict, fetch_json: Callable[[str], object],
                      raw_out: dict | None = None) -> object:
    """GET a public same-origin JSON endpoint declared in the profile.

    `{placeholders}` fill from fields extracted earlier. Origin check lives
    in the caller's fetch_json; failures mean not_observed, never guesses.
    When raw_out is given, the raw response text is stored under "response".
    """
    try:
        url = str(rule.get("url", "")).format(**{k: v for k, v in row.items() if isinstance(v, (str, int))})
    except (KeyError, IndexError, ValueError):
        return None
    try:
        data = fetch_json(url)
    except (OSError, ValueError):
        return None
    if raw_out is not None:
        import json as _json_mod

        try:
            raw_out["response"] = _json_mod.dumps(data, ensure_ascii=False)
        except (TypeError, ValueError):
            raw_out["response"] = str(data)
    val = data
    if rule.get("path"):
        curr: Any = data
        for part in str(rule["path"]).split("."):
            curr = curr.get(part) if isinstance(curr, dict) else None
        val = curr
    if val is None:
        return None
    return apply_clean(rule, val)


@overload
def crawl_fields(html: str, profile: dict, fetch_json: Callable[[str], object] | None = None,
                 *, include_raw: Literal[False] = False) -> dict[str, Any]: ...


@overload
def crawl_fields(html: str, profile: dict, fetch_json: Callable[[str], object] | None = None,
                 *, include_raw: Literal[True]) -> tuple[dict[str, Any], dict[str, Any]]: ...


def crawl_fields(html: str, profile: dict, fetch_json: Callable[[str], object] | None = None,
                 include_raw: bool = False) -> dict[str, Any] | tuple[dict[str, Any], dict[str, Any]]:
    """Full canonical row from one page: static fields first, api fields after.

    With include_raw=True returns (row, raw) where raw holds pre-clean values;
    evidence must always be checked against raw, never against cleaned output.
    """
    soup = BeautifulSoup(html, "html.parser")
    json_ld = parse_json_ld(html)
    row: dict[str, object] = {}
    raw: dict[str, object] = {}
    deferred: dict[str, dict] = {}
    for field, rule in (profile.get("fields") or {}).items():
        if rule and rule.get("source") == "api":
            deferred[str(field)] = rule
            continue
        try:
            v = extract_field(soup, json_ld, rule or {})
            r = _raw_field(soup, json_ld, rule or {})
        except Exception as exc:
            log.warning("field %s failed (%s: %s); left empty",
                        field, type(exc).__name__, str(exc)[:120])
            v, r = "", ""
        row[str(field)] = v if v is not None else ""
        raw[str(field)] = r
    if fetch_json is not None:
        for field, rule in deferred.items():
            holder: dict = {}
            try:
                v = extract_api_field(rule, row, fetch_json, holder)
            except Exception as exc:
                log.warning("api field %s failed (%s: %s); left empty",
                            field, type(exc).__name__, str(exc)[:120])
                v = ""
            row[field] = v if v is not None else ""
            raw[field] = holder.get("response", "")
    else:
        for field in deferred:
            row[field] = ""
            raw[field] = ""
    offers = row.get("offers")
    if isinstance(offers, list):
        from .quality import normalize_offer, sort_offers

        row["offers"] = sort_offers([normalize_offer(d) for d in offers])
    if include_raw:
        return row, raw
    return row


def _raw_field(soup: BeautifulSoup, json_ld: list, rule: dict) -> object:
    """The value before `clean` runs; empty string when the source is absent."""
    if not rule or rule.get("status") == "not_observed":
        return ""
    rule = dict(rule)
    rule.pop("clean", None)
    rule.pop("transform", None)
    v = extract_field(soup, json_ld, rule)
    return v if v is not None else ""


def same_origin_getter(page_url: str, fetcher: SafeFetcher) -> Callable[[str], object]:
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


def main(argv: list[str] | None = None) -> int:
    """Self-test entry: files (or URLs) + profile -> JSONL. Used by site surveys."""
    import argparse
    from pathlib import Path

    import yaml

    parser = argparse.ArgumentParser(prog="ingest-extract", description="Strict profile-DSL field extraction.")
    parser.add_argument("targets", nargs="+")
    parser.add_argument("--profile", required=True)
    parser.add_argument("-o", "--output", default="tours.jsonl")
    args = parser.parse_args(argv)
    profile = yaml.safe_load(Path(args.profile).read_text(encoding="utf-8"))
    rows = []
    fetcher = None
    for target in args.targets:
        if target.startswith(("http://", "https://")):
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
    out.write_text("\n".join(_json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    print(f"OK: wrote {len(rows)} tours to {out}")
    return 0


if __name__ == "__main__":
    from shared.runtime import run_cli

    raise SystemExit(run_cli(main))


__all__ = [
    "apply_clean",
    "crawl_fields",
    "extract_api_field",
    "extract_field",
    "iso_to_dmy",
    "load_profile",
    "load_settings",
    "page_prose",
    "page_text_only",
    "parse_json_ld",
    "same_origin_getter",
    "walk_departures",
]
