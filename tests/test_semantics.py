"""Semantic gold assertions, independent fixtures, and complete v2 proposal flow."""

import asyncio
import json
from datetime import date, timedelta
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from vi_lunaire import solar_to_lunar

from api.app import create_app
from api.dto import Answer
from api.v2.models import RequirementV2
from api.v2.service import typed_edits
from data_access.fixtures import fixture_registry
from data_access.gateway import DataGateway
from data_access.v2 import GatewayV2, core_requirement
from decision.semantic import evaluate
from decision.v2 import build_comparison
from domain.common import AppError, now
from domain.crawl import Evidence, Fact, OfferSnapshot, SourceResult, Supplier
from domain.crawl_v2 import CrawlResultV2, TourSnapshotV2
from domain.requirements import Message, QuerySpec, SourceReference, UnresolvedValue
from domain.semantic import ConditionV2, QualitativeValue, SemanticRequirement, TemporalValue
from requirements.edits import answer_edits
from requirements.nim import parse_validated
from requirements.semantic import answer_clarification, finalize_v2, normalize_v2
from requirements.service import from_extraction
from requirements.temporal import lunar_date, normalize_temporal, resolve_temporal
from requirements.v2 import (
    InitialExtractionV2,
    RawAnswer,
    RawConditionV2,
    RawTemporal,
    SlotExtractor,
    UpdateExtractionV2,
    coverage_guard,
)

TET = "Tết Nguyên đán năm nay e dự định đi du lịch ghép đoàn bằng xe ô tô từ Hải Phòng đi dọc miền trung vào Đà Nẵng hoặc Tây Nguyên.\nCty nào uy tín và dv tốt, giá hợp lý, tour có các điểm đẹp gần gũi thiên nhiên e tham khảo ạ.\nTừ 27/12 âm đến mùng 4 Tết ạ."


def test_numeric_budget_party_and_duplicate_date_are_repaired_together():
    message = Message(
        id="m_budget",
        received_at=now().isoformat(),
        text="Nhật Bản ngày 2026-11-03, đi 1 người lớn, ngân sách tối đa 30 triệu VND mỗi người lớn cho giá tour.",
    )
    date_condition = dict(
        id="date",
        field="departure_date",
        operator="eq",
        strength="hard",
        raw_values=["2026-11-03"],
        quote="ngày 2026-11-03",
    )
    base = dict(preference_updates=[], reference_urls_update=None, notes_update=None)
    bad = InitialExtractionV2(**base, conditions=[date_condition, dict(date_condition, id="budget")])
    good = InitialExtractionV2(
        **base,
        conditions=[
            date_condition,
            dict(
                id="dest",
                field="destinations",
                operator="contains",
                strength="hard",
                raw_values=["Nhật Bản"],
                quote="Nhật Bản",
            ),
            dict(
                id="budget",
                field="estimated_cost",
                operator="lte",
                strength="hard",
                raw_values=["30 triệu"],
                quote="ngân sách tối đa 30 triệu VND mỗi người lớn cho giá tour",
            ),
        ],
        party=dict(adults_raw="1", adults_quote="đi 1 người lớn", children=None, rooming_quote=None),
    )

    class BudgetNim:
        def __init__(self):
            self.calls = []

        async def extract(self, _message, previous=None, *, feedback=None):
            self.calls.append(feedback)
            return (bad if feedback is None else good), {}

        extract_v2 = extract

    nim = BudgetNim()
    parsed, metrics = asyncio.run(
        parse_validated(
            SlotExtractor(nim),
            message,
            requirement_id="budget_regression",
            timezone="Asia/Ho_Chi_Minh",
            mode="discover",
            targets=[],
        )
    )
    assert metrics["repair_used"] and len(nim.calls) == 2
    assert "estimated_cost" in nim.calls[1] and "party.adults_raw" in nim.calls[1]
    assert "trùng" in nim.calls[1]
    assert parsed.party.adults == 1
    assert len([c for c in parsed.conditions if c.field == "departure_date"]) == 1
    assert next(c for c in parsed.conditions if c.field == "estimated_cost").value.amount == 30000000


@pytest.mark.parametrize("text", ["giá hợp lý", "không quan tâm ngân sách 30 triệu", "không có 2 người lớn"])
def test_omission_guard_does_not_invent_numeric_slots(text):
    raw = InitialExtractionV2(preference_updates=[], reference_urls_update=None, notes_update=None)
    if text == "giá hợp lý":
        raw.conditions = [
            RawConditionV2(
                id="value", field="price_value", operator="prefer", strength="soft", raw_values=[], quote=text
            )
        ]
    coverage_guard(raw, Message(id="m_guard", text=text, received_at=now().isoformat()), None)


CLARIFIED = (
    TET
    + "\nĐây là khoảng thời gian tôi có thể đi. Tour có thể khởi hành bất kỳ ngày nào từ 27/12 âm trở đi và phải kết thúc không muộn hơn mùng 4 Tết."
)


def extraction(text=TET):
    semantics = "availability" if "có thể đi" in text else "ambiguous"
    rows = [
        ("origin", "departure_origin", "in", "hard", ["Hải Phòng"], "Hải Phòng"),
        ("transport", "transport", "in", "hard", ["xe ô tô"], "xe ô tô từ Hải Phòng"),
        (
            "dest",
            "destinations",
            "contains_any",
            "hard",
            ["Đà Nẵng", "Tây Nguyên"],
            "Đà Nẵng hoặc Tây Nguyên",
        ),
        ("group", "tour_type", "in", "hard", ["ghép đoàn"], "ghép đoàn"),
        ("route", "route", "contains_all", "unresolved", ["miền trung"], "đi dọc miền trung"),
        ("reputation", "supplier_reputation", "prefer", "soft", [], "uy tín"),
        ("service", "service_quality", "prefer", "soft", [], "dv tốt"),
        ("value", "price_value", "prefer", "soft", [], "giá hợp lý"),
        ("nature", "nature", "prefer", "soft", [], "gần gũi thiên nhiên"),
    ]
    cs = [
        RawConditionV2(id=cid, field=field, operator=op, strength=strength, raw_values=values, quote=quote)
        for cid, field, op, strength, values, quote in rows
    ]
    for cid, field, value, quote in [
        ("start", "departure_date", "27/12 âm", "Từ 27/12 âm đến mùng 4 Tết ạ."),
        ("end", "return_date", "mùng 4 Tết", "Từ 27/12 âm đến mùng 4 Tết ạ."),
    ]:
        cs.append(
            RawConditionV2(
                id=cid,
                field=field,
                operator="gte"
                if semantics == "availability" and field == "departure_date"
                else "lte"
                if semantics == "availability"
                else "eq",
                strength="hard",
                raw_values=[value],
                quote=quote,
                temporal=RawTemporal(calendar="vietnamese_lunar", semantics=semantics, group_id="tet_window"),
            )
        )
    return InitialExtractionV2(
        conditions=cs, preference_updates=[], reference_urls_update=None, notes_update=None
    )


