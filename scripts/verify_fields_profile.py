"""Offline verifier for an agent-produced `fields` profile (no network).

The site-survey agent writes profile.yaml in the new `fields` format
(source/path/context/normalize/gate). selftest.md claims PASS by applying
the rules "mentally". This script actually executes the JSON-LD rules
against the saved raw/tour-*.html and prints produced values so a human
can compare them with selftest.md.

Scope: only the deterministic `source: json_ld` rules are executed here.
Text-section rules (context/heading windows) are reported as SKIP until
the generic text engine exists, so this never pretends to verify more
than it does.

Usage:
    uv run python scripts/verify_fields_profile.py --source pys
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tourcrawl import blocks  # noqa: E402


def _iter_type(nodes):
    """Yield (node, @type-list) for every dict in the JSON-LD forest."""
    stack = list(nodes)
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            types = node.get("@type")
            types = [types] if isinstance(types, str) else (types or [])
            yield node, types
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)


def _dotted(node, path: str):
    """Resolve a dotted path (offers.price) through dicts; None if absent."""
    current = node
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def _type_hint(gate: str) -> str | None:
    """Extract a JSON-LD @type hint from a gate string, if any."""
    match = re.search(r"contains\s+(\w+)", gate or "", re.I)
    if match:
        return match.group(1)
    match = re.search(r"@type\s+(\w+)", gate or "", re.I)
    return match.group(1) if match else None


def run_json_ld_rule(html: str, rule: dict) -> object:
    """Best-effort execution of a json_ld field rule.

    Resolves `path` from every JSON-LD node in document order and returns
    the first non-empty hit. Note: a gate's @type mention (e.g. "@type Offer")
    describes a confirmation condition, NOT the node to resolve from — the
    owning entity (Product/TouristTrip) is usually the root that carries the
    path, so we must scan all nodes rather than filter by the gate type.
    """
    nodes = blocks.parse_json_ld(html)
    path = rule.get("path", "")
    for node, _types in _iter_type(nodes):
        value = _dotted(node, path)
        if value not in (None, "", [], {}):
            return value
    return None


HEADING_TAGS = ["h1", "h2", "h3"]


def text_section(html: str, label: str) -> str:
    """Text from a heading whose text matches `label` to the next heading.

    Used only to sanity-check text rules; not a full engine.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    wanted = [part.strip().casefold() for part in re.split(r"/|,", label) if part.strip()]
    for heading in soup.find_all(HEADING_TAGS):
        title = heading.get_text(" ", strip=True)
        if any(word and word in title.casefold() for word in wanted):
            chunks = []
            for sibling in heading.find_next_siblings():
                if sibling.name in HEADING_TAGS:
                    break
                text = sibling.get_text("\n", strip=True)
                if text:
                    chunks.append(text)
            return "\n".join(chunks)
    return ""


def load_profile(path: Path) -> dict:
    import yaml

    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Offline verify a fields-format profile.")
    parser.add_argument("--source", required=True, help="agent survey folder name, e.g. pys")
    parser.add_argument("--limit", type=int, default=0, help="max raw tour files (0 = all)")
    args = parser.parse_args(argv)

    survey = Path("artifacts/agent_surveys") / args.source
    profile = load_profile(survey / "profile.yaml")
    rules = profile.get("fields", {})
    raw_dir = survey / "raw"
    tours = sorted(raw_dir.glob("tour-*.html"))
    if args.limit > 0:
        tours = tours[: args.limit]

    print(f"source={args.source} rules={len(rules)} tours={len(tours)}")
    print(f"json_ld rules: {[k for k, v in rules.items() if v.get('source') == 'json_ld']}")
    print(f"text rules (SKIP, no engine): {[k for k, v in rules.items() if v.get('source') == 'text']}")
    print()

    for tour in tours:
        html = tour.read_text(encoding="utf-8", errors="replace")
        print(f"=== {tour.name} ===")
        for name, rule in rules.items():
            source = rule.get("source")
            if source == "json_ld":
                value = run_json_ld_rule(html, rule)
                shown = json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value
                status = "OK" if value not in (None, "", [], {}) else "NULL"
                print(f"  [{status:4}] {name:20} = {shown}")
            elif source == "text":
                label = (rule.get("context") or {}).get("label", "")
                section = text_section(html, label) if label else ""
                has = "found" if section else "MISSING"
                print(f"  [SKIP] {name:20} section[{label!r}] -> {has} ({len(section)} chars)")
            else:
                print(f"  [????] {name:20} unknown source {source!r}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
