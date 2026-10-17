"""Shared catalog-to-comparison workflow used by HTTP and agent tools."""

from __future__ import annotations

from backend.decide.engine import compare
from backend.errors import AppError
from backend.input.pipeline import validate_requirement
from backend.models import Comparison, ExtractedTourFacts, Requirement, State, TourSnapshot
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
        traveler_mix=None,
        alternatives=None,
        assumptions=None,
    ) -> Requirement:
        return validate_requirement(
            raw_text,
            conditions,
            travelers,
            requirement_id=requirement_id,
            ranking=ranking,
            require_weights=require_weights,
            traveler_mix=traveler_mix,
            alternatives=alternatives,
            assumptions=assumptions,
        )

    def snapshots(self, candidate_limit: int | None = None) -> list[TourSnapshot]:
        high = self.settings.supabase_scan_limit
        default_limit = min(self.settings.candidate_limit, high)
        limit = default_limit if candidate_limit is None else candidate_limit
        if (not isinstance(limit, int) or isinstance(limit, bool)
                or not 1 <= limit <= high):
            limit = default_limit
        index_reader = getattr(self.catalog, "list_tour_index", None)
        rows = index_reader(limit) if callable(index_reader) else self.catalog.list_tours(limit)
        return rows_to_snapshots(rows, freshness_seconds=self.settings.supabase_tour_freshness_seconds)

    def tour_detail(self, tour_id: str) -> TourSnapshot | None:
        detail_reader = getattr(self.catalog, "list_tour_details", None)
        if callable(detail_reader):
            rows = detail_reader([tour_id])
            snapshots = rows_to_snapshots(
                rows, freshness_seconds=self.settings.supabase_tour_freshness_seconds
            )
            return next((item for item in snapshots if item.id == tour_id), None)
        return next((item for item in self.snapshots(self.settings.supabase_scan_limit)
                     if item.id == tour_id), None)

    def comparison(
        self,
        requirement: Requirement,
        candidate_limit: int | None = None,
        soft_verdicts: dict[tuple[str, str], tuple[State, str, str]] | None = None,
    ) -> Comparison:
        return self.comparison_on_snapshot(
            requirement,
            self.snapshots(candidate_limit),
            soft_verdicts=soft_verdicts,
        )

    def comparison_on_snapshot(
        self,
        requirement: Requirement,
        snapshots: list[TourSnapshot],
        soft_verdicts: dict[tuple[str, str], tuple[State, str, str]] | None = None,
        *,
        eligible_tour_ids: set[str] | None = None,
        hydrate_tour_ids: set[str] | None = None,
        metric_facts: dict[str, ExtractedTourFacts] | None = None,
    ) -> Comparison:
        """Compare a scan index, hydrating only eligible and displayed near-miss tours."""
        if not any(tour.detail_state == "index" for tour in snapshots):
            return compare(
                requirement,
                snapshots,
                cfg=self.settings.tuning.decide,
                soft_verdicts=soft_verdicts,
                metric_facts=metric_facts,
                eligible_tour_ids=eligible_tour_ids,
            )
        preliminary = compare(requirement, snapshots, cfg=self.settings.tuning.decide)
        needed_ids = (
            set(hydrate_tour_ids)
            if hydrate_tour_ids is not None
            else {candidate.tour_id for candidate in preliminary.ranked}
        )
        needed_ids.update(candidate.tour_id for candidate in preliminary.near_miss)
        missing = [
            tour for tour in snapshots
            if tour.id in needed_ids and tour.detail_state == "index"
        ]
        detail_reader = getattr(self.catalog, "list_tour_details", None)
        if not missing or not callable(detail_reader):
            return compare(
                requirement,
                snapshots,
                cfg=self.settings.tuning.decide,
                soft_verdicts=soft_verdicts,
                metric_facts=metric_facts,
                eligible_tour_ids=eligible_tour_ids,
            )

        details = rows_to_snapshots(
            detail_reader([tour.id for tour in missing]),
            freshness_seconds=self.settings.supabase_tour_freshness_seconds,
        )
        details_by_id = {tour.id: tour for tour in details}
        merged: dict[str, TourSnapshot] = {tour.id: tour for tour in snapshots}
        for index_tour in missing:
            detail = details_by_id.get(index_tour.id)
            if detail is None:
                raise AppError(
                    "CATALOG_DETAIL_UNAVAILABLE",
                    "A selected catalog record could not be loaded. Please rerun the comparison.",
                    502,
                    retryable=True,
                )
            if not _same_catalog_index(index_tour, detail):
                raise AppError(
                    "CATALOG_CHANGED_DURING_SCAN",
                    "The catalog changed while this comparison was running. Please rerun it.",
                    409,
                    retryable=True,
                )
            merged[index_tour.id] = detail
        return compare(
            requirement,
            [merged[tour.id] for tour in snapshots],
            cfg=self.settings.tuning.decide,
            soft_verdicts=soft_verdicts,
            metric_facts=metric_facts,
            eligible_tour_ids=eligible_tour_ids,
        )


def _same_catalog_index(index: TourSnapshot, detail: TourSnapshot) -> bool:
    """Ensure detail hydration is from the same observed catalog revision as the index."""
    if (
        index.id != detail.id
        or index.observed_at != detail.observed_at
        or index.name != detail.name
        or index.url != detail.url
        or index.destinations != detail.destinations
        or index.raw_destinations != detail.raw_destinations
        or index.route != detail.route
        or index.duration_nights != detail.duration_nights
        or index.departure_city != detail.departure_city
        or index.duration_days != detail.duration_days
        or index.transport != detail.transport
        or index.accommodation != detail.accommodation
        or index.verification != detail.verification
    ):
        return False
    index_offers = {
        offer.id: (offer.departure_date, offer.price, offer.currency, offer.price_basis,
                   offer.availability, offer.evidence.observed_at)
        for offer in index.offers
    }
    detail_offers = {
        offer.id: (offer.departure_date, offer.price, offer.currency, offer.price_basis,
                   offer.availability, offer.evidence.observed_at)
        for offer in detail.offers
    }
    return index_offers == detail_offers