def parsed(text=TET):
    message = Message(id="msg_gold", text=text, received_at="2026-10-07T14:00:00+00:00")
    raw = extraction(text)
    coverage_guard(raw, message, None)
    r = from_extraction(
        extraction=raw,
        message=message,
        requirement_id="req_gold",
        mode="discover",
        timezone="Asia/Ho_Chi_Minh",
        targets=[],
        requirement_model=SemanticRequirement,
        normalizer=normalize_v2,
        condition_model=ConditionV2,
        finalizer=finalize_v2,
    )
    return RequirementV2.model_validate(
        {**r.model_dump(), "schema_version": "2.0-draft", "input_kind": "text"}
    )


def answer(r, reason, value):
    q = next(q for q in r.clarifications if q.reason_code == reason)
    return answer_clarification(
        r, q, value, SourceReference(kind="form", field_path=q.field_path, submitted_value=value)
    )


def ready():
    r = answer(parsed(CLARIFIED), "DATE_YEAR_REQUIRED", {"holiday_year": 2027})
    return answer(r, "CONDITION_STRENGTH_REQUIRED", "soft")


def test_model_cannot_soften_available_window_bounds():
    raw = extraction(CLARIFIED)
    for c in raw.conditions:
        if c.temporal:
            c.strength = "soft"
    message = Message(id="m", text=CLARIFIED, received_at=now().isoformat())
    r = from_extraction(
        extraction=raw,
        message=message,
        requirement_id="req_dates",
        mode="discover",
        timezone="Asia/Ho_Chi_Minh",
        targets=[],
        requirement_model=SemanticRequirement,
        normalizer=normalize_v2,
        condition_model=ConditionV2,
        finalizer=finalize_v2,
    )
    dates = [c for c in r.conditions if isinstance(c.value, TemporalValue)]
    assert [c.strength for c in dates] == ["hard", "hard"]
    assert [c.operator for c in dates] == ["gte", "lte"]
    assert all(any(s.rule == "date_bound_strength_v1" for s in c.sources) for c in dates)
    assert next(q for q in r.clarifications if q.reason_code == "DATE_YEAR_REQUIRED").blocking


@pytest.mark.parametrize(
    "text,expected", [("Ưu tiên khởi hành 10/11/2027", "soft"), ("Khởi hành 10/11/2027", "hard")]
)
def test_gregorian_date_strength_uses_user_cue(text, expected):
    raw = RawConditionV2(
        id="date",
        field="departure_date",
        operator="eq",
        strength="soft",
        raw_values=["10/11/2027"],
        quote=text,
    )
    c = normalize_v2(raw, Message(id="m", text=text, received_at=now().isoformat()), "Asia/Ho_Chi_Minh")
    assert c.strength == expected and c.value.value == "2027-11-10"


def vn_crawl():
    at = now().isoformat()
    supplier_id = fixture_registry()[0].supplier_id
    evidence = []

    def fact(value, name, *, scope=None, snapshot="vn_tour"):
        eid = f"ev_{snapshot}_{name}"
        evidence.append(
            Evidence(
                id=eid,
                snapshot_id=snapshot,
                url="https://tour-demo.invalid/tour-vn",
                publisher=supplier_id,
                method="synthetic_fixture",
                locator=name,
                raw_quote=f"Synthetic {name}: {value}",
                observed_at=at,
            )
        )
        return Fact(
            value=value,
            raw_value=f"Synthetic {name}: {value}",
            data_state="present",
            verification="supplier_published",
            completeness="complete",
            observed_at=at,
            evidence_ids=[eid],
            scope=scope,
        )

    tour = TourSnapshotV2(
        snapshot_id="vn_tour",
        tour_id="vn_tour_id",
        supplier_id=supplier_id,
        canonical_url="https://tour-demo.invalid/tour-vn",
        title="Synthetic Hải Phòng – Đà Nẵng",
        observed_at=at,
        fields={
            "destinations": fact(["city:vn:danang"], "destinations"),
            "departure_origin": fact("city:vn:haiphong", "departure_origin"),
            "transport": fact(["coach"], "transport", scope="main_journey"),
        },
        semantic_fields={
            "tour_type": fact("join_group", "tour_type"),
            "route": fact(["region:vn:central"], "route", scope="itinerary"),
            "nature": fact(["forest"], "nature", scope="itinerary"),
        },
    )
    offer = OfferSnapshot(
        snapshot_id="vn_offer",
        offer_id="offer_id",
        tour_snapshot_id=tour.snapshot_id,
        fields={
            "departure_date": fact("2027-02-04", "departure_date", snapshot="vn_offer"),
            "return_date": fact("2027-02-08", "return_date", snapshot="vn_offer"),
        },
    )
    return CrawlResultV2(
        request_id="crawl_vn",
        origin="synthetic",
        suppliers=[Supplier(supplier_id=supplier_id, display_name="Synthetic provider")],
        tours=[tour],
        offers=[offer],
        evidence=evidence,
        source_results=[
            SourceResult(
                source_id="demo",
                status="ok",
                tour_snapshot_ids=[tour.snapshot_id],
                offer_snapshot_ids=[offer.snapshot_id],
            )
        ],
    )


