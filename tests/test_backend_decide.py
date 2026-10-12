"""Hard rules, tri-state eligibility, soft verdict ranking and analysis."""

from datetime import UTC, datetime, timedelta

from backend.data.catalog import FixtureCatalog
from backend.decide.engine import compare
from backend.input.pipeline import requirement_from_form
from backend.models import Condition, Requirement, TourRow, uid
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


def test_destination_mismatch_fails(decide_cfg):
    comparison = compare(_req({"destinations": ["Đà Lạt"]}), _snapshots(), decide_cfg)
    assert {item.tour_id for item in comparison.ranked} == {"dlv-dalat-3n"}


def test_unknown_destination_does_not_pass_hard_filter(decide_cfg):
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
    assert states[("partial-offer", "city")] == "unknown"
    assert comparison.ranked == []
    assert [item.tour_id for item in comparison.near_miss] == ["partial"]


def test_country_matching_ignores_origin_endpoints_and_keeps_unknown_places(decide_cfg):
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
        Condition(id="country", field="destination", value="Việt Nam", strength="hard"),
        Condition(id="city", field="destination", value="Tokyo", strength="hard"),
    ])
    comparison = compare(req, rows_to_snapshots([foreign, unknown]), decide_cfg)
    states = {(item.offer_id, item.condition_id): item.state for item in comparison.evaluations}
    assert states[("foreign-offer", "country")] == "fail"
    assert states[("partial-offer", "country")] == "unknown"
    assert states[("partial-offer", "city")] == "unknown"
    assert comparison.ranked == []
    assert {item.tour_id for item in comparison.near_miss} == {"foreign", "partial"}


def test_stale_offer_cannot_pass_hard_budget_or_date(decide_cfg):
    future = datetime.now(UTC) + timedelta(days=2)
    stale_tours = rows_to_snapshots(FixtureCatalog().list_tours(10), now=future)
    req = _req({"destinations": ["Đà Lạt"], "budget_max": 8_000_000})
    req.conditions.append(Condition(id="old-date", field="date_from", value="2026-12-01"))
    comparison = compare(req, stale_tours, decide_cfg)
    reasons = {(item.offer_id, item.condition_id): item.reason_code for item in comparison.evaluations}
    assert reasons[("dlv-dalat-3n-20261225", "h2")] == "FIELD_STALE"
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
