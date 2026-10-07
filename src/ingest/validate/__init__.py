"""Evidence validation and error taxonomy. Fail loud, never invent."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

OK, BLOCKED, FETCH_FAIL, PARSE_FAIL = "ok", "blocked", "fetch_fail", "parse_fail"


@dataclass(slots=True)
class EvidenceReport:
    fields: dict[str, dict[str, str | None]]
    populated: str
    evidence_match: str
    dropped: list[str] = field(default_factory=list)


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


def _fuzzy_ok(quote: str, context_norm: str, threshold: float = 0.7) -> bool:
    tokens = [token for token in normalize(quote).split() if len(token) > 2]
    if not tokens:
        return False
    hits = sum(1 for token in tokens if token in context_norm)
    return hits / len(tokens) >= threshold


def validate_fields(payload: dict, field_names: list[str], context: str,
                    strict: set, fuzzy_threshold: float = 0.7,
                    max_value_chars: int = 400) -> EvidenceReport:
    """Null any field whose evidence is missing/stitched; report metrics."""
    context_norm = normalize(context)
    fields: dict[str, dict[str, str | None]] = {}
    dropped: list[str] = []
    for name in field_names:
        entry = payload.get(name)
        value = entry.get("value") if isinstance(entry, dict) else None
        quote = entry.get("evidence_quote") if isinstance(entry, dict) else None
        if not isinstance(value, str) or not value.strip():
            fields[name] = {"value": None, "evidence_quote": None}
            continue
        value = value.strip()[:max_value_chars]
        if not isinstance(quote, str) or not quote.strip():
            dropped.append(name)
            fields[name] = {"value": None, "evidence_quote": None}
            continue
        if name in strict:
            ok = normalize(quote) in context_norm
        else:
            ok = normalize(quote) in context_norm or _fuzzy_ok(quote, context_norm, fuzzy_threshold)
        if ok:
            fields[name] = {"value": value, "evidence_quote": quote.strip()}
        else:
            dropped.append(name)
            fields[name] = {"value": None, "evidence_quote": None}
    nonnull = sum(1 for item in fields.values() if item["value"] is not None)
    matched = nonnull - len(dropped)
    return EvidenceReport(
        fields=fields,
        populated=f"{nonnull}/{len(field_names)}",
        evidence_match=f"{matched}/{nonnull}" if nonnull else "0/0",
        dropped=dropped,
    )
