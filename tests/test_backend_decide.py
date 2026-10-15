"""Hard rules, tri-state eligibility, soft verdict ranking and analysis."""

from datetime import UTC, datetime, timedelta

from backend.data.catalog import FixtureCatalog
from backend.decide.engine import compare
from backend.decide.scenarios import cost_scenario
from backend.input.pipeline import requirement_from_form
from backend.models import (
    Condition,
    CostExposure,
    CostScenarioAssumptions,
    ExtractedTourFacts,
    OfferSnapshot,
    Requirement,
    TourRow,
    TourSnapshot,
    uid,
)
from backend.normalize.snapshots import rows_to_snapshots


def _snapshots():
    return rows_to_snapshots(FixtureCatalog().list_tours(10))


def _req(form):
    return requirement_from_form(form)


def test_budget_hard_filter_per_offer(decide_cfg):
    comparison = compare(_req({"destinations": ["Đà Lạt"], "budget_max": 7_000_000}),
                         _snapshots(), decide_cfg)
    kept = {(item.tour_id, item.offer_id) for item in comparison.ranked}
    assert ("dlv-dalat-3n", "dlv-dalat-3n-20270109") in kept
    assert ("dlv-dalat-3n", "dlv-dalat-3n-20261225") not in kept


def test_from_price_is_unknown_and_never_passes_budget(decide_cfg):
    req = _req({"destinations": ["Hạ Long"], "budget_max": 10_000_000})
    comparison = compare(req, _snapshots(), decide_cfg)
    budget_id = next(condition.id for condition in req.conditions if condition.field == "budget_max")
    states = {(item.offer_id, item.condition_id): item.state for item in comparison.evaluations}
    offer_id = "sgt-halong-3n-20261227"
    assert states[(offer_id, budget_id)] == "unknown"
    assert offer_id not in {item.offer_id for item in comparison.ranked}
    assert offer_id in {item.offer_id for item in comparison.near_miss}


def test_from_price_above_budget_fails(decide_cfg):
    row = TourRow(
        tour={"record_key": "from-high", "price_type": "from", "currency": "VND"},
        offers=[{
            "record_key": "from-high-offer",
            "price": 11_000_000,
                "price_type": "from",
            "currency": "VND",
            "departure_date": "2027-02-01",
            "observed_at": datetime.now(UTC).isoformat(),
        }],
    )
    comparison = compare(
        _req({"budget_max": 10_000_000}), rows_to_snapshots([row]), decide_cfg
    )
    budget_id = next(c.id for c in comparison.requirement.conditions if c.field == "budget_max")
    evaluation = next(e for e in comparison.evaluations if e.condition_id == budget_id)
    assert evaluation.state == "fail"
    assert evaluation.reason_code == "PRICE_LOWER_BOUND_OVER_BUDGET"


def test_missing_contact_and_non_vnd_prices_are_unknown(decide_cfg):
    observed = datetime.now(UTC).isoformat()
    row = TourRow(
        tour={"record_key": "price-cases", "price_type": "fixed"},
        offers=[
            {"record_key": "missing", "price": None, "currency": "VND", "observed_at": observed},
            {"record_key": "contact", "price": 5_000_000, "price_type": "contact",
             "currency": "VND", "observed_at": observed},
            {"record_key": "foreign-currency", "price": 5_000_000, "currency": "USD",
             "observed_at": observed},
        ],
    )
    comparison = compare(_req({"budget_max": 8_000_000}), rows_to_snapshots([row]), decide_cfg)
    budget_id = next(c.id for c in comparison.requirement.conditions if c.field == "budget_max")
    states = {(e.offer_id, e.state, e.reason_code) for e in comparison.evaluations}
    assert ("missing", "unknown", "PRICE_MISSING") in states
    assert ("contact", "unknown", "PRICE_NOT_EXACT") in states
    assert ("foreign-currency", "unknown", "PRICE_CURRENCY_MISMATCH") in states
    assert all(e.condition_id == budget_id for e in comparison.evaluations)


def test_destination_mismatch_fails(decide_cfg):
    comparison = compare(_req({"destinations": ["Đà Lạt"]}), _snapshots(), decide_cfg)
    assert {item.tour_id for item in comparison.ranked} == {"dlv-dalat-3n"}


