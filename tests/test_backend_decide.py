"""Decide: hard filter → rank → analyze. Offline, soft stays unknown without LLM."""

import json
from datetime import UTC, datetime, timedelta

import httpx

from backend.data.catalog import FixtureCatalog
from backend.decide.engine import assess_soft_llm, compare
from backend.input.nim import NimClient
from backend.input.pipeline import build_requirement
from backend.models import Condition, Requirement, TourRow, uid
from backend.normalize.snapshots import rows_to_snapshots
from backend.settings import PromptCfg


def _snapshots():
    return rows_to_snapshots(FixtureCatalog().list_tours(10))


def _mock_nim(payload: dict) -> NimClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(payload)}}]})

    return NimClient("key", "model", 9.0,
                     prompt=PromptCfg(system="s", max_tokens=64, temperature=0),
                     transport=httpx.MockTransport(handler))


def test_assess_goes_through_shared_gateway(input_cfg, decide_cfg):
    from backend.models import Condition

    nim = _mock_nim({"scores": [{"tour_id": "dlv-dalat-3n", "condition_id": "s1",
                                 "score": 0.9, "quote": "Langbiang"}]})
    soft = [Condition(id="s1", field="preference", value="thích núi", strength="soft")]
    scores = assess_soft_llm(_snapshots(), soft, nim,
                             prompt=nim.prompt,
                             excerpt_chars=decide_cfg.excerpt_chars,
                             quote_chars=decide_cfg.quote_chars,
                             soft_fields=decide_cfg.soft_fields)
    assert scores[("dlv-dalat-3n", "s1")][0] == 0.9
    assert "Langbiang" in scores[("dlv-dalat-3n", "s1")][1]


def test_assess_receives_only_survivors(input_cfg, decide_cfg):
    seen: list[list[str]] = []

    def spy(ts, soft):
        seen.append([t.id for t in ts])
        return {}

    req = build_requirement("", {"destinations": ["Đà Lạt"]}, cfg=input_cfg)
    req.conditions.append(Condition(
        id="s1", field="preference", value="thích núi", strength="soft"))
    compare(req, _snapshots(), spy, decide_cfg)
    assert seen and seen[0] == ["dlv-dalat-3n"]


def test_gateway_retries_malformed_json_once():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(200, json={"choices": [{"message": {"content": "not json"}}]})
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    nim = NimClient("key", "model", 9.0,
                    prompt=PromptCfg(system="s", max_tokens=64, temperature=0),
                    transport=httpx.MockTransport(handler))
    assert nim.complete_json(system="s", user="u", max_tokens=64, temperature=0) == {}
    assert len(calls) == 2


def test_gateway_raises_after_second_malformed():
    from backend.errors import AppError

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "not json"}}]})

    nim = NimClient("key", "model", 9.0,
                    prompt=PromptCfg(system="s", max_tokens=64, temperature=0),
                    transport=httpx.MockTransport(handler))
    try:
        nim.complete_json(system="s", user="u", max_tokens=64, temperature=0)
        raise AssertionError("should have raised")
    except AppError as exc:
        assert exc.code == "LLM_INVALID_OUTPUT"


def test_compare_uses_soft_scores_in_rank(input_cfg, decide_cfg):
    nim = _mock_nim({"scores": [{"tour_id": "vtr-phuquoc-4n", "condition_id": "s1",
                                 "score": 1.0, "quote": "VinWonders"}]})
    req = build_requirement("", {}, cfg=input_cfg)
    req.conditions.append(Condition(
        id="s1", field="preference", value="thích công viên", strength="soft"))
    comp = compare(req, _snapshots(),
                   lambda ts, soft: assess_soft_llm(ts, soft, nim, nim.prompt, 6000, 300,
                                                    decide_cfg.soft_fields),
                   decide_cfg)
    assert comp.ranked[0].tour_id == "vtr-phuquoc-4n"


def _req(form, input_cfg):
    return build_requirement("", form, cfg=input_cfg)


def test_budget_hard_filter_per_offer(input_cfg, decide_cfg):
    req = _req({"destinations": ["Đà Lạt"], "budget_max": 7_000_000}, input_cfg)
    comp = compare(req, _snapshots(), None, decide_cfg)
    kept = {(c.tour_id, c.offer_id) for c in comp.ranked}
    assert ("dlv-dalat-3n", "dlv-dalat-3n-20270109") in kept
    assert ("dlv-dalat-3n", "dlv-dalat-3n-20261225") not in kept


