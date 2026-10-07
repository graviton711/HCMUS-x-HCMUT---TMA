"""Category-based junk filtering, dedup, prose cleaning. No site specifics."""

from __future__ import annotations

import re

QUOTED_ITEM = re.compile(r'"([^"\\]{8,2000})"')
SLUG_RE = re.compile(r"^[a-z0-9\-/._]+$")
URLISH_RE = re.compile(r"://|^/(?:[A-Za-z0-9\-._~%/?#=&]+/?)+$|\.(aspx|html?|js|css|webp|png|jpe?g|svg|woff2?)$", re.I)
DATE_RE = re.compile(r"\d{2}/\d{2}/20\d{2}")
CODE_SIGNS = ("function(", "=>")
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I
)


def letters_ratio(text: str) -> float:
    letters = sum(1 for ch in text if ch.isalpha() or ch.isspace())
    return letters / max(1, len(text))


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


def clean_prose(prose: str, short_words: int = 6, short_run: int = 20,
                flight_short_run: int = 15) -> str:
    """Keep human prose, drop code and boilerplate (generic, no site keys)."""
    keep: list[str] = []
    run: list[str] = []
    shorts: list[str] = []

    def flush() -> None:
        keep.extend(run if len(run) < short_run else [])

    def flush_shorts() -> None:
        if len(shorts) < flight_short_run:
            for item in shorts:
                if item not in keep:
                    keep.append(item)
        shorts.clear()

    def feed_flight(line: str) -> None:
        for raw in QUOTED_ITEM.findall(line):
            text = re.sub(r"\s+", " ", raw).strip()
            if (
                len(text) < 8
                or letters_ratio(text) < 0.6
                or any(sign in text for sign in CODE_SIGNS)
                or URLISH_RE.search(text)
                or text in keep
            ):
                continue
            if len(text) >= 40 or DATE_RE.search(text):
                flush_shorts()
                keep.append(text)
            elif SLUG_RE.match(text):
                continue
            else:
                shorts.append(text)

    def is_code(line: str) -> bool:
        return letters_ratio(line) < 0.5 or any(sign in line for sign in CODE_SIGNS)

    for line in prose.splitlines():
        if "__next_f" in line or '["$"' in line:
            feed_flight(line)
            continue
        if is_code(line):
            flush()
            run = []
            continue
        if len(line.split()) <= short_words:
            run.append(line)
        else:
            flush()
            run = []
            keep.append(line)
    flush()
    flush_shorts()
    return "\n".join(keep)


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
