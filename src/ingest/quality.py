"""Evidence gate: junk filtering plus verbatim validation. Fail loud, never invent."""

from __future__ import annotations

import re

OK, BLOCKED, FETCH_FAIL, PARSE_FAIL = "ok", "blocked", "fetch_fail", "parse_fail"

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I
)


def visible_len(value: object) -> int:
    """Visible-text characters of a value (HTML tags don't count)."""
    if not isinstance(value, str):
        return 0
    return len(re.sub(r"\s+", " ", re.sub(r"<[^>]{1,500}>", " ", value)).strip())


def is_junk_field(key: str, value: object, presentation: set, keep: re.Pattern,
                  min_visible: int = 40) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        if not value.strip():
            return True
        if UUID_RE.match(value.strip()):
            return True
        if key.casefold() in presentation:
            return True
        if visible_len(value) >= min_visible:
            return False
        return not keep.search(key)
    if isinstance(value, bool):
        return not keep.search(key)
    if isinstance(value, (int, float)):
        return not keep.search(key)
    return isinstance(value, (dict, list)) and not value


def compile_keep(patterns: list) -> re.Pattern:
    """Keep-patterns always case-insensitive (keys are camelCase)."""
    return re.compile("|".join(patterns or [r"(?!)"]), re.I)


def filter_dep(dep: dict, presentation: set, keep: re.Pattern, min_visible: int = 40) -> dict:
    return {k: v for k, v in dep.items() if not is_junk_field(k, v, presentation, keep, min_visible)}


def dedupe_departures(departures: list) -> tuple[list, dict]:
    """Hoist values identical across all departures to tour level."""
    if not departures:
        return departures, {}
    shared: dict = {}
    for key in set(departures[0].keys()):
        values = [dep.get(key) for dep in departures]
        if all(v == values[0] and v not in (None, "") for v in values):
            shared[key] = values[0]
    if not shared:
        return departures, {}
    return [{k: v for k, v in dep.items() if k not in shared} for dep in departures], shared


def extract_notes(payloads: list, pattern: str, min_visible: int = 40) -> dict:
    """Notes subtrees keyed by semantic key pattern (generic, never URLs)."""
    note_pat = re.compile(pattern, re.I) if pattern else None
    notes: dict = {}

    def walk(node) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if (
                    isinstance(key, str)
                    and note_pat is not None
                    and note_pat.search(key)
                    and visible_len(value) >= min_visible
                    and key not in notes
                ):
                    notes[key] = value
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    for payload in payloads:
        walk(payload)
    return notes


def normalize(text: str) -> str:
    return re.sub(r"\W+", " ", text.casefold()).strip()


def departure_evidence(dep: dict, context: str) -> str:
    """Spot-check one departure: key decision values verbatim in context.

    Returns verified (all present), partial (some present), or unverified.
    Generic: checks whatever decision fields the entry carries, no fixed schema.
    """
    context_norm = normalize(context)
    checks = []
    for name in ("tourCode", "salePrice", "price", "departureDate", "meetingPlace"):
        value = dep.get(name)
        if value is None or value == "":
            continue
        checks.append(normalize(str(value)) in context_norm)
    if not checks:
        return "unverified"
    if all(checks):
        return "verified"
    return "partial" if any(checks) else "unverified"