def test_original_tet_preserves_every_intent_and_asks_actual_ambiguities():
    r = parsed()
    assert len(r.conditions) == 11
    assert {c.field for c in r.conditions if c.strength == "soft"} == {
        "supplier_reputation",
        "service_quality",
        "price_value",
        "nature",
    }
    assert (
        next(c for c in r.conditions if c.field == "departure_origin").value.members[0].entity_id
        == "city:vn:haiphong"
    )
    dest = next(c for c in r.conditions if c.field == "destinations")
    assert dest.operator == "contains_any"
    assert {m.entity_id for m in dest.value.members} == {"city:vn:danang", "region:vn:central_highlands"}
    assert (
        next(c for c in r.conditions if c.field == "transport").value.members[0].entity_id == "motor_vehicle"
    )
    assert {q.reason_code for q in r.clarifications} == {
        "DATE_YEAR_REQUIRED",
        "TEMPORAL_SEMANTICS_REQUIRED",
        "CONDITION_STRENGTH_REQUIRED",
    }
    assert len([q for q in r.clarifications if q.reason_code == "DATE_YEAR_REQUIRED"]) == 1
    assert r.party.adults is None and not any(c.field == "estimated_cost" for c in r.conditions)
    assert r.readiness.can_collect_data and not r.readiness.can_evaluate_hard_constraints


def test_year_and_semantics_answers_update_both_boundaries_and_preserve_other_conditions():
    r = parsed()
    original = {c.id: c for c in r.conditions if not isinstance(c.value, TemporalValue)}
    r = answer(r, "DATE_YEAR_REQUIRED", {"holiday_year": 2027})
    assert all(c.value.resolved_date is None for c in r.conditions if isinstance(c.value, TemporalValue))
    r = answer(r, "TEMPORAL_SEMANTICS_REQUIRED", {"semantics": "availability"})
    dates = {c.field: c for c in r.conditions if isinstance(c.value, TemporalValue)}
    assert (
        dates["departure_date"].operator,
        dates["departure_date"].value.year,
        dates["departure_date"].value.resolved_date,
    ) == ("gte", 2026, "2027-02-03")
    assert (
        dates["return_date"].operator,
        dates["return_date"].value.year,
        dates["return_date"].value.resolved_date,
    ) == ("lte", 2027, "2027-02-09")
    assert original == {c.id: c for c in r.conditions if not isinstance(c.value, TemporalValue)}
    assert not any(q.reason_code == "DATE_YEAR_REQUIRED" for q in r.clarifications)


def test_clarified_input_keeps_availability_bounds_before_year_is_known():
    r = parsed(CLARIFIED)
    dates = {c.field: c for c in r.conditions if isinstance(c.value, TemporalValue)}
    assert dates["departure_date"].operator == "gte" and dates["return_date"].operator == "lte"
    assert not any(q.reason_code == "TEMPORAL_SEMANTICS_REQUIRED" for q in r.clarifications)
    assert all(c.value.holiday_year is None for c in dates.values())


@pytest.mark.parametrize(
    "value", [2027, {"year": 2027}, {"holiday_year": True}, {"holiday_year": 1999}, {"holiday_year": 2100}]
)
def test_year_answer_rejects_wrong_semantics_type_and_range(value):
    with pytest.raises(AppError, match="Năm"):
        answer(parsed(CLARIFIED), "DATE_YEAR_REQUIRED", value)


def test_exact_semantics_is_distinct_from_availability():
    r = answer(parsed(), "TEMPORAL_SEMANTICS_REQUIRED", {"semantics": "exact"})
    r = answer(r, "DATE_YEAR_REQUIRED", {"holiday_year": 2027})
    assert all(c.operator == "eq" for c in r.conditions if isinstance(c.value, TemporalValue))


@pytest.mark.parametrize(
    "case", json.loads((Path(__file__).parent / "fixtures/lunar-reference.json").read_text())["cases"]
)
def test_lunar_converter_independent_date_anchors(case):
    assert lunar_date(*case["lunar"]).isoformat() == case["solar"]


@pytest.mark.parametrize("year", [2001, 2023, 2024, 2025, 2026, 2027, 2033, 2098])
def test_calendar_roundtrip_across_full_solar_year_including_leap_boundaries(year):
    day = date(year, 1, 1)
    while day.year == year:
        lunar = solar_to_lunar(day.year, day.month, day.day)
        assert lunar_date(lunar.year, lunar.month, lunar.day, lunar.leap) == day
        day += timedelta(days=1)


def test_nonexistent_lunar_leap_month_and_day_are_rejected():
    with pytest.raises(ValueError):
        lunar_date(2026, 2, 1, True)
    with pytest.raises(ValueError):
        lunar_date(2026, 2, 30)  # This month has 29 days.


def test_lunar_month_with_leap_variant_needs_a_choice():
    v = TemporalValue(
        raw="1/2 âm",
        calendar="vietnamese_lunar",
        group_id="one",
        role="single",
        semantics="single",
        day=1,
        month=2,
        year=2023,
        year_origin="explicit",
        reason="DATE_YEAR_REQUIRED",
    )
    unresolved = resolve_temporal(v)
    assert unresolved.reason == "LUNAR_LEAP_REQUIRED"
    assert resolve_temporal(v.model_copy(update={"leap": True})).resolved_date == "2023-03-22"


def test_lunar_quote_cannot_be_sent_to_gregorian_normalizer():
    raw = (
        extraction()
        .conditions[-2]
        .model_copy(
            update={"temporal": RawTemporal(calendar="gregorian", semantics="ambiguous", group_id="bad")}
        )
    )
    with pytest.raises(AppError, match="Lịch âm"):
        normalize_temporal(raw, Message(id="m", text=TET, received_at="2026-10-07T14:00:00Z"))


@pytest.mark.parametrize(
    "field", ["tour_type", "route", "supplier_reputation", "service_quality", "price_value", "nature"]
)
def test_coverage_guard_detects_explicit_omission(field):
    raw = extraction()
    raw.conditions = [c for c in raw.conditions if c.field != field]
    with pytest.raises(AppError, match="bỏ sót") as exc:
        coverage_guard(raw, Message(id="m", text=TET, received_at="2026-10-07T14:00:00Z"), None)
    assert field in exc.value.repair_hint