def test_destination_value_without_catalog_match_fails_when_destinations_exist(decide_cfg):
    now = datetime.now(UTC).isoformat()
    partial = TourRow(
        tour={"record_key": "partial", "departure_city": "TP.HCM", "destinations": ["Unknown city"]},
        offers=[{"record_key": "partial-offer", "departure_date": "2027-02-01",
                 "price": 20_000_000, "price_type": "fixed", "observed_at": now}],
    )
    req = Requirement(id=uid("req"), conditions=[Condition(
        id="city", field="destination", value="Tokyo", strength="hard"
    )])
    comparison = compare(req, rows_to_snapshots([partial]), decide_cfg)
    states = {(item.offer_id, item.condition_id): item.state for item in comparison.evaluations}
    assert states[("partial-offer", "city")] == "fail"
    assert comparison.ranked == []
    assert [item.tour_id for item in comparison.near_miss] == ["partial"]


def test_destination_matching_uses_only_explicit_catalog_labels(decide_cfg):
    now = datetime.now(UTC).isoformat()
    foreign = TourRow(
        tour={"record_key": "foreign", "departure_city": "TP.HCM",
              "destinations": ["TP.HCM", "Thượng Hải", "Hàng Châu", "TP.HCM"],
              "route": ["TP.HCM", "Thượng Hải", "Hàng Châu", "TP.HCM"]},
        offers=[{"record_key": "foreign-offer", "departure_date": "2027-02-01",
                 "price": 20_000_000, "price_type": "fixed", "observed_at": now}],
    )
    unknown = TourRow(
        tour={"record_key": "partial", "departure_city": "TP.HCM",
              "destinations": ["TP.HCM", "Unmapped city", "TP.HCM"]},
        offers=[{"record_key": "partial-offer", "departure_date": "2027-02-01",
                 "price": 20_000_000, "price_type": "fixed", "observed_at": now}],
    )
    req = Requirement(id=uid("req"), conditions=[
        Condition(id="explicit", field="destination", operator="any",
                  value=["Thượng Hải", "Hàng Châu"], strength="hard"),
        Condition(id="country", field="destination", value="Việt Nam", strength="hard"),
    ])
    comparison = compare(req, rows_to_snapshots([foreign, unknown]), decide_cfg)
    states = {(item.offer_id, item.condition_id): item.state for item in comparison.evaluations}
    assert states[("foreign-offer", "explicit")] == "pass"
    assert states[("foreign-offer", "country")] == "fail"
    assert states[("partial-offer", "explicit")] == "fail"
    assert states[("partial-offer", "country")] == "fail"
    assert comparison.ranked == []
    assert {item.tour_id for item in comparison.near_miss} == {"foreign", "partial"}


def test_missing_destination_data_is_unknown(decide_cfg):
    row = TourRow(
        tour={"record_key": "missing-destination", "destinations": []},
        offers=[{"record_key": "missing-destination-offer"}],
    )
    req = Requirement(id=uid("req"), conditions=[Condition(
        id="destination", field="destination", value="Tokyo", strength="hard"
    )])
    comparison = compare(req, rows_to_snapshots([row]), decide_cfg)
    assert comparison.evaluations[0].state == "unknown"
    assert comparison.evaluations[0].reason_code == "DESTINATION_MISSING"


def test_date_matching_uses_catalog_date_regardless_of_crawl_freshness(decide_cfg):
    future = datetime.now(UTC) + timedelta(days=2)
    stale_tours = rows_to_snapshots(
        FixtureCatalog().list_tours(10),
        freshness_seconds={"departure_date": 86400},
        now=future,
    )
    req = _req({"destinations": ["Đà Lạt"], "budget_max": 8_000_000})
    req.conditions.append(Condition(id="old-date", field="date_from", value="2026-12-01"))
    comparison = compare(req, stale_tours, decide_cfg)
    states = {(item.offer_id, item.condition_id): item.state for item in comparison.evaluations}
    assert states[("dlv-dalat-3n-20261225", "h2")] == "pass"
    assert states[("dlv-dalat-3n-20261225", "old-date")] == "pass"
    stale_offer = next(
        offer for tour in stale_tours for offer in tour.offers
        if offer.id == "dlv-dalat-3n-20261225"
    )
    assert stale_offer.departure_freshness == "stale"


def test_date_matching_does_not_require_observed_at(decide_cfg):
    row = TourRow(
        tour={"record_key": "no-crawl-time", "departure_city": "TP.HCM"},
        offers=[{"record_key": "scheduled", "departure_date": "2026-12-25"}],
    )
    req = Requirement(id=uid("req"), conditions=[
        Condition(id="start", field="date_from", value="2026-12-19", strength="hard"),
        Condition(id="end", field="date_to", value="2026-12-26", strength="hard"),
    ])
    snapshot = rows_to_snapshots([row])[0]
    comparison = compare(req, [snapshot], decide_cfg)
    states = {item.condition_id: item.state for item in comparison.evaluations}
    assert snapshot.offers[0].departure_freshness == "unknown"
    assert states == {"start": "pass", "end": "pass"}