def test_from_price_above_cap_fails_but_lower_bound_below_cap_is_unknown(input_cfg, decide_cfg):
    req = _req({"destinations": ["Hạ Long"], "budget_max": 1_000_000}, input_cfg)
    comp = compare(req, _snapshots(), None, decide_cfg)
    states = {(e.offer_id, e.condition_id): e.state for e in comp.evaluations}
    budget_id = next(c.id for c in req.conditions if c.field == "budget_max")
    assert states[("sgt-halong-3n-20261227", budget_id)] == "fail"
    assert not comp.ranked

    req = _req({"destinations": ["Hạ Long"], "budget_max": 10_000_000}, input_cfg)
    comp = compare(req, _snapshots(), None, decide_cfg)
    states = {(e.offer_id, e.condition_id): e.state for e in comp.evaluations}
    budget_id = next(c.id for c in req.conditions if c.field == "budget_max")
    assert states[("sgt-halong-3n-20261227", budget_id)] == "unknown"
    assert ("sgt-halong-3n", "sgt-halong-3n-20261227") in {
        (c.tour_id, c.offer_id) for c in comp.ranked}


def test_destination_mismatch_fails(input_cfg, decide_cfg):
    req = _req({"destinations": ["Đà Lạt"]}, input_cfg)
    comp = compare(req, _snapshots(), None, decide_cfg)
    tours = {c.tour_id for c in comp.ranked}
    assert tours == {"dlv-dalat-3n"}


def test_country_match_ignores_origin_endpoints_but_keeps_unknown_places(decide_cfg):
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
        Condition(id="country", field="destination", operator="contains",
                  value="Việt Nam", strength="hard"),
        Condition(id="city", field="destination", operator="contains",
                  value="Tokyo", strength="hard")],
    )
    comp = compare(req, rows_to_snapshots([foreign, unknown]), None, decide_cfg)
    states = {(e.offer_id, e.condition_id): e.state for e in comp.evaluations}
    assert states[("foreign-offer", "country")] == "fail"
    assert states[("partial-offer", "country")] == "unknown"
    assert states[("partial-offer", "city")] == "unknown"
    assert {c.tour_id for c in comp.ranked} == {"partial"}


def test_stale_offer_cannot_pass_hard_budget_or_date(input_cfg, decide_cfg):
    rows = FixtureCatalog().list_tours(10)
    future = datetime.now(UTC) + timedelta(days=2)
    stale_tours = rows_to_snapshots(rows, now=future)
    req = _req({"destinations": ["Đà Lạt"], "budget_max": 8_000_000}, input_cfg)
    req.conditions.append(Condition(id="old-date", field="date_from", value="2026-12-01"))
    comp = compare(req, stale_tours, None, decide_cfg)
    reasons = {(e.offer_id, e.condition_id): e.reason_code for e in comp.evaluations}
    assert reasons[("dlv-dalat-3n-20261225", "h2")] == "FIELD_STALE"
    assert reasons[("dlv-dalat-3n-20261225", "old-date")] == "FIELD_STALE"


def test_any_operator_matches_either(input_cfg, decide_cfg):
    from backend.models import Condition, Requirement, uid

    req = Requirement(id=uid("req"), conditions=[
        Condition(id="h1", field="destination", operator="any",
                  value=["Đà Nẵng", "Hạ Long"], strength="hard")], missing=[])
    comp = compare(req, _snapshots(), None, decide_cfg)
    assert {c.tour_id for c in comp.ranked} == {"sgt-halong-3n"}


def test_rank_prefers_cheaper_on_tie(input_cfg, decide_cfg):
    req = _req({"destinations": ["Đà Lạt"]}, input_cfg)
    comp = compare(req, _snapshots(), None, decide_cfg)
    assert comp.ranked[0].offer_id == "dlv-dalat-3n-20270109"


def test_analysis_surfaces_costs_risks_benefits(input_cfg, decide_cfg):
    req = _req({"destinations": ["Phú Quốc"]}, input_cfg)
    comp = compare(req, _snapshots(), None, decide_cfg)
    text = " ".join(comp.analysis.hidden_costs + comp.analysis.conditions
                    + comp.analysis.risks + comp.analysis.benefits)
    assert "Phụ thu" in text or "phụ thu" in text.lower()
    assert comp.analysis.benefits, "inclusions should surface as benefits"
    assert comp.candidates_considered == 3