def test_negative_qualitative_mention_does_not_force_a_preference():
    raw = InitialExtractionV2(
        conditions=[
            RawConditionV2(
                id="d",
                field="destinations",
                operator="contains",
                strength="hard",
                raw_values=["Đà Nẵng"],
                quote="Đà Nẵng",
            )
        ],
        preference_updates=[],
        reference_urls_update=None,
        notes_update=None,
    )
    coverage_guard(
        raw,
        Message(id="m", text="Đi Đà Nẵng. Không cần công ty uy tín.", received_at="2026-10-07T14:00:00Z"),
        None,
    )


def test_missing_soft_metrics_do_not_block_confirm_or_turn_into_zero_score():
    r, crawl = ready(), vn_crawl()
    assert r.readiness.can_evaluate_hard_constraints
    assert len([i for i in r.issues if i.reason_code == "METRIC_UNSUPPORTED"]) == 3
    result = build_comparison("cmp", r, crawl, fixture_registry(), now().isoformat())
    assert len(result["recommendations"]["candidate_ids"]) == 1
    item = result["recommendations"]["items"][0]
    assert item["score"] == 1 and item["coverage"] == pytest.approx(0.4)
    assert {c["condition_id"] for c in item["contributions"] if c["utility"] is None} == {
        "reputation",
        "service",
        "value",
    }
    evaluations = {e["field"]: e for e in result["evaluations"]}
    assert evaluations["supplier_reputation"]["status"] == "unknown"
    assert evaluations["nature"]["status"] == "pass"


def test_unsupported_hard_qualitative_stays_a_backend_issue():
    r = ready()
    c = next(c for c in r.conditions if c.field == "supplier_reputation")
    raw = c.model_copy(update={"strength": "hard", "operator": "requires"})
    from requirements.service import conjunction

    cs = [raw if item.id == c.id else item for item in r.conditions]
    r = finalize_v2(
        r.model_copy(
            update={
                "conditions": cs,
                "hard_tree": conjunction(cs, False),
                "preference_tree": conjunction(cs, True),
            }
        )
    )
    assert not r.readiness.can_evaluate_hard_constraints
    assert any(i.blocking and i.reason_code == "METRIC_UNSUPPORTED" for i in r.issues)
    assert not any(q.field_path.startswith(f"conditions.{c.id}") for q in r.clarifications)


@pytest.mark.parametrize(
    "operator,actual,completeness,expected",
    [
        ("contains_any", ["city:vn:danang"], "complete", "pass"),
        ("contains_any", ["country:jp"], "complete", "unknown"),
        ("contains_all", ["city:vn:danang"], "complete", "unknown"),
        ("contains_all", ["country:jp"], "complete", "fail"),
        ("excludes", ["city:vn:danang"], "complete", "fail"),
        ("excludes", ["country:jp"], "complete", "unknown"),
    ],
)
def test_partial_entity_group_three_valued_logic(operator, actual, completeness, expected):
    raw = RawConditionV2(
        id="partial",
        field="destinations",
        operator=operator,
        strength="hard",
        raw_values=["Đà Nẵng", "Atlantis"],
        quote="Đà Nẵng hoặc Atlantis",
    )
    c = normalize_v2(
        raw, Message(id="m", text=raw.quote, received_at="2026-10-07T14:00:00Z"), "Asia/Ho_Chi_Minh"
    )
    crawl = vn_crawl()
    crawl.tours[0].fields["destinations"] = (
        crawl.tours[0]
        .fields["destinations"]
        .model_copy(update={"value": actual, "completeness": completeness})
    )
    assert len(c.value.members) == 2 and c.value.members[1].status == "catalog_missing"
    assert (
        evaluate(
            c, crawl.tours[0], crawl.offers[0], ready().party, fixture_registry()[0], now().isoformat(), True
        )["status"]
        == expected
    )


def test_local_transfer_cannot_pass_main_journey_transport():
    r, crawl = ready(), vn_crawl()
    c = next(c for c in r.conditions if c.field == "transport")
    crawl.tours[0].fields["transport"].scope = "local_transfers"
    e = evaluate(c, crawl.tours[0], crawl.offers[0], r.party, fixture_registry()[0], now().isoformat(), True)
    assert e["status"] == "unknown" and e["reason_code"] == "FIELD_SCOPE_INCOMPATIBLE"
    crawl.tours[0].fields["transport"].scope = "main_journey"
    assert (
        evaluate(c, crawl.tours[0], crawl.offers[0], r.party, fixture_registry()[0], now().isoformat(), True)[
            "status"
        ]
        == "pass"
    )


def test_legacy_query_adapter_preserves_markers_and_does_not_send_raw_text():
    r = ready()
    raw = QuerySpec.from_requirement(core_requirement(r, "discover", [])).model_dump(mode="json")
    assert len(raw["conditions"]) == len(r.conditions)
    assert next(c for c in raw["conditions"] if c["id"] == "transport")["field"] == "unsupported"
    assert next(c for c in raw["conditions"] if c["id"] == "dest")["value"]["items"] == [
        "city:vn:danang",
        "region:vn:central_highlands",
    ]
    assert "Tết" not in json.dumps(raw, ensure_ascii=False)


def test_semantic_fact_evidence_must_belong_to_same_snapshot():
    crawl = vn_crawl().model_dump()
    crawl["tours"][0]["semantic_fields"]["nature"]["evidence_ids"] = ["ev_vn_offer_departure_date"]
    with pytest.raises(ValidationError, match="Semantic fact/evidence"):
        CrawlResultV2.model_validate(crawl)


def test_no_unreviewed_trust_metric_can_be_submitted():
    with pytest.raises(ValidationError, match="reviewed"):
        QualitativeValue(concept="supplier_reputation", raw="uy tín", metric_policy="made_up_score")


