"""Replayable what-if calculations over immutable comparison snapshots."""

from __future__ import annotations

from backend.models import (
    Comparison,
    CostExposure,
    CostScenarioAssumptions,
    CostScenarioItem,
    CostScenarioResult,
    MetricEvidence,
    MetricProfile,
    OfferSnapshot,
    TourSnapshot,
)


def cost_scenario(
    comparison: Comparison, assumptions: CostScenarioAssumptions
) -> CostScenarioResult:
    facts = {item.offer_id: item for item in comparison.metric_profiles}
    option_ids = list(dict.fromkeys(item.offer_id for item in comparison.decision_options[:3]))
    selected = [facts[offer_id] for offer_id in option_ids if offer_id in facts]
    if not selected:
        selected = comparison.metric_profiles[:3]
    tour_offers = {
        offer.id: (tour, offer)
        for tour in comparison.tour_snapshots for offer in tour.offers
    }
    items = [
        _scenario_item(comparison, profile, *tour_offers[profile.offer_id], assumptions)
        for profile in selected if profile.offer_id in tour_offers
    ]
    return CostScenarioResult(
        source_comparison_id=comparison.id,
        assumptions=assumptions,
        scanned_offers=(
            comparison.decision_trace.scanned_offers
            if comparison.decision_trace is not None
            else comparison.candidates_considered
        ),
        items=items,
    )


def _scenario_item(
    comparison: Comparison,
    profile: MetricProfile,
    tour: TourSnapshot,
    offer: OfferSnapshot,
    assumptions: CostScenarioAssumptions,
) -> CostScenarioItem:
    base, base_evidence = _party_base(offer, assumptions)
    priced: list[CostExposure] = []
    unresolved: list[CostExposure] = []
    evidence = list(base_evidence)
    for source in profile.exclusions:
        item = source.model_copy(deep=True)
        if item.obligation in ("optional", "conditional", "unknown"):
            unresolved.append(item)
            continue
        quantity = _quantity(item.unit, assumptions, tour)
        if (
            item.amount is None or item.unit == "unknown" or quantity is None
            or not item.currency or item.currency.upper() != offer.currency.upper()
        ):
            unresolved.append(item)
            continue
        item.calculated_total = item.amount * quantity
        priced.append(item)
        if item.quote:
            evidence.append(MetricEvidence(
                source_field=item.source_field,
                quote=item.quote,
                observed_at=tour.observed_at,
                url=tour.url,
            ))

    exposure_coverage = profile.metrics.get("unpriced_cost_exposures")
    if exposure_coverage is None or exposure_coverage.state != "observed":
        unresolved.append(CostExposure(
            name="Phần loại trừ/phụ thu chưa được rà đủ",
            obligation="unknown",
            unit="unknown",
            applies_when="Nguồn chưa được phân tích đầy đủ cho mọi khoản loại trừ và phụ thu",
            source_field="exclusions_and_surcharges",
        ))

    if offer.single_supplement is not None:
        if assumptions.single_rooms is None:
            unresolved.append(CostExposure(
                name="Phụ thu phòng đơn", obligation="conditional",
                amount=offer.single_supplement, currency=offer.currency,
                unit="per_room", applies_when="Chưa giả định số phòng đơn",
                source_field="offers.single_supplement",
            ))
        elif assumptions.single_rooms > 0:
            priced.append(CostExposure(
                name="Phụ thu phòng đơn", obligation="mandatory",
                amount=offer.single_supplement, currency=offer.currency,
                unit="per_room", applies_when=f"{assumptions.single_rooms} phòng đơn giả định",
                source_field="offers.single_supplement",
                calculated_total=offer.single_supplement * assumptions.single_rooms,
            ))
            evidence.append(MetricEvidence(
                source_field="offers.single_supplement",
                quote=f"{offer.single_supplement} {offer.currency} mỗi phòng đơn",
                observed_at=offer.evidence.observed_at or tour.observed_at,
                url=offer.evidence.url or tour.url,
            ))

    priced_total = sum(item.calculated_total or 0 for item in priced)
    known_total = base + priced_total if base is not None else None
    complete = base is not None and not any(
        item.obligation != "optional" for item in unresolved
    )
    baseline_profile = next((p for p in comparison.metric_profiles
                             if p.offer_id == offer.id and p.cost.currency.upper() == offer.currency.upper()), None)
    baseline = (
        baseline_profile.cost.group_total_calculated
        if baseline_profile and baseline_profile.cost.state == "observed" else None
    )
    return CostScenarioItem(
        tour_id=tour.id,
        tour_name=tour.name,
        offer_id=offer.id,
        currency=offer.currency.upper(),
        price_basis=offer.price_basis,
        listed_price=offer.price,
        group_base_calculated=base,
        priced_mandatory_extras=priced,
        known_total=known_total,
        unresolved_exposures=unresolved,
        delta_from_original=known_total - baseline if known_total is not None and baseline is not None else None,
        state="observed" if complete else "partial" if known_total is not None else "unknown",
        evidence=evidence,
    )


def _party_base(
    offer: OfferSnapshot, assumptions: CostScenarioAssumptions
) -> tuple[int | None, list[MetricEvidence]]:
    if offer.price is None or not offer.currency:
        return None, []
    mix = assumptions.traveler_mix
    if not mix or sum(mix.values()) != assumptions.travelers:
        return None, []
    total = 0
    for age_group, count in mix.items():
        if count <= 0:
            continue
        age_price = offer.price_by_age.get(age_group)
        if age_price is None and age_group == "adult":
            age_price = offer.price
        if age_price is None:
            return None, []
        total += age_price * count
    quote = next((str(item.get("quote", "")) for item in offer.price_quotes if item.get("quote")), "")
    evidence = [MetricEvidence(
        source_field="offers.price_by_age" if offer.price_by_age else "offers.price",
        quote=quote,
        observed_at=offer.evidence.observed_at,
        url=offer.evidence.url,
    )] if offer.evidence.url or quote else []
    return total, evidence


def _quantity(unit: str, assumptions: CostScenarioAssumptions, tour: TourSnapshot) -> int | None:
    mix = assumptions.traveler_mix
    if unit == "per_booking":
        return 1
    if unit == "per_person":
        return assumptions.travelers
    if unit == "per_adult":
        return mix.get("adult") if "adult" in mix else None
    if unit == "per_child":
        return mix.get("child", 0) + mix.get("small_child", 0) if mix else None
    if unit == "per_day":
        return tour.duration_days
    if unit == "per_night":
        return assumptions.nights if assumptions.nights is not None else tour.duration_nights
    if unit == "per_room":
        return assumptions.rooms
    return None
