"""Evidence gate: junk filtering plus verbatim validation. Fail loud, never invent."""

from __future__ import annotations

import re
from collections.abc import Sequence

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


def fallback_fields(record: dict) -> list[str]:
    """Record fields that fell back to empty (no usable value extracted).

    A rising fallback share per field across runs is the cheapest layout-drift
    signal: the site changed faster than any re-survey schedule.
    """
    return sorted(key for key, value in record.items()
                  if value in (None, "", [], {}))


def summarize_details(details: list[dict], fill_fields: Sequence[str]) -> dict:
    """Run stats from detail JSONs: tour count, mean price, fill rates."""
    prices: list[float] = []
    fills: dict[str, int] = {}
    fallback_total = 0
    for detail in details:
        record = detail.get("record") if isinstance(detail, dict) else None
        if not isinstance(record, dict):
            continue
        price = record.get("price")
        if isinstance(price, bool):
            pass
        elif isinstance(price, (int, float)) and price > 0:
            prices.append(float(price))
        for field in fill_fields:
            value = record.get(field)
            fills[field] = fills.get(field, 0) + (0 if value in (None, "", [], {}) else 1)
        fallback_total += len(fallback_fields(record))
    tours = len(details)
    return {
        "tours": tours,
        "price_mean": (sum(prices) / len(prices)) if prices else None,
        "fill": {f: (fills.get(f, 0) / tours if tours else 0.0) for f in fill_fields},
        "fallback_total": fallback_total,
    }


def compare_quality(current: dict, previous: dict, cfg: dict) -> list[str]:
    """Warn-only drift signals of the current run against the previous good one."""
    warnings: list[str] = []
    min_ratio = float(cfg.get("min_tours_ratio", 0.8))
    max_shift = float(cfg.get("max_price_shift", 0.3))
    min_fill = float(cfg.get("min_fill_rate", 0.85))
    prev_tours = int(previous.get("tours", 0) or 0)
    cur_tours = int(current.get("tours", 0) or 0)
    if prev_tours > 0 and cur_tours / prev_tours < min_ratio:
        warnings.append(f"tours {cur_tours} below {min_ratio:.2f} of previous {prev_tours}")
    prev_mean = previous.get("price_mean")
    cur_mean = current.get("price_mean")
    if prev_mean and cur_mean and prev_mean > 0:
        shift = abs(cur_mean - prev_mean) / prev_mean
        if shift > max_shift:
            warnings.append(f"mean price shifted {shift:.2f} "
                            f"({prev_mean:.0f} -> {cur_mean:.0f})")
    for field, rate in (current.get("fill") or {}).items():
        if rate < min_fill:
            warnings.append(f"fill {field} {rate:.2f} below {min_fill:.2f}")
    return warnings


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


def _leaves(value: object) -> list[str]:
    """Scalar leaves of a record value for verbatim checking."""
    if value is None:
        return []
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [re.sub(r"\D", "", str(value))]
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_leaves(item))
        return out
    if isinstance(value, dict):
        out = []
        for item in value.values():
            out.extend(_leaves(item))
        return out
    return []


def verify_record(record: dict, raw: dict, html: str) -> tuple[str, list[str]]:
    """Verbatim evidence check for one static DSL record.

    Evidence is always checked against RAW pre-clean values, never against
    cleaned output: a normalized enum (`mixed`) or a reformatted structure
    can never appear verbatim, so checking cleaned values would fail honest
    records. A field with an empty raw but a non-empty value was synthesized
    without a source and counts as missing. Structural keys such as the
    source url are never checked. No fuzzy matching.
    """
    context_norm = normalize(html)
    context_digits = re.sub(r"\D", "", html)
    missing: list[str] = []
    checked = 0
    for key, value in record.items():
        if key == "url":
            continue
        raw_leaves = [leaf for leaf in _leaves(raw.get(key)) if normalize(leaf)]
        if not raw_leaves:
            if _leaves(value):
                missing.append(key)
            continue
        checked += len(raw_leaves)
        ok = True
        for leaf in raw_leaves:
            if leaf.isdigit():
                if leaf not in context_digits:
                    ok = False
                    break
            elif normalize(leaf) not in context_norm:
                ok = False
                break
        if not ok:
            missing.append(key)
    if checked == 0:
        return "unverified", missing
    if not missing:
        return "verified", missing
    return "partial", missing


OFFER_KEY_MAP = {
    "departureDate": "departure_date",
    "salePrice": "price",
    "tourCode": "tour_code",
    "meetingPlace": "pickup_point",
    "hotelName": "hotel_location",
}

OFFER_SORT_KEYS = ("departure_date", "price")


def normalize_offer(dep: dict) -> dict:
    """Map browser camelCase to the contract snake_case; unknown keys pass through."""
    if not isinstance(dep, dict):
        return dep
    out: dict = {}
    for key, value in dep.items():
        out[OFFER_KEY_MAP.get(key, key)] = value
    return out


def sort_offers(offers: list) -> list:
    """Deterministic Runner ordering so profiles never sort in `clean` (no lambda)."""
    if not isinstance(offers, list):
        return offers
    try:
        return sorted(offers, key=lambda d: (
            str(d.get("departure_date", "")) if isinstance(d, dict) else "",
            d.get("price", 0) if isinstance(d, dict) and isinstance(d.get("price"), (int, float)) else 0,
        ))
    except TypeError:
        return offers


def departure_evidence(dep: dict, context: str) -> str:
    """Spot-check one departure: key decision values verbatim in context.

    Returns verified (all present), partial (some present), or unverified.
    Generic: checks whatever decision fields the entry carries, no fixed schema.
    """
    context_norm = normalize(context)
    checks = []
    for name in ("tour_code", "tourCode", "price", "salePrice",
                 "departure_date", "departureDate", "pickup_point", "meetingPlace"):
        value = dep.get(name)
        if value is None or value == "":
            continue
        checks.append(normalize(str(value)) in context_norm)
    if not checks:
        return "unverified"
    if all(checks):
        return "verified"
    return "partial" if any(checks) else "unverified"
