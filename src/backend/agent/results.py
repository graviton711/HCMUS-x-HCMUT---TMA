"""Limits and parsers for tool results relayed through OpenCode JSON events."""

from __future__ import annotations

import json
from typing import Any

from backend.models import Comparison, RankedCandidate


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
    limited_views = [
        view.model_copy(update={
            "candidates": view.candidates[:limit],
            "currencies": sorted({currency.upper() for currency in view.currencies}),
        })
        for view in comparison.decision_views
    ]
    selected_options = comparison.decision_options[:3]
    option_candidates = [
        RankedCandidate(tour_id=item.tour_id, offer_id=item.offer_id)
        for item in selected_options
    ]
    view_candidates = [candidate for view in limited_views for candidate in view.candidates]
    seen.update(candidate.tour_id for candidate in view_candidates)
    offer_ids = {
        candidate.offer_id
        for candidate in (*selected_ranked, *selected_near, *view_candidates, *option_candidates)
    }
    selected_tours = {
        candidate.tour_id
        for candidate in (*selected_ranked, *selected_near, *view_candidates)
    }
    return comparison.model_copy(
        update={
            "ranked": selected_ranked,
            "near_miss": selected_near,
            "tour_snapshots": [
                tour.model_copy(update={
                    "offers": [offer for offer in tour.offers if offer.id in offer_ids],
                })
                for tour in comparison.tour_snapshots
                if tour.id in selected_tours
            ],
            "evaluations": [item for item in comparison.evaluations if item.offer_id in offer_ids],
            "decision_views": limited_views,
            "decision_options": [item for item in selected_options if item.tour_id in selected_tours],
            "metric_profiles": [item for item in comparison.metric_profiles if item.offer_id in offer_ids],
            "extracted_facts": [item for item in comparison.extracted_facts if item.tour_id in selected_tours],
            "recommendation": (
                comparison.recommendation
                if comparison.recommendation and comparison.recommendation.tour_id in selected_tours
                else None
            ),
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