class TetNim:
    async def extract(self, message, previous=None, *, feedback=None):
        if previous:
            q = next(q for q in previous.clarifications if q.reason_code == "DATE_YEAR_REQUIRED")
            return UpdateExtractionV2(
                answers=[RawAnswer(clarification_id=q.id, value_raw="2027", quote="Tết 2027")],
                preference_updates=[],
                reference_urls_update=None,
                notes_update=None,
            ), {}
        return extraction(message.text), {}

    extract_v2 = extract


def finish(app):
    for _ in range(6):
        if not asyncio.run(app.state.worker.run_once()):
            break


def test_api_tet_proposal_targeted_answers_cas_confirm_and_persistence(settings):
    settings.data_provider = "http"
    settings.crawler_url = "https://crawler.invalid/collect"

    def handler(request):
        payload = vn_crawl().model_dump(mode="json")
        payload["origin"] = "source"
        payload["request_id"] = json.loads(request.content)["request_id"]
        for evidence in payload["evidence"]:
            evidence["method"] = "json"
        return httpx.Response(200, json=payload)

    gateway = DataGateway(settings, registry=fixture_registry(), transport=httpx.MockTransport(handler))
    app = create_app(settings, nim=TetNim(), gateway=gateway)
    with TestClient(app) as client:
        token = client.post("/v2/sessions").json()["data"]["token"]
        client.headers["Authorization"] = f"Bearer {token}"
        accepted = client.post(
            "/v2/requirements", json={"input": {"kind": "text", "text": CLARIFIED}}
        ).json()["data"]
        finish(app)
        p = client.get(f"/v2/proposals/{accepted['proposal_id']}").json()["data"]
        assert len(p["preview"]["conditions"]) == 11
        # Natural-language year answer binds the group rather than re-parsing old dates.
        body = {
            "expected_revision": 0,
            "proposal_id": p["id"],
            "expected_proposal_version": p["version"],
            "input": {"kind": "message", "text": "Tết 2027"},
        }
        response = client.post(f"/v2/requirements/{accepted['requirement_id']}/proposals", json=body)
        assert response.status_code == 202, response.text
        finish(app)
        p = client.get(f"/v2/proposals/{p['id']}").json()["data"]
        q = next(q for q in p["clarifications"] if q["reason_code"] == "CONDITION_STRENGTH_REQUIRED")
        body.update(
            expected_proposal_version=p["version"],
            input={
                "kind": "structured",
                "edits": [{"op": "answer_clarification", "clarification_id": q["id"], "answer": "soft"}],
            },
        )
        response = client.post(f"/v2/requirements/{accepted['requirement_id']}/proposals", json=body)
        assert response.status_code == 200, response.text
        updated = response.json()["data"]
        assert (
            client.post(f"/v2/requirements/{accepted['requirement_id']}/proposals", json=body).status_code
            == 409
        )
        committed = client.post(
            f"/v2/proposals/{p['id']}/confirm",
            json={"expected_revision": 0, "expected_proposal_version": updated["version"]},
        )
        assert committed.status_code == 200, committed.text
        r = client.get(f"/v2/requirements/{accepted['requirement_id']}").json()["data"]
        assert r["revision"] == 1 and r["readiness"]["can_evaluate_hard_constraints"]
        assert (
            next(c for c in r["conditions"] if c["id"] == "start")["value"]["resolved_date"] == "2027-02-03"
        )
        assert len(r["issues"]) == 3
        accepted_comparison = client.post(
            "/v2/comparisons", json={"requirement_id": r["id"], "revision": 1}
        ).json()["data"]
        finish(app)
        comparison = client.get(f"/v2/comparisons/{accepted_comparison['comparison_id']}").json()["data"]
        assert comparison["status"] == "succeeded", comparison
        result = comparison["result"]
        item = result["recommendations"]["items"][0]
        assert item["score"] == 1 and item["coverage"] == pytest.approx(0.4)
        assert next(e for e in result["evaluations"] if e["field"] == "tour_type")["status"] == "pass"
        replay = client.post(
            "/v2/comparisons",
            json={
                "requirement_id": r["id"],
                "revision": 1,
                "previous_comparison_id": accepted_comparison["comparison_id"],
            },
        ).json()["data"]
        finish(app)
        reused = client.get(f"/v2/comparisons/{replay['comparison_id']}").json()["data"]
        assert reused["status"] == "succeeded" and reused["result"]["recommendations"]["items"][0][
            "coverage"
        ] == pytest.approx(0.4)


@pytest.mark.parametrize(
    "field,target,actual",
    [("transport", "xe khách", ["motor_vehicle"]), ("destinations", "Đà Nẵng", ["country:vn"])],
)
def test_coarse_parent_fact_cannot_disprove_specific_target(field, target, actual):
    raw = RawConditionV2(
        id="granularity",
        field=field,
        operator="in" if field == "transport" else "contains",
        strength="hard",
        raw_values=[target],
        quote=target,
    )
    c = normalize_v2(raw, Message(id="m", text=target, received_at=now().isoformat()), "Asia/Ho_Chi_Minh")
    crawl = vn_crawl()
    crawl.tours[0].fields[field].value = actual
    assert (
        evaluate(
            c, crawl.tours[0], crawl.offers[0], ready().party, fixture_registry()[0], now().isoformat(), True
        )["status"]
        == "unknown"
    )


@pytest.mark.parametrize(
    "operator,actual,expected",
    [
        ("contains", ["city:vn:unreviewed"], "unknown"),
        ("excludes", ["city:vn:unreviewed"], "unknown"),
        ("contains", ["city:vn:unreviewed", "city:vn:danang"], "pass"),
        ("excludes", ["city:vn:unreviewed", "city:vn:danang"], "fail"),
    ],
)
def test_unknown_actual_catalog_id_cannot_prove_non_match(operator, actual, expected):
    c = next(c for c in ready().conditions if c.id == "dest")
    c = c.model_copy(
        update={"operator": operator, "value": c.value.model_copy(update={"members": c.value.members[:1]})}
    )
    crawl = vn_crawl()
    crawl.tours[0].fields["destinations"].value = actual
    evaluation = evaluate(
        c, crawl.tours[0], crawl.offers[0], ready().party, fixture_registry()[0], now().isoformat(), True
    )
    assert evaluation["status"] == expected
    if expected == "unknown":
        assert evaluation["reason_code"] == "ENTITY_FACT_CATALOG_MISSING"