def test_any_operator_matches_either(decide_cfg):
    req = Requirement(id=uid("req"), conditions=[Condition(
        id="h1", field="destination", operator="any", value=["Đà Nẵng", "Hạ Long"], strength="hard"
    )])
    comparison = compare(req, _snapshots(), decide_cfg)
    assert {item.tour_id for item in comparison.ranked} == {"sgt-halong-3n"}


def test_rank_prefers_cheaper_offer_when_soft_verdicts_tie(decide_cfg):
    comparison = compare(_req({"destinations": ["Đà Lạt"]}), _snapshots(), decide_cfg)
    assert comparison.ranked[0].offer_id == "dlv-dalat-3n-20270109"


def test_soft_verdict_count_ranks_before_price_and_keeps_quote_reason(decide_cfg):
    req = Requirement(
        id=uid("req"),
        raw_text="thích công viên giải trí và hoạt động vui chơi",
        conditions=[
            Condition(id="s1", field="preference", operator="contains", value="công viên giải trí",
                      strength="soft", quote="công viên giải trí"),
            Condition(id="s2", field="preference", operator="contains", value="hoạt động vui chơi",
                      strength="soft", quote="hoạt động vui chơi"),
        ],
    )
    tours = _snapshots()
    phu_offer = "vtr-phuquoc-4n-20261226"
    verdicts = {
        (phu_offer, "s1"): ("pass", "VinWonders", "Có công viên giải trí trong lịch trình."),
        (phu_offer, "s2"): ("pass", "VinWonders", "Có hoạt động vui chơi trong lịch trình."),
    }
    comparison = compare(req, tours, decide_cfg, verdicts)
    assert comparison.ranked[0].tour_id == "vtr-phuquoc-4n"
    assert comparison.ranked[0].score == 2
    by_id = {item.condition_id: item for item in comparison.evaluations if item.offer_id == phu_offer}
    assert by_id["s1"].state == "pass"
    assert by_id["s1"].quote == "VinWonders"
    assert by_id["s1"].reason == "Có công viên giải trí trong lịch trình."


def test_weighted_views_are_explainable_currency_safe_and_pareto(decide_cfg):
    req = Requirement(
        id="req_views",
        raw_text="Ưu tiên thiên nhiên, sau đó biển",
        conditions=[
            Condition(id="nature", field="preference", value="thiên nhiên", strength="soft",
                      quote="thiên nhiên", weight_percent=80),
            Condition(id="beach", field="preference", value="biển", strength="soft",
                      quote="biển", weight_percent=20),
        ],
    )

    def tour(key, price, currency="VND", basis="exact"):
        return TourSnapshot(
            id=key,
            name=f"Tour {key}",
            itinerary=f"Evidence for {key}",
            offers=[OfferSnapshot(
                id=f"offer-{key}", tour_id=key, price=price, currency=currency,
                price_basis=basis,
            )],
        )

    tours = [
        tour("a", 100), tour("b", 200), tour("c", 150), tour("d", 40, "USD"),
        tour("e", 100),
        tour("from", 1, "VND", "from"), tour("contact", 5, "VND", "contact"),
        tour("missing", None),
    ]
    verdicts = {
        ("offer-a", "nature"): ("pass", "Evidence for a", "Có bằng chứng phù hợp."),
        ("offer-a", "beach"): ("fail", "Evidence for a", "Không thấy nội dung về biển."),
        ("offer-b", "nature"): ("pass", "Evidence for b", "Có bằng chứng phù hợp."),
        ("offer-b", "beach"): ("pass", "Evidence for b", "Có bằng chứng phù hợp."),
        ("offer-c", "nature"): ("pass", "Evidence for c", "Có bằng chứng phù hợp."),
        ("offer-c", "beach"): ("fail", "Evidence for c", "Không thấy nội dung về biển."),
        ("offer-d", "nature"): ("unknown", "", "Thiếu dữ liệu."),
        ("offer-d", "beach"): ("pass", "Evidence for d", "Có bằng chứng phù hợp."),
        ("offer-e", "nature"): ("pass", "Evidence for e", "Có bằng chứng phù hợp."),
        ("offer-e", "beach"): ("pass", "Evidence for e", "Có bằng chứng phù hợp."),
        ("offer-from", "nature"): ("pass", "Evidence for from", "Có bằng chứng phù hợp."),
        ("offer-from", "beach"): ("pass", "Evidence for from", "Có bằng chứng phù hợp."),
        ("offer-contact", "nature"): ("pass", "Evidence for contact", "Có bằng chứng phù hợp."),
        ("offer-contact", "beach"): ("pass", "Evidence for contact", "Có bằng chứng phù hợp."),
        ("offer-missing", "nature"): ("pass", "Evidence for missing", "Có bằng chứng phù hợp."),
        ("offer-missing", "beach"): ("pass", "Evidence for missing", "Có bằng chứng phù hợp."),
    }

    comparison = compare(req, tours, decide_cfg, verdicts)
    views = {view.kind: view for view in comparison.decision_views}

    assert [item.tour_id for item in views["cheapest"].candidates[:3]] == ["d", "e", "a"]
    assert views["cheapest"].currencies == ["USD", "VND"]
    best_fit_ids = [item.tour_id for item in views["best_fit"].candidates]
    assert {"b", "from", "contact", "missing"}.issubset(best_fit_ids)
    cheapest_ids = {item.tour_id for item in views["cheapest"].candidates}
    assert not {"from", "contact", "missing"} & cheapest_ids
    balanced_ids = {item.tour_id for item in views["balanced"].candidates}
    assert not {"from", "contact", "missing"} & balanced_ids
    assert "c" not in {item.tour_id for item in views["balanced"].candidates}
    assert balanced_ids == {"d", "e"}
    assert [item.tour_id for item in views["best_fit"].candidates] == [
        item.tour_id for item in compare(req, tours, decide_cfg, verdicts).decision_views[1].candidates
    ]
    assert next(item for item in comparison.evaluations
                if item.offer_id == "offer-d" and item.condition_id == "nature").state == "unknown"


