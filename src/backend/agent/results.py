"""Limits and parsers for tool results relayed through OpenCode JSON events."""

from __future__ import annotations

import json
from typing import Any

from backend.models import Comparison


def limit_comparison(comparison: Comparison, limit: int = 5) -> Comparison:
    selected_ranked = []
    seen: set[str] = set()
    for candidate in comparison.ranked:
        if candidate.tour_id in seen:
            continue
        if len(selected_ranked) >= limit:
            break
        selected_ranked.append(candidate)
        seen.add(candidate.tour_id)
    remaining = max(0, limit - len(seen))
    selected_near = []
    for candidate in comparison.near_miss:
        if candidate.tour_id in seen:
            continue
        if remaining == 0:
            break
        selected_near.append(candidate)
        seen.add(candidate.tour_id)
        remaining -= 1
    offer_ids = {candidate.offer_id for candidate in (*selected_ranked, *selected_near)}
    return comparison.model_copy(
        update={
            "ranked": selected_ranked,
            "near_miss": selected_near,
            "tour_snapshots": [tour for tour in comparison.tour_snapshots if tour.id in seen],
            "evaluations": [item for item in comparison.evaluations if item.offer_id in offer_ids],
        }
    )


def json_candidates(value: Any) -> list[dict[str, Any]]:
    """Find JSON objects in common MCP/OpenCode result envelopes."""
    found: list[dict[str, Any]] = []
    pending = [value]
    seen: set[int] = set()
    while pending:
        item = pending.pop()
        if isinstance(item, dict):
            if id(item) in seen:
                continue
            seen.add(id(item))
            found.append(item)
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
        elif isinstance(item, str):
            try:
                parsed = json.loads(item)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, (dict, list)):
                pending.append(parsed)
    return found