@pytest.mark.parametrize("value", [["join_group"], {"type": "join_group"}, 1])
def test_tour_type_invalid_type_is_validation_error(value):
    payload = vn_crawl().model_dump(mode="json")
    payload["tours"][0]["semantic_fields"]["tour_type"]["value"] = value
    with pytest.raises(ValidationError, match="Invalid tour type"):
        CrawlResultV2.model_validate(payload)


def test_generation_quotes_and_minimum_are_bound_to_input_fields():
    from requirements.v2 import generation_schema

    message = Message(id="m", text=TET, received_at=now().isoformat())
    schema = generation_schema(InitialExtractionV2, message)
    assert schema["properties"]["conditions"]["minItems"] == 6
    assert all(
        q in TET and TET.count(q) == 1 and "thiên nhiên" in q
        for q in schema["$defs"]["RawNatureV2"]["properties"]["quote"]["enum"]
    )
    assert "enum" not in schema["$defs"]["RawDepartureOriginV2"]["properties"]["quote"]
    assert all(q in TET for q in schema["$defs"]["RawDepartureDateV2"]["properties"]["quote"]["enum"])


def test_v2_one_repair_has_draft_and_all_quote_failures():
    class RepairNim(TetNim):
        calls = []

        async def extract(self, message, previous=None, *, feedback=None):
            self.calls.append(feedback)
            raw = extraction(message.text)
            if not feedback:
                raw.conditions[0].quote = "BAD_ORIGIN_QUOTE"
                raw.conditions[1].quote = "BAD_TRANSPORT_QUOTE"
            return raw, {}

        extract_v2 = extract

    nim = RepairNim()
    r, metrics = asyncio.run(
        parse_validated(
            SlotExtractor(nim),
            Message(id="m", text=TET, received_at=now().isoformat()),
            requirement_id="repair",
            mode="discover",
            timezone="Asia/Ho_Chi_Minh",
            targets=[],
            requirement_model=SemanticRequirement,
            condition_model=ConditionV2,
            normalizer=normalize_v2,
            finalizer=finalize_v2,
            batch_validation=True,
        )
    )
    assert len(nim.calls) == 2 and metrics["repair_used"] and len(r.conditions) == 11
    assert (
        "BAD_ORIGIN_QUOTE" in nim.calls[1]
        and "BAD_TRANSPORT_QUOTE" in nim.calls[1]
        and "INVALID_DRAFT_TO_CORRECT" in nim.calls[1]
    )


def test_price_phai_chang_is_soft_and_mandatory_cue_is_not_clipped():
    for field, text, quote, expected in [
        ("price_value", "Ưu tiên giá phải chăng", "giá phải chăng", "soft"),
        ("supplier_reputation", "Công ty bắt buộc uy tín", "uy tín", "hard"),
    ]:
        raw = RawConditionV2(id="quality", field=field, operator="prefer", strength="soft", quote=quote)
        c = normalize_v2(raw, Message(id="m", text=text, received_at=now().isoformat()), "Asia/Ho_Chi_Minh")
        assert c.strength == expected and c.sources[-1].rule == "qualitative_strength_default_v1"


def test_literal_tet_window_does_not_trust_model_exact_metadata():
    raw = extraction()
    for c in raw.conditions:
        if c.temporal:
            c.temporal.semantics = "exact"
            c.temporal.group_id = None
    message = Message(id="m", text=TET, received_at=now().isoformat())
    dates = [normalize_v2(c, message, "Asia/Ho_Chi_Minh") for c in raw.conditions if c.temporal]
    assert all(c.value.semantics == "ambiguous" and c.value.group_id == "tet_window" for c in dates)


def test_pure_clarification_generation_prevents_reextraction_and_bounds_ids():
    from requirements.v2 import clarification_only, generation_schema

    previous = parsed()
    message = Message(
        id="m",
        text="Tết 2027. Đây là khoảng thời gian tôi có thể đi. Đi dọc miền Trung chỉ là ưu tiên.",
        received_at=now().isoformat(),
    )
    assert clarification_only(message, previous)
    schema = generation_schema(UpdateExtractionV2, message, previous)
    assert schema["properties"]["operations"]["maxItems"] == 0
    assert schema["properties"]["answers"]["minItems"] == 3
    assert set(schema["$defs"]["RawAnswer"]["properties"]["clarification_id"]["enum"]) == {
        q.id for q in previous.clarifications
    }
    assert not clarification_only(
        message.model_copy(update={"text": message.text + " Thêm Huế vào điểm đến."}), previous
    )
    year_only = generation_schema(
        UpdateExtractionV2, message.model_copy(update={"text": "Tết 2027"}), previous
    )
    assert year_only["properties"]["answers"]["minItems"] == 1


def test_duplicate_and_stale_typed_answers_are_rejected():
    from api.v2.models import TypedEdit

    r = parsed(CLARIFIED)
    q = next(q for q in r.clarifications if q.reason_code == "DATE_YEAR_REQUIRED")
    edit = TypedEdit(op="answer_clarification", clarification_id=q.id, answer={"holiday_year": 2027})
    with pytest.raises(AppError, match="trùng"):
        typed_edits(r, [edit, edit])
    edited = typed_edits(r, [edit])
    with pytest.raises(AppError, match="Clarification"):
        typed_edits(edited, [edit])


def test_v1_year_answer_never_interprets_lunar_text_as_gregorian():
    from conftest import condition, requirement

    r = requirement(
        [
            condition("destinations", {"kind": "set", "items": ["country:vn"]}, "contains", cid="d"),
            condition(
                "departure_date",
                UnresolvedValue(raw="27/12 âm", reason="DATE_NEEDS_CLARIFICATION"),
                cid="day",
            ),
        ]
    )
    q = next(q for q in r.clarifications if q.reason_code == "DATE_YEAR_REQUIRED")
    with pytest.raises(AppError) as exc:
        answer_edits(r, [Answer(clarification_id=q.id, value=2027)])
    assert exc.value.code == "LUNAR_DATE_REQUIRES_V2"


