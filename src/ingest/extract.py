"""Read layer: profile coordinates in, verbatim records out. No guessing.

Strict field extraction from agent-authored profiles, raw block
readers, and the profile/settings loader. Nothing here interprets content;
cleaning happens only through reviewed `clean` expressions in profiles.
"""

from __future__ import annotations

import hashlib
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

    `{placeholders}` fill from fields extracted earlier. Origin/robots checks
    live in the caller's fetch_json; fetch failures are not source absence.
    When raw_out is given, the raw response text is stored under "response".
    """
    if rule.get("status") == "not_observed":
        if raw_out is not None:
            raw_out["state"] = "declared_not_observed"
        return None
    if raw_out is not None:
        raw_out["state"] = "api_fetch_failed"
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
    if raw_out is not None:
        raw_out["value"] = val
        raw_out["state"] = "source_empty" if not _has_value(val) else "extracted"
    if not _has_value(val):
        return None
    cleaned = apply_clean(rule, val)
    if raw_out is not None:
        raw_out["state"] = "extracted" if _has_value(cleaned) else "clean_empty"
    return cleaned


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
    row, raw, _states = crawl_fields_detailed(html, profile, fetch_json)
    if include_raw:
        return row, raw
    return row


def _has_value(value: object) -> bool:
    return value is not None and value != "" and value != [] and value != {}


def crawl_fields_detailed(html: str, profile: dict,
                          fetch_json: Callable[[str], object] | None = None
                          ) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    """Return cleaned row, exact pre-clean values, and extractor outcomes.

    `source_empty` means the declared coordinate resolved but contained no
    value; `selector_missing`/`extraction_error` mean the extractor failed to
    locate or process it. These states are intentionally kept distinct.
    """
    soup = BeautifulSoup(html, "html.parser")
    json_ld = parse_json_ld(html)
    row: dict[str, object] = {}
    raw: dict[str, object] = {}
    states: dict[str, str] = {}
    deferred: dict[str, dict] = {}
    for field, rule in (profile.get("fields") or {}).items():
        rule = rule or {}
        if rule.get("status") == "not_observed":
            row[str(field)] = ""
            raw[str(field)] = ""
            states[str(field)] = "declared_not_observed"
            continue
        if rule.get("source") == "api":
            deferred[str(field)] = rule
            continue
        try:
            raw_rule = dict(rule)
            raw_rule.pop("clean", None)
            raw_rule.pop("transform", None)
            r = extract_field(soup, json_ld, raw_rule)
            if r is None:
                v = ""
                state = ("source_empty" if _source_locator_exists(soup, json_ld, raw_rule)
                         else "selector_missing")
            elif not _has_value(r):
                v = ""
                state = "source_empty"
            else:
                try:
                    v = apply_clean(rule, r)
                    state = "extracted" if _has_value(v) else "clean_empty"
                except Exception as exc:
                    log.warning("field %s clean failed (%s: %s); left empty",
                                field, type(exc).__name__, str(exc)[:120])
                    v, state = "", "clean_error"
        except Exception as exc:
            log.warning("field %s failed (%s: %s); left empty",
                        field, type(exc).__name__, str(exc)[:120])
            v, r, state = "", "", "extraction_error"
        row[str(field)] = v if v is not None else ""
        raw[str(field)] = r if r is not None else ""
        states[str(field)] = state
    if fetch_json is not None:
        for field, rule in deferred.items():
            holder: dict = {}
            try:
                v = extract_api_field(rule, row, fetch_json, holder)
            except Exception as exc:
                log.warning("api field %s failed (%s: %s); left empty",
                            field, type(exc).__name__, str(exc)[:120])
                holder["state"] = "clean_error"
                v = ""
            row[field] = v if v is not None else ""
            raw[field] = holder.get("value", "")
            states[field] = str(holder.get("state", "api_fetch_failed"))
    else:
        for field in deferred:
            row[field] = ""
            raw[field] = ""
            states[field] = "api_fetch_unavailable"
    offers = row.get("offers")
    if isinstance(offers, list):
        from .quality import normalize_offer, sort_offers

        row["offers"] = sort_offers([normalize_offer(d) for d in offers])
    return row, raw, states


def _raw_field(soup: BeautifulSoup, json_ld: list, rule: dict) -> object:
    """The value before `clean` runs; empty string when the source is absent."""
    if not rule or rule.get("status") == "not_observed":
        return ""
    rule = dict(rule)
    rule.pop("clean", None)
    rule.pop("transform", None)
    v = extract_field(soup, json_ld, rule)
    return v if v is not None else ""


def _source_locator_exists(soup: BeautifulSoup, json_ld: list, rule: dict) -> bool:
    """Whether the declared anchor exists, even if its requested value is absent."""
    source = rule.get("source")
    if source == "css":
        return soup.select_one(rule.get("selector", "")) is not None
    if source == "json_ld":
        entity = rule.get("entity", "")
        return any(isinstance(item, dict) and
                   (not entity or entity in str(item.get("@type", "")))
                   for item in json_ld)
    if source == "label_sibling":
        return soup.find(string=_re.compile(_re.escape(rule.get("label", "")))) is not None
    if source == "section":
        return soup.find(lambda tag: tag.name in ("h1", "h2", "h3", "h4") and
                         rule.get("start_label", "") in tag.get_text()) is not None
    return False


def same_origin_getter(page_url: str, fetcher: SafeFetcher, robots=None) -> Callable[[str], object]:
    """Public, robots-allowed GETs through SafeFetcher at the exact page origin."""
    page_parts = urlsplit(page_url)
    origin = f"{page_parts.scheme}://{page_parts.netloc}"

    def origin_key(url: str) -> tuple[str, str, int]:
        parts = urlsplit(url)
        port = parts.port or (443 if parts.scheme == "https" else 80)
        return parts.scheme, (parts.hostname or "").lower(), port

    def fetch_json(url: str) -> object:
        if origin_key(url) != origin_key(origin):
            raise OSError(f"cross-origin api not allowed: {url}")
        if robots is None:
            raise OSError("robots.txt unavailable for API request")
        if not robots.can_fetch(fetcher.user_agent, url):
            raise OSError(f"robots.txt disallows API URL: {url}")
        result = fetcher.fetch(url, origin)
        if result.error or result.status_code != 200:
            raise OSError(result.error or f"HTTP {result.status_code}")
        return _json.loads(result.body.decode("utf-8", errors="replace"))

    return fetch_json


def main(argv: list[str] | None = None) -> int:
    """Extract files or verify every successful page in a survey manifest."""
    import argparse
    from pathlib import Path

    import yaml

    parser = argparse.ArgumentParser(prog="ingest-extract", description="Strict profile-DSL field extraction.")
    parser.add_argument("targets", nargs="*")
    parser.add_argument("--all", dest="all_dir", type=Path,
                        help="self-test all tour HTML files described by tour_pages.csv")
    parser.add_argument("--profile", required=True)
    parser.add_argument("-o", "--output", default="tours.jsonl")
    args = parser.parse_args(argv)
    if bool(args.targets) == bool(args.all_dir):
        parser.error("provide positional targets OR --all <raw-dir>")
    profile = yaml.safe_load(Path(args.profile).read_text(encoding="utf-8")) or {}
    if args.all_dir:
        return _self_test_all(args.all_dir, Path(args.output), profile)
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


def _cached_api_getter(page_url: str, fetcher: SafeFetcher, robots,
                      cache_dir: Path) -> Callable[[str], object]:
    """Same-origin robots-checked API GETs backed by a bounded disk cache."""
    page_parts = urlsplit(page_url)
    origin = f"{page_parts.scheme}://{page_parts.netloc}"
    safe_get = same_origin_getter(page_url, fetcher, robots)

    def get(api_url: str) -> object:
        parts = urlsplit(api_url)
        origin_parts = urlsplit(origin)
        api_port = parts.port or (443 if parts.scheme == "https" else 80)
        origin_port = origin_parts.port or (443 if origin_parts.scheme == "https" else 80)
        if (parts.scheme, (parts.hostname or "").lower(), api_port) != (
                origin_parts.scheme, (origin_parts.hostname or "").lower(), origin_port):
            raise OSError(f"cross-origin api not allowed: {api_url}")
        if robots is None or not robots.can_fetch(fetcher.user_agent, api_url):
            raise OSError(f"robots.txt unavailable or disallows API URL: {api_url}")
        cache_path = cache_dir / (hashlib.sha256(api_url.encode("utf-8")).hexdigest() + ".json")
        if cache_path.exists() and cache_path.stat().st_size <= 2_000_000:
            try:
                return _json.loads(cache_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                pass
        value = safe_get(api_url)
        serialized = _json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        if len(serialized.encode("utf-8")) > 2_000_000:
            raise OSError("API cache response exceeds 2 MB")
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(serialized, encoding="utf-8")
        return value

    return get


def _self_test_all(raw_dir: Path, output: Path, profile: dict) -> int:
    """Run per-field checks against the complete fetched-tour manifest."""
    import csv
    from collections import Counter
    from urllib.robotparser import RobotFileParser

    from .fetch import RateLimiter, SafeFetcher
    from .quality import verify_record_fields

    raw_dir = raw_dir.resolve()
    manifest = raw_dir / "tour_pages.csv"
    gaps: list[str] = []
    if not manifest.exists():
        gaps.append("coverage_unknown:tour_pages.csv is missing")
        entries = [{"index": str(i), "url": "", "file": path.name,
                    "status": "ok", "error": ""}
                   for i, path in enumerate(sorted(raw_dir.glob("tour-*.html")), 1)]
    else:
        with manifest.open(encoding="utf-8-sig", newline="") as handle:
            entries = list(csv.DictReader(handle))
    report_path = raw_dir / "survey_fetch_report.json"
    if not report_path.exists():
        gaps.append("coverage_unknown:survey_fetch_report.json is missing")
    else:
        try:
            fetch_report = _json.loads(report_path.read_text(encoding="utf-8"))
            gaps.extend(str(item) for item in fetch_report.get("gaps", []))
            if fetch_report.get("discovered_unique") != len(entries):
                gaps.append("coverage_count_mismatch:report_vs_manifest")
        except (OSError, ValueError, AttributeError):
            gaps.append("coverage_unknown:survey_fetch_report.json is invalid")
    urls_in_manifest = [str(entry.get("url", "")) for entry in entries]
    if len(set(urls_in_manifest)) != len(urls_in_manifest):
        gaps.append("duplicate_tour_urls_in_manifest")
    urls_path = raw_dir / "tour_urls.txt"
    if not urls_path.exists():
        gaps.append("coverage_unknown:tour_urls.txt is missing")
    else:
        listed_urls = [line.strip() for line in urls_path.read_text(encoding="utf-8").splitlines()
                       if line.strip()]
        if listed_urls != urls_in_manifest:
            gaps.append("coverage_mismatch:tour_urls_vs_manifest")
    if not entries:
        gaps.append("no_tours_in_manifest")

    rows: list[dict] = []
    field_status: dict[str, Counter] = {}
    failed_tours: list[str] = []
    api_rules = [rule for rule in (profile.get("fields") or {}).values()
                 if isinstance(rule, dict) and rule.get("source") == "api"]
    api_fetcher = (SafeFetcher(max_bytes=2_000_000, user_agent="MLAITourSourceAuditor/0.1",
                               limiter=RateLimiter(1.0), retries=2)
                   if api_rules else None)
    api_cache = raw_dir / "api-cache"
    robots_parser = None
    if api_rules:
        robots_file = raw_dir / "robots.txt"
        if robots_file.exists():
            robots_parser = RobotFileParser(robots_file.resolve().as_uri())
            robots_parser.parse(robots_file.read_text(encoding="utf-8", errors="replace").splitlines())
        else:
            gaps.append("api_gap:robots.txt snapshot is missing")

    for entry in entries:
        url = str(entry.get("url", ""))
        status = str(entry.get("status", ""))
        filename = str(entry.get("file", ""))
        if status not in {"ok", "cached"} or not filename:
            gaps.append(f"fetch_gap:{url or entry.get('index', '?')}:{entry.get('error', status)}")
            failed_tours.append(url or str(entry.get("index", "?")))
            continue
        path = (raw_dir / filename).resolve()
        if raw_dir not in path.parents or not path.is_file():
            gaps.append(f"missing_or_unsafe_file:{url or filename}")
            failed_tours.append(url or filename)
            continue
        try:
            html_text = path.read_text(encoding="utf-8", errors="replace")
            fetch_json: Callable[[str], object] | None = None
            if api_fetcher is not None:
                fetch_json = _cached_api_getter(url, api_fetcher, robots_parser, api_cache)

            record, record_raw, states = crawl_fields_detailed(html_text, profile, fetch_json)
            json_ld = parse_json_ld(html_text)
            verdict, missing, checks = verify_record_fields(
                record, record_raw, html_text, profile, states, json_ld)
        except Exception as exc:
            gaps.append(f"extract_failed:{url or filename}:{type(exc).__name__}:{exc}")
            failed_tours.append(url or filename)
            continue
        rows.append({"url": url, "source_file": filename, "record": record,
                     "record_raw": record_raw, "record_evidence": verdict,
                     "record_missing": missing, "record_field_checks": checks})
        if missing or verdict != "verified":
            failed_tours.append(url or filename)
        for name, check in checks.items():
            field_status.setdefault(name, Counter())[str(check.get("status", "unknown"))] += 1
            if check.get("reason") in {"api_fetch_failed", "api_fetch_unavailable"}:
                gaps.append(f"api_gap:{url}:{name}:{check.get('reason')}")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(_json.dumps(row, ensure_ascii=False) for row in rows)
                      + ("\n" if rows else ""), encoding="utf-8")
    summary = {
        "discovered": len(entries),
        "checked": len(rows),
        "failed_or_unverified_tours": list(dict.fromkeys(failed_tours)),
        "gaps": list(dict.fromkeys(gaps)),
        "fields": {name: dict(counts) for name, counts in sorted(field_status.items())},
        "jsonl": str(output),
    }
    summary_path = output.with_suffix(output.suffix + ".summary.json")
    summary_path.write_text(_json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
    print(_json.dumps(summary, ensure_ascii=False, indent=2))
    complete = len(rows) == len(entries) and not gaps and not failed_tours and bool(entries)
    return 0 if complete else 1


if __name__ == "__main__":
    from shared.runtime import run_cli

    raise SystemExit(run_cli(main))


__all__ = [
    "apply_clean",
    "crawl_fields",
    "crawl_fields_detailed",
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
