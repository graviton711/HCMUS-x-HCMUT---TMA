"""Hard rules, tri-state eligibility, soft verdict ranking and analysis."""

from datetime import UTC, datetime, timedelta

from backend.data.catalog import FixtureCatalog
from backend.decide.engine import compare
from backend.input.pipeline import requirement_from_form
from backend.models import Condition, OfferSnapshot, Requirement, TourRow, TourSnapshot, uid
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


def test_stale_price_can_pass_budget_while_stale_departure_cannot_pass_date(decide_cfg):
    future = datetime.now(UTC) + timedelta(days=2)
    stale_tours = rows_to_snapshots(
        FixtureCatalog().list_tours(10),
        freshness_seconds={"departure_date": 86400},
        now=future,
    )
    req = _req({"destinations": ["Đà Lạt"], "budget_max": 8_000_000})
    req.conditions.append(Condition(id="old-date", field="date_from", value="2026-12-01"))
    comparison = compare(req, stale_tours, decide_cfg)
    reasons = {(item.offer_id, item.condition_id): item.reason_code for item in comparison.evaluations}
    states = {(item.offer_id, item.condition_id): item.state for item in comparison.evaluations}
    assert states[("dlv-dalat-3n-20261225", "h2")] == "pass"
    assert reasons[("dlv-dalat-3n-20261225", "old-date")] == "FIELD_STALE"


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