@pytest.mark.parametrize(
    "text,quote,field,operator",
    [
        ("Đi Nhật", "Đi Nhật", "nature", "prefer"),
        ("Không cần thiên nhiên", "thiên nhiên", "nature", "prefer"),
        ("Không cần thiên nhiên", "Không cần thiên nhiên", "nature", "excludes"),
        ("Không thích tour thiên nhiên", "thiên nhiên", "nature", "prefer"),
        ("Không muốn công ty uy tín", "uy tín", "supplier_reputation", "prefer"),
    ],
)
def test_qualitative_invention_and_clipped_negation_are_rejected(text, quote, field, operator):
    raw = RawConditionV2(id="q", field=field, operator=operator, strength="soft", raw_values=[], quote=quote)
    with pytest.raises(AppError) as exc:
        normalize_v2(raw, Message(id="m", text=text, received_at=now().isoformat()), "Asia/Ho_Chi_Minh")
    assert exc.value.code == "LLM_INVALID_OUTPUT"


def test_unicode_grounding_and_negative_qualitative_are_preserved():
    import unicodedata

    text = unicodedata.normalize("NFD", "  Không thích tour thiên nhiên. Ưu tiên giá hợp lý.")
    quote = unicodedata.normalize("NFD", "Không thích tour thiên nhiên")
    raw = RawConditionV2(id="q", field="nature", operator="excludes", strength="soft", quote=quote)
    c = normalize_v2(raw, Message(id="m", text=text, received_at=now().isoformat()), "Asia/Ho_Chi_Minh")
    assert c.operator == "excludes" and c.sources[0].quote == quote


def test_all_unobserved_preferences_score_null():
    result = build_comparison(
        "all_missing",
        ready(),
        vn_crawl().model_copy(
            update={
                "tours": [
                    vn_crawl()
                    .tours[0]
                    .model_copy(
                        update={
                            "semantic_fields": {"tour_type": vn_crawl().tours[0].semantic_fields["tour_type"]}
                        }
                    )
                ]
            }
        ),
        fixture_registry(),
        now().isoformat(),
    )
    item = result["recommendations"]["items"][0]
    assert item["score"] is None and item["coverage"] == 0


def test_partial_or_query_never_narrows_to_known_branch():
    r = ready()
    raw = RawConditionV2(
        id="dest",
        field="destinations",
        operator="contains_any",
        strength="hard",
        raw_values=["Đà Nẵng", "Atlantis"],
        quote="Đà Nẵng hoặc Atlantis",
    )
    c = normalize_v2(raw, Message(id="m", text=raw.quote, received_at=now().isoformat()), r.timezone)
    message = Message(id="m", text=raw.quote, received_at=now().isoformat())
    r = finalize_v2(
        r.model_copy(
            update={
                "conditions": [c if old.id == "dest" else old for old in r.conditions],
                "issues": [],
                "messages": [*r.messages, message],
            }
        )
    )
    query = QuerySpec.from_requirement(core_requirement(r, "discover", []))
    dest = next(c for c in query.conditions if c.id == "dest")
    assert dest.value.kind == "unresolved" and dest.value.reason == "ENTITY_PARTIAL"
    assert r.readiness.scope_coverage == "partial"


def test_typed_temporal_derived_date_is_recomputed():
    r = ready()
    dates = [
        c.model_copy(update={"value": c.value.model_copy(update={"resolved_date": "2027-12-31"})})
        if isinstance(c.value, TemporalValue)
        else c
        for c in r.conditions
    ]
    updated = finalize_v2(r.model_copy(update={"conditions": dates}))
    assert next(c for c in updated.conditions if c.id == "start").value.resolved_date == "2027-02-03"


def test_answer_and_operation_cannot_modify_same_target():
    from requirements.v2 import OperationV2

    r = parsed(CLARIFIED)
    q = next(q for q in r.clarifications if q.reason_code == "DATE_YEAR_REQUIRED")
    wrapper = SlotExtractor(TetNim())
    wrapper.slots.answers = [RawAnswer(clarification_id=q.id, value_raw="2027", quote="Tết 2027")]
    wrapper.extraction = UpdateExtractionV2(
        operations=[OperationV2(op="remove", target_id="start", quote="Bỏ ngày đi")],
        preference_updates=[],
        reference_urls_update=None,
        notes_update=None,
    )
    with pytest.raises(AppError, match="cùng target"):
        wrapper.finish_requirement(
            r, Message(id="m", text="Tết 2027. Bỏ ngày đi", received_at=now().isoformat()), r
        )


def test_http_v2_accepts_evidence_bound_semantic_facts(settings):
    settings.data_provider = "http"
    settings.crawler_url = "https://crawler.invalid/collect"
    registry = fixture_registry()
    payload = vn_crawl().model_dump(mode="json")
    payload["origin"] = "source"
    for evidence in payload["evidence"]:
        evidence["method"] = "json"

    def handler(request):
        payload["request_id"] = json.loads(request.content)["request_id"]
        return httpx.Response(200, json=payload)

    gateway = GatewayV2(
        DataGateway(settings, registry=registry, transport=httpx.MockTransport(handler)), registry
    )
    result = asyncio.run(gateway.collect(ready(), (now() + timedelta(seconds=60)).isoformat()))
    assert result.tours[0].semantic_fields["nature"].value == ["forest"]
    payload["tours"][0]["semantic_fields"]["nature"]["observed_at"] = (now() + timedelta(days=1)).isoformat()
    result = asyncio.run(gateway.collect(ready(), (now() + timedelta(seconds=60)).isoformat()))
    assert not result.tours and any(s.reason_code == "CRAWLER_INVALID_OUTPUT" for s in result.source_results)