def test_analysis_surfaces_costs_risks_benefits(decide_cfg):
    comparison = compare(_req({"destinations": ["Phú Quốc"]}), _snapshots(), decide_cfg)
    text = " ".join(comparison.analysis.hidden_costs + comparison.analysis.conditions
                     + comparison.analysis.risks + comparison.analysis.benefits)
    assert "Phụ thu" in text or "phụ thu" in text.lower()
    assert comparison.analysis.benefits
    assert comparison.candidates_considered == 3


def test_near_miss_keeps_failures_separate_from_ranked(decide_cfg):
    def row(key, destinations, transport, duration):
        return TourRow(
            tour={"record_key": key, "departure_city": "TP.HCM", "destinations": destinations,
                  "transport": transport, "duration_days": duration},
            offers=[{"record_key": f"{key}-offer", "departure_date": "2027-02-01"}],
        )

    tours = rows_to_snapshots([
        row("ok", ["Đà Lạt"], "bus", 3),
        row("near1", ["Đà Lạt"], "flight", 3),
        row("near2", ["Nha Trang"], "flight", 3),
        row("out", ["Nha Trang"], "flight", 5),
    ])
    req = Requirement(id=uid("req"), conditions=[
        Condition(id="h1", field="destination", operator="contains", value="Đà Lạt", strength="hard"),
        Condition(id="h2", field="transport", operator="eq", value="bus", strength="hard"),
        Condition(id="h3", field="duration_days", operator="eq", value=3, strength="hard"),
    ])
    comparison = compare(req, tours, decide_cfg)
    assert [item.tour_id for item in comparison.ranked] == ["ok"]
    assert [item.tour_id for item in comparison.near_miss] == ["near1", "near2"]
    assert comparison.near_miss[0].score > comparison.near_miss[1].score


