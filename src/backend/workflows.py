"""Shared catalog-to-comparison workflow used by HTTP and agent tools."""

from __future__ import annotations

from backend.decide.engine import compare
from backend.input.pipeline import validate_requirement
from backend.models import Comparison, Requirement, State, TourSnapshot
from backend.normalize.snapshots import rows_to_snapshots
from backend.settings import Settings


class TourWorkflows:
    def __init__(self, settings: Settings, catalog):
        self.settings = settings
        self.catalog = catalog

    def requirement(
        self,
        raw_text: str,
        conditions,
        travelers=1,
        ranking=None,
        requirement_id: str | None = None,
        require_weights: bool = False,
    ) -> Requirement:
        return validate_requirement(
            raw_text,
            conditions,
            travelers,
            requirement_id=requirement_id,
            ranking=ranking,
            require_weights=require_weights,
        )

    def snapshots(self, candidate_limit: int | None = None) -> list[TourSnapshot]:
        high = self.settings.supabase_scan_limit
        default_limit = min(self.settings.candidate_limit, high)
        limit = default_limit if candidate_limit is None else candidate_limit
        if (not isinstance(limit, int) or isinstance(limit, bool)
                or not 1 <= limit <= high):
            limit = default_limit
        return rows_to_snapshots(
            self.catalog.list_tours(limit),
            freshness_seconds=self.settings.supabase_tour_freshness_seconds,
        )

    def comparison(
        self,
        requirement: Requirement,
        candidate_limit: int | None = None,
        soft_verdicts: dict[tuple[str, str], tuple[State, str, str]] | None = None,
    ) -> Comparison:
        return compare(
            requirement,
            self.snapshots(candidate_limit),
            cfg=self.settings.tuning.decide,
            soft_verdicts=soft_verdicts,
        )