def test_exported_extraction_schema_constrains_operator_by_field():
    schema = InitialExtractionV2.model_json_schema()
    assert schema["$defs"]["RawTransportV2"]["properties"]["operator"]["enum"] == ["in", "not_in"]
    assert set(schema["$defs"]["RawNatureV2"]["properties"]["operator"]["enum"]) == {
        "prefer",
        "requires",
        "excludes",
    }


def test_live_assertions_use_semantics_and_ignore_ids():
    from requirements.evaluation_v2 import assertions

    case = json.loads(Path("tests/fixtures/requirements-semantic.json").read_text(encoding="utf-8"))[0]
    checks = assertions(parsed(), case["expected"])
    assert all(checks.values()), checks


def test_explicit_gregorian_date_near_tet_keeps_its_calendar():
    text = "Đi dịp Tết, khởi hành 03/02/2027 dương lịch."
    raw = RawConditionV2(
        id="date",
        field="departure_date",
        operator="eq",
        strength="hard",
        raw_values=["03/02/2027 dương lịch"],
        quote=text,
    )
    c = normalize_v2(raw, Message(id="m", text=text, received_at=now().isoformat()), "Asia/Ho_Chi_Minh")
    assert c.value.calendar == "gregorian" and c.value.holiday is None
    assert c.value.resolved_date == "2027-02-03"


def test_reserved_lunar_departure_window_is_backend_issue():
    r = ready()
    r = finalize_v2(
        r.model_copy(
            update={
                "conditions": [
                    c.model_copy(
                        update={"value": c.value.model_copy(update={"semantics": "departure_window"})}
                    )
                    if isinstance(c.value, TemporalValue)
                    else c
                    for c in r.conditions
                ]
            }
        )
    )
    assert r.readiness.status == "unsupported"
    assert "TEMPORAL_SEMANTICS_UNSUPPORTED" in r.readiness.reasons
    assert not r.clarifications
    assert all(c.value.resolved_date is None for c in r.conditions if isinstance(c.value, TemporalValue))


def test_pure_reply_reextracting_old_conditions_is_rejected():
    from requirements.v2 import OperationV2

    class BadReply(TetNim):
        async def extract_v2(self, message, previous=None, *, feedback=None):
            return UpdateExtractionV2(
                operations=[OperationV2(op="remove", target_id="start", quote=message.text)],
                preference_updates=[],
                reference_urls_update=None,
                notes_update=None,
            ), {}

    with pytest.raises(AppError, match="thuần"):
        asyncio.run(
            SlotExtractor(BadReply()).extract(
                Message(id="m", text="Tết 2027", received_at=now().isoformat()), parsed()
            )
        )


def test_route_answer_cannot_resolve_a_different_route():
    from requirements.v2 import clarification_only, clarification_targets

    r = parsed()
    q = next(q for q in r.clarifications if q.reason_code == "CONDITION_STRENGTH_REQUIRED")
    message = Message(id="m", text="Đi dọc Tây Nguyên chỉ là ưu tiên.", received_at=now().isoformat())
    assert not clarification_only(message, r)
    assert q not in clarification_targets(message, r)
    wrapper = SlotExtractor(TetNim())
    wrapper.slots.answers = [RawAnswer(clarification_id=q.id, value_raw="ưu tiên", quote=message.text)]
    wrapper.extraction = UpdateExtractionV2(
        preference_updates=[], reference_urls_update=None, notes_update=None
    )
    with pytest.raises(AppError, match="đúng route"):
        wrapper.finish_requirement(r, message, r)


def test_old_v2_values_and_policy_remain_readable():
    from conftest import condition, requirement

    from domain.requirements import SetValue

    old = requirement([condition("destinations", SetValue(items=["country:jp"]), "contains")]).model_dump(
        mode="json"
    )
    old.update(schema_version="2.0-draft", input_kind="text", policy_version="requirements-v1")
    r = RequirementV2.model_validate(old)
    assert r.policy_version == "requirements-v1" and r.conditions[0].value.kind == "set"
    updated = finalize_v2(r)
    assert updated.policy_version == "requirements-v2.2" and updated.readiness.status == "ready"


def test_hard_unsupported_blocks_api_confirm_and_removal_rebuilds_issues(settings):
    class HardNim(TetNim):
        async def extract_v2(self, message, previous=None, *, feedback=None):
            return InitialExtractionV2(
                conditions=[
                    RawConditionV2(
                        id="dest",
                        field="destinations",
                        operator="contains",
                        strength="hard",
                        raw_values=["Đà Nẵng"],
                        quote="Đà Nẵng",
                    ),
                    RawConditionV2(
                        id="trust",
                        field="supplier_reputation",
                        operator="requires",
                        strength="hard",
                        raw_values=[],
                        quote="Bắt buộc uy tín",
                    ),
                ],
                preference_updates=[],
                reference_urls_update=None,
                notes_update=None,
            ), {}

    app = create_app(settings, nim=HardNim())
    with TestClient(app) as client:
        token = client.post("/v2/sessions").json()["data"]["token"]
        client.headers["Authorization"] = f"Bearer {token}"
        accepted = client.post(
            "/v2/requirements", json={"input": {"kind": "text", "text": "Đi Đà Nẵng. Bắt buộc uy tín."}}
        ).json()["data"]
        finish(app)
        p = client.get(f"/v2/proposals/{accepted['proposal_id']}").json()["data"]
        confirm = {"expected_revision": 0, "expected_proposal_version": p["version"]}
        blocked = client.post(f"/v2/proposals/{p['id']}/confirm", json=confirm)
        assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "REQUIREMENT_NOT_READY"
        body = {
            **confirm,
            "proposal_id": p["id"],
            "input": {"kind": "structured", "edits": [{"op": "remove_condition", "condition_id": "trust"}]},
        }
        updated = client.post(f"/v2/requirements/{accepted['requirement_id']}/proposals", json=body)
        assert updated.status_code == 200, updated.text
        p = updated.json()["data"]
        assert not p["preview"]["issues"] and p["preview"]["readiness"]["status"] == "ready"
        confirm["expected_proposal_version"] = p["version"]
        assert client.post(f"/v2/proposals/{p['id']}/confirm", json=confirm).status_code == 200