def test_decision_trace_counts_overlapping_states_and_first_blocker(decide_cfg):
    rows = [
        TourRow(tour={"record_key": "a", "departure_city": "Hà Nội", "duration_days": 1},
                offers=[{"record_key": "oa"}]),
        TourRow(tour={"record_key": "b", "departure_city": "TP.HCM", "duration_days": 2},
                offers=[
                    {"record_key": "ob", "departure_date": "2026-10-20"},
                    {"record_key": "ob-unknown"},
                ]),
        TourRow(tour={"record_key": "c", "departure_city": "TP.HCM", "duration_days": 2},
                offers=[{"record_key": "oc"}]),
    ]
    tours = rows_to_snapshots(rows)
    req = Requirement(id=uid("req"), conditions=[
        Condition(id="origin", field="departure_city", value="TP.HCM", strength="hard"),
        Condition(id="date", field="date_from", value="2026-10-19", strength="hard"),
        Condition(id="duration", field="duration_days", value=2, strength="hard"),
    ])

    comparison = compare(req, tours, decide_cfg)
    trace = comparison.decision_trace
    assert trace is not None
    assert (trace.scanned_tours, trace.scanned_offers) == (3, 4)
    assert (trace.eligible_tours, trace.eligible_offers, trace.excluded_offers) == (1, 1, 3)
    counts = {item.condition_id: item for item in trace.condition_counts}
    assert (counts["origin"].pass_offers, counts["origin"].fail_offers) == (3, 1)
    assert (counts["origin"].pass_tours, counts["origin"].fail_tours) == (2, 1)
    assert (counts["date"].pass_offers, counts["date"].unknown_offers) == (1, 3)
    assert (counts["date"].pass_tours, counts["date"].unknown_tours) == (1, 3)
    assert (counts["duration"].pass_offers, counts["duration"].fail_offers) == (3, 1)
    assert [(item.condition_id, item.state, item.offers) for item in trace.first_blockers] == [
        ("origin", "fail", 1), ("date", "unknown", 2),
    ]
    assert [(item.offers_before, item.offers_after) for item in trace.sequential_funnel] == [
        (4, 3), (3, 1), (1, 1),
    ]


def test_decision_options_compare_group_cost_to_same_currency_median(decide_cfg):
    rows = [
        TourRow(tour={"record_key": f"tour-{price}", "name": f"Tour {price}",
                      "destinations": ["Vũng Tàu"], "duration_days": 2},
                offers=[{"record_key": f"offer-{price}", "price": price,
                         "price_type": "fixed", "currency": "VND", "departure_date": "2027-02-01"}])
        for price in (1_000_000, 2_000_000, 3_000_000)
    ]
    tours = rows_to_snapshots(rows)
    req = Requirement(id=uid("req"), travelers=1, traveler_mix={"adult": 1}, conditions=[
        Condition(id="destination", field="destination", value="Vũng Tàu", strength="hard"),
    ])
    facts = {tour.id: ExtractedTourFacts(tour_id=tour.id, reviewed_fields=["exclusions", "surcharges"])
             for tour in tours}
    comparison = compare(req, tours, decide_cfg, metric_facts=facts)

    assert len(comparison.decision_options) == 3
    for option in comparison.decision_options:
        metric = next(item for item in option.metric_comparisons if item.key == "group_total")
        assert metric.reference_median == 2_000_000
        assert metric.currency == "VND"
        assert metric.state == "observed"
        assert metric.relation in {"favorable", "tradeoff", "similar"}


def test_cost_scenario_recalculates_room_and_age_costs_from_source_values(decide_cfg):
    row = TourRow(
        tour={"record_key": "cost-tour", "name": "Cost tour", "destinations": ["Vũng Tàu"],
              "duration_days": 2, "duration_nights": 1},
        offers=[{"record_key": "cost-offer", "price": 1_000_000, "price_type": "fixed",
                 "currency": "VND", "departure_date": "2027-02-01", "single_supplement": 50_000}],
    )
    tours = rows_to_snapshots([row])
    tour = tours[0]
    req = Requirement(id=uid("req"), travelers=2, traveler_mix={"adult": 2}, conditions=[
        Condition(id="destination", field="destination", value="Vũng Tàu", strength="hard"),
    ])
    facts = {tour.id: ExtractedTourFacts(
        tour_id=tour.id,
        exclusions=[CostExposure(
            name="Phí phòng", obligation="mandatory", amount=100_000, currency="VND",
            unit="per_room", source_field="exclusions", quote="Phí phòng 100.000 VND mỗi phòng",
        )],
        reviewed_fields=["exclusions", "surcharges"],
    )}
    comparison = compare(req, tours, decide_cfg, metric_facts=facts)
    scenario = cost_scenario(comparison, CostScenarioAssumptions(
        travelers=2, traveler_mix={"adult": 2}, rooms=2, single_rooms=1, nights=1,
    ))

    assert scenario.items[0].group_base_calculated == 2_000_000
    assert scenario.items[0].priced_mandatory_extras[0].calculated_total == 200_000
    assert scenario.items[0].priced_mandatory_extras[1].calculated_total == 50_000
    assert scenario.items[0].known_total == 2_250_000
    assert scenario.items[0].state == "observed"
    assert scenario.items[0].evidence
