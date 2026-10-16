"""Cost totals stay conservative and expose excluded expenses separately."""

from backend.agent.mcp_server import CostExposureInput, TourMetricFactsInput, _validate_metric_facts
from backend.decide.metrics import build_metric_profiles
from backend.models import (
    CostExposure,
    ExtractedTourFacts,
    OfferSnapshot,
    Requirement,
    TourSnapshot,
)


def _tour(*, price_basis="from", currency="VND"):
    offer = OfferSnapshot(
        id="offer-1",
        tour_id="tour-1",
        price=1_000_000,
        currency=currency,
        price_basis=price_basis,
        price_by_age={"adult": 1_000_000},
    )
    return TourSnapshot(
        id="tour-1",
        name="Example tour",
        duration_days=2,
        duration_nights=1,
        exclusions="Không bao gồm vé tham quan",
        surcharges="Phụ thu phòng đơn 500.000 VND/phòng",
        offers=[offer],
    ), offer


def _req():
    return Requirement(id="req-1", travelers=2, traveler_mix={"adult": 2})


def test_group_total_adds_only_grounded_mandatory_exclusions_and_surcharges():
    tour, offer = _tour()
    facts = ExtractedTourFacts(
        tour_id=tour.id,
        exclusions=[CostExposure(
            name="Vé tham quan",
            obligation="mandatory",
            amount=200_000,
            currency="VND",
            unit="per_person",
            source_field="exclusions",
            quote="Vé tham quan bắt buộc 200.000 VND/người",
        )],
        surcharges=[CostExposure(
            name="Phụ thu phòng đơn",
            obligation="conditional",
            amount=500_000,
            currency="VND",
            unit="per_room",
            source_field="surcharges",
            quote="Phụ thu phòng đơn 500.000 VND/phòng",
            applies_when="nếu ở phòng riêng",
        )],
        reviewed_fields=["exclusions", "surcharges"],
    )

    profile = build_metric_profiles(_req(), [(tour, offer.id)], {}, {tour.id: facts})[0]

    assert profile.cost.group_total_calculated == 2_400_000
    assert profile.cost.priced_extras[0].calculated_total == 400_000
    assert profile.cost.optional_or_conditional[0].amount == 500_000
    assert "Tạm tính" in profile.cost.group_total_scope


def test_unpriced_exclusion_is_not_guessed_or_added_to_group_total():
    tour, offer = _tour()
    facts = ExtractedTourFacts(
        tour_id=tour.id,
        exclusions=[CostExposure(
            name="Vé tham quan",
            obligation="mandatory",
            source_field="exclusions",
            quote="Không bao gồm vé tham quan",
        )],
        reviewed_fields=["exclusions", "surcharges"],
    )

    profile = build_metric_profiles(_req(), [(tour, offer.id)], {}, {tour.id: facts})[0]

    assert profile.cost.group_total_calculated == 2_000_000
    assert profile.cost.unpriced_exclusions[0].amount is None
    assert profile.cost.state == "partial"
    assert profile.metrics["unpriced_cost_exposures"].value["count"] == 1


def test_unreviewed_cost_fields_keep_total_and_cost_coverage_partial():
    tour, offer = _tour()
    facts = ExtractedTourFacts(tour_id=tour.id)

    profile = build_metric_profiles(_req(), [(tour, offer.id)], {}, {tour.id: facts})[0]

    assert profile.cost.group_total_calculated == 2_000_000
    assert profile.cost.state == "partial"
    assert profile.metrics["unpriced_cost_exposures"].state == "unknown"


def test_empty_extraction_does_not_claim_nonempty_exclusions_were_reviewed():
    tour, offer = _tour()
    payload = TourMetricFactsInput(
        tour_id=tour.id,
        exclusions=[CostExposureInput(
            name="Vé tham quan",
            obligation="mandatory",
            quote="Không bao gồm vé tham quan",
        )],
    )

    facts, rejected = _validate_metric_facts(tour, payload, 3)
    profile = build_metric_profiles(_req(), [(tour, offer.id)], {}, {tour.id: facts})[0]

    assert rejected == 0
    assert facts.exclusions[0].quote == "Không bao gồm vé tham quan"
    assert facts.reviewed_fields == []
    assert profile.metrics["unpriced_cost_exposures"].state == "unknown"
    assert profile.cost.state == "partial"


def test_mid_word_fact_quote_is_stored_snapped():
    tour, offer = _tour()
    payload = TourMetricFactsInput(
        tour_id=tour.id,
        exclusions=[CostExposureInput(
            name="Vé tham quan",
            obligation="mandatory",
            quote="hông bao gồm vé tham qua",
        )],
    )
    facts, rejected = _validate_metric_facts(tour, payload, 3)
    assert rejected == 0
    assert facts.exclusions[0].quote == "Không bao gồm vé tham quan"
