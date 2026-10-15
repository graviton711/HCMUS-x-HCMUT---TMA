"""Code-first parsing of countable soft metrics from catalog text.

Covers what does not need LLM judgment: activity mentions, explicit route
legs and full-refund cutoffs. Every returned value carries the verbatim
substring it came from; no match means (0/None, []) and the metric stays
unknown. LLM facts, when present, always take precedence over parsed values.
"""

from __future__ import annotations

import re

_DAY_MARKER = re.compile(r"ngày\s*\d+\s*:", re.IGNORECASE)
_ARROW = re.compile(r"→|->")
_REFUND_SENTENCE = re.compile(r"[^.;]+100[^.;]*", re.IGNORECASE)
_REFUND_DAYS = re.compile(r"(\d+)\s*ngày", re.IGNORECASE)


def count_activities(itinerary: str) -> tuple[int, list[str]]:
    """Split itinerary into day blocks, then into comma/semicolon segments."""
    if not itinerary or not itinerary.strip():
        return 0, []
    blocks = _DAY_MARKER.split(itinerary)
    blocks = [block for block in blocks if block.strip()] or [itinerary]
    seen: dict[str, str] = {}
    for block in blocks:
        for segment in re.split(r"[,;\n·]", block):
            text = segment.strip().strip("-–— ").strip()
            if not text:
                continue
            key = text.casefold()
            seen.setdefault(key, text)
    quotes = list(seen.values())
    return len(quotes), quotes


def count_legs(itinerary: str) -> tuple[int, list[str]]:
    """Count explicit route arrows in itinerary text. No arrows, no legs."""
    if not itinerary:
        return 0, []
    quotes = [line.strip() for line in itinerary.split("\n") if _ARROW.search(line)]
    if not quotes and _ARROW.search(itinerary):
        quotes = [itinerary.strip()]
    arrows = sum(len(_ARROW.findall(quote)) for quote in quotes)
    return arrows, quotes


def full_refund_cutoff(cancellation_policy: str) -> tuple[int | None, str | None]:
    """Days before departure for a 100% refund, from the policy sentence."""
    if not cancellation_policy:
        return None, None
    for match in _REFUND_SENTENCE.finditer(cancellation_policy):
        sentence = match.group(0).strip()
        lowered = sentence.casefold()
        if "hoàn" not in lowered and "hoan" not in lowered:
            continue
        days = _REFUND_DAYS.search(sentence)
        if days:
            return int(days.group(1)), sentence
    return None, None
