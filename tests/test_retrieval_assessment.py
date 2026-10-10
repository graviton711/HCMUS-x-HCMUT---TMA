"""Independent counterexamples for filter, per-offer and citation policies."""

import asyncio
import copy
import json
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from test_semantics import ready, vn_crawl
from test_supabase import Engine, crawl_request, field_proof
from test_supabase import config as config
from test_supabase import rows as rows
from test_v2 import Nim, comparison, data, form
from test_v2_edges import fixture

from api.app import create_app
from api.v2.models import ComparisonV2, RequirementV2
from data_access.fixtures import fixture_registry
from data_access.supabase.reader import SupabaseRepository
from decision.candidates import assess_options, prepare_candidates, refresh_candidates
from decision.v2 import build_comparison, preference_utility, score_bounds, score_tree
from domain.common import AppError, now
from domain.crawl import Fact
from domain.crawl_v2 import CrawlResultV2, EvidenceV2
from domain.requirements import Condition, Message, NumberValue, QuerySpec, SetValue, SourceReference, Tree
from domain.semantic import ConditionV2
from requirements.v2 import InitialExtractionV2, coverage_guard
from semantic_assessment.models import AssessmentBatch
from semantic_assessment.service import SemanticAssessor, prepare, validate


def request_requirement(settings):
    app = create_app(settings, nim=Nim())
    with TestClient(app) as c:
        c.headers["Authorization"] = "Bearer " + data(c.post("/v2/sessions"), 201)["token"]
        body = form()
        body["input"]["form"]["conditions"][3]["strength"] = "hard"
        body["input"]["form"]["conditions"][3]["value"]["amount"] = 30000000
        return RequirementV2.model_validate(data(c.post("/v2/requirements", json=body), 201))


def options_case(settings):
    r = request_requirement(settings)
    crawl = fixture(r)
    t = crawl.tours[0]
    first = next(o for o in crawl.offers if o.tour_snapshot_id == t.snapshot_id).model_copy(deep=True)
    second = first.model_copy(deep=True)
    second.snapshot_id, second.offer_id = "offer_second", "second"
    first.price_quotes[0].value.amount = 40000000
    second.price_quotes[0].value.amount = 20000000
    second.fields["departure_date"].value = "2026-11-11"
    return r, t, first, second


def test_cross_offer_date_price_cannot_establish_hard_pass(settings):
    r, t, a, b = options_case(settings)
    out = assess_options(r, t, [a, b], fixture_registry()[0], now().isoformat(), True)
    assert out["hard_status"] == "fail"
    assert not out["eligible_offer_snapshot_ids"]
    assert all(o["hard_status"] == "fail" for o in out["offer_assessments"])


def test_offer_truncation_preserves_unknown_instead_of_all_fail(settings):
    r, t, a, b = options_case(settings)
    out = assess_options(r, t, [a, b], fixture_registry()[0], now().isoformat(), True, complete=False)
    assert out["hard_status"] == "unknown" and out["selected"] is None


def test_unique_feasible_offer_selected_without_cheapest_shortcut(settings):
    r, t, a, b = options_case(settings)
    b.fields["departure_date"].value = "2026-11-10"
    out = assess_options(r, t, [a, b], fixture_registry()[0], now().isoformat(), True)
    assert out["hard_status"] == "pass" and out["selected"].snapshot_id == b.snapshot_id
    assert out["eligible_offer_snapshot_ids"] == [b.snapshot_id]


def test_multiple_feasible_offers_remain_explicit_options(settings):
    r, t, a, b = options_case(settings)
    b.fields["departure_date"].value = "2026-11-10"
    a.price_quotes[0].value.amount = 29000000
    out = assess_options(r, t, [a, b], fixture_registry()[0], now().isoformat(), True)
    assert out["hard_status"] == "pass" and out["selected"] is None
    assert len(out["eligible_offer_snapshot_ids"]) == 2


def test_or_tree_evaluated_within_offer(settings):
    r, t, a, b = options_case(settings)
    r.hard_tree = Tree(
        kind="any",
        children=[Tree(kind="predicate", condition_id=c.id) for c in r.conditions if c.strength == "hard"],
    )
    out = assess_options(r, t, [a, b], fixture_registry()[0], now().isoformat(), True)
    assert out["hard_status"] == "pass" and len(out["eligible_offer_snapshot_ids"]) == 2


def test_pool_filters_fail_before_limit_and_retains_unknown(settings):
    r = request_requirement(settings)
    crawl = fixture(r)
    failing = next(o for o in crawl.offers if o.tour_snapshot_id == crawl.tours[0].snapshot_id)
    failing.fields["departure_date"].value = "2026-11-11"
    other_tour = next(
        t
        for t in crawl.tours
        if t.snapshot_id != failing.tour_snapshot_id and "country:jp" in t.fields["destinations"].value
    )
    other = next(o for o in crawl.offers if o.tour_snapshot_id == other_tour.snapshot_id)
    other.price_quotes[0].value.amount = 29000000
    pool, _ = prepare_candidates(r, crawl, fixture_registry(), now().isoformat(), candidate_limit=1)
    assert len(pool) == 1 and pool[0]["tour"].snapshot_id == other.tour_snapshot_id
    del other.fields["departure_date"]
    pool, _ = prepare_candidates(r, crawl, fixture_registry(), now().isoformat(), candidate_limit=1)
    assert len(pool) == 1 and pool[0]["hard_status"] == "unknown"


def test_missing_soft_score_bounds_do_not_inflate_full_score():
    tree = Tree(kind="all", children=[Tree(kind="predicate", condition_id=str(i)) for i in range(5)])
    a = {str(i): {"utility": 1 if i == 0 else None, "weight": 1} for i in range(5)}
    b = {str(i): {"utility": 0.8, "weight": 1} for i in range(5)}
    assert score_tree(tree, a) == (1, 5, 1)
    assert score_bounds(tree, a) == (0.2, 1, 5)
    assert score_bounds(tree, b) == (0.8, 0.8, 5)
    assert score_bounds(tree, b)[0] > score_bounds(tree, a)[0]


def test_numeric_utility_independent_of_pool_and_zero_weights():
    c = ConditionV2(
        id="hotel",
        field="hotel_stars_min",
        operator="prefer_high",
        strength="soft",
        value=NumberValue(amount=4),
        sources=[SourceReference(kind="form", field_path="hotel")],
    )
    e = dict(status="unknown", reason_code="PREFERENCE_VALUE", actual=4)
    assert preference_utility(c, e, [1, 4]) == preference_utility(c, e, [4, 5]) == 0.75
    assert (
        score_bounds(Tree(kind="predicate", condition_id="hotel"), {"hotel": {"utility": None, "weight": 0}})[
            2
        ]
        == 0
    )


def test_ranking_prefers_supported_80_percent_over_partial_perfect_score(settings):
    r = request_requirement(settings)
    crawl = CrawlResultV2.model_validate(fixture(r).model_dump())
    fields = ["duration_days", "duration_nights", "hotel_stars_min", "shopping_stops", "flight_stops"]
    conditions = [c for c in r.conditions if c.strength == "hard"] + [
        ConditionV2(
            id="soft_" + field,
            field=field,
            operator="lte" if field in {"shopping_stops", "flight_stops"} else "near",
            strength="soft",
            value=NumberValue(amount=0 if field in {"shopping_stops", "flight_stops"} else 4),
            sources=[SourceReference(kind="form", field_path=field)],
        )
        for field in fields
    ]
    tree = Tree(
        kind="all",
        children=[Tree(kind="predicate", condition_id=c.id) for c in conditions if c.strength == "soft"],
    )
    r = RequirementV2.model_validate(
        {
            **r.model_dump(),
            "conditions": [c.model_dump() for c in conditions],
            "preference_tree": tree.model_dump(),
        }
    )
    japan = [t for t in crawl.tours if "country:jp" in t.fields["destinations"].value]
    for index, tour in enumerate(japan):
        base = tour.fields["duration_days"].model_copy(deep=True)
        for field in fields:
            tour.fields.pop(field, None)
            if index == 0 and field != "duration_days":
                continue
            value = (
                4
                if index == 0
                else 2
                if field in {"duration_nights", "hotel_stars_min"}
                else 6
                if field == "duration_days"
                else 0
            )
            eid = f"rank_{tour.snapshot_id}_{field}"
            text = f"Synthetic {field}: {value}"
            tour.fields[field] = base.model_copy(
                update={"value": value, "raw_value": text, "evidence_ids": [eid]}
            )
            crawl.evidence.append(
                EvidenceV2(
                    id=eid,
                    snapshot_id=tour.snapshot_id,
                    url=tour.canonical_url,
                    publisher=tour.supplier_id,
                    method="synthetic_fixture",
                    locator=field,
                    raw_quote=text,
                    observed_at=base.observed_at,
                )
            )
        for offer in crawl.offers:
            if offer.tour_snapshot_id == tour.snapshot_id:
                offer.price_quotes[0].value.amount = 20000000
    out = build_comparison("cmp", r, crawl, fixture_registry(), now().isoformat())
    items = out["recommendations"]["items"]
    from decision.candidates import tour_identity

    assert items[0]["candidate_id"] == tour_identity(japan[1])
    assert items[0]["score_interval"]["lower"] == pytest.approx(0.8)
    assert items[1]["score"] == 1 and items[1]["coverage"] == 0.2
    assert items[1]["score_interval"] == {"lower": 0.2, "upper": 1}
    ComparisonV2.model_validate(out)


def test_metric_availability_does_not_claim_foreign_prices_computed(settings):
    r = request_requirement(settings)
    crawl = fixture(r)
    japan = [t.snapshot_id for t in crawl.tours if "country:jp" in t.fields["destinations"].value]
    for offer in crawl.offers:
        if offer.tour_snapshot_id in japan:
            offer.price_quotes[0].value.amount = 20000000
            if offer.tour_snapshot_id == japan[1]:
                quote = offer.price_quotes[0].value
                offer.price_quotes[0].value = type(quote).model_validate(
                    {**quote.model_dump(), "currency": "USD", "amount": "20000000.00"}
                )
    out = build_comparison("cmp", r, crawl, fixture_registry(), now().isoformat())
    difference = next(
        a for a in out["analysis"]["metric_availability"] if a["metric"] == "published_price_difference"
    )
    assert any(m["operation"] == "subtract" and not m["comparable"] for m in out["analysis"]["metrics"])
    assert (
        difference["state"] == "blocked"
        and difference["reason_code"] == "PRICE_CURRENCY_BASIS_COVERAGE_MISMATCH"
    )


def test_all_rejected_catalog_preserves_empty_reason_and_scan_scope(settings):
    r = request_requirement(settings)
    raw = fixture(r).model_dump()
    raw.update(
        tours=[], offers=[], evidence=[], retrieval={"runs": [{"static_rejected": 3, "scan_truncated": True}]}
    )
    for source in raw["source_results"]:
        source.update(tour_snapshot_ids=[], offer_snapshot_ids=[])
    crawl = CrawlResultV2.model_validate(raw)
    out = build_comparison("cmp", r, crawl, fixture_registry(), now().isoformat())
    assert out["empty_reason"] == "ALL_INELIGIBLE"
    assert out["analysis"]["retrieval"]["runs"][0]["scan_truncated"]


def semantic_case():
    r, crawl = ready(), vn_crawl()
    crawl.tours[0].semantic_fields.pop("nature")
    text = "Ngày 2: đi bộ trong rừng và tham quan thác nước."
    ev = EvidenceV2(
        id="itinerary_proof",
        snapshot_id=crawl.tours[0].snapshot_id,
        url=crawl.tours[0].canonical_url,
        publisher=crawl.tours[0].supplier_id,
        method="html",
        locator="#itinerary",
        raw_quote=text,
        observed_at=now().isoformat(),
    )
    crawl.evidence.append(ev)
    crawl.tours[0].catalog_fields["itinerary"] = Fact(
        value=text,
        raw_value=text,
        data_state="present",
        verification="supplier_published",
        completeness="complete",
        observed_at=ev.observed_at,
        evidence_ids=[ev.id],
    )
    pool, _ = prepare_candidates(r, crawl, fixture_registry(), now().isoformat())
    assert len(pool) == 1 and pool[0]["hard_status"] == "pass"
    return r, crawl, pool


class SemanticGateway:
    def __init__(self, behavior="good"):
        self.calls = []
        self.behavior = behavior

    async def assess(self, payload, *, timeout, feedback=None):
        self.calls.append(feedback)
        if self.behavior == "timeout":
            raise AppError("LLM_TIMEOUT", "Synthetic timeout", 504)
        quote = "đi bộ trong rừng"
        if self.behavior == "bad" or self.behavior == "repair" and feedback is None:
            quote = "bịa bằng chứng"
        return AssessmentBatch(
            items=[
                dict(
                    candidate_id=pair["candidate_id"],
                    condition_id=pair["condition_id"],
                    status="matched",
                    citations=[dict(excerpt_id=pair["excerpt_ids"][0], quote=quote)],
                )
                for pair in payload["pairs"]
            ]
        )


@pytest.mark.parametrize(
    "behavior,state,repairs,calls",
    [
        ("good", "completed", False, 1),
        ("repair", "completed", True, 2),
        ("bad", "partial", True, 2),
        ("timeout", "partial", False, 1),
    ],
)
def test_assessment_validation_repair_timeout_and_replay(settings, behavior, state, repairs, calls):
    r, crawl, pool = semantic_case()
    gateway = SemanticGateway(behavior)
    assessor = SemanticAssessor(settings, gateway)
    report = asyncio.run(assessor.run(r, pool, crawl, (now() + timedelta(seconds=20)).isoformat()))
    assert report.state == state and report.repair_used == repairs and len(gateway.calls) == calls
    if state == "completed":
        assert report.items[0].usable_for_ranking and report.items[0].evidence_ids == ["itinerary_proof"]
        replay = asyncio.run(
            assessor.run(
                r, pool, crawl, (now() + timedelta(seconds=20)).isoformat(), previous=report.model_dump()
            )
        )
        assert replay == report and len(gateway.calls) == calls
        out = build_comparison(
            "cmp",
            r,
            crawl,
            fixture_registry(),
            now().isoformat(),
            prepared=(pool, False),
            semantic_report=report.model_dump(mode="json"),
        )
        nature = next(
            a for a in out["recommendations"]["items"][0]["contributions"] if a["condition_id"] == "nature"
        )
        assert nature["utility"] == 1 and nature["assessment"]["reason_code"] == "TEXT_SUPPORT"
        assert next(e for e in out["evaluations"] if e["condition_id"] == "nature")["status"] == "unknown"


def test_unverified_interpretation_is_not_scored(settings):
    r, crawl, pool = semantic_case()
    crawl.tours[0].catalog_fields["itinerary"].verification = "unverified"
    report = asyncio.run(
        SemanticAssessor(settings, SemanticGateway()).run(
            r, pool, crawl, (now() + timedelta(seconds=10)).isoformat()
        )
    )
    assert report.state == "completed" and not report.items[0].usable_for_ranking


@pytest.mark.parametrize("defect", ["quote", "candidate", "duplicate", "negative", "missing"])
def test_assessment_rejects_invalid_bindings_and_incomplete_negative(settings, defect):
    r, crawl, pool = semantic_case()
    payload, excerpts, _ = prepare(r, pool, crawl, settings)
    batch = asyncio.run(SemanticGateway().assess(payload, timeout=1))
    if defect == "quote":
        batch.items[0].citations[0].quote = "not in source"
    elif defect == "candidate":
        batch.items[0].candidate_id = "another_tour"
    elif defect == "duplicate":
        batch.items.append(batch.items[0])
    elif defect == "missing":
        batch.items.clear()
    else:
        batch.items[0].status = "not_matched"
        excerpts[payload["excerpts"][0]["id"]]["complete"] = False
    with pytest.raises(ValueError):
        validate(batch, payload, excerpts)


def test_hard_unknown_skips_nim_and_truncated_input_cannot_be_complete(settings):
    r, crawl, pool = semantic_case()
    gateway = SemanticGateway()
    pool[0]["hard_status"] = "unknown"
    report = asyncio.run(
        SemanticAssessor(settings, gateway).run(r, pool, crawl, (now() + timedelta(seconds=10)).isoformat())
    )
    assert report.state == "skipped" and not gateway.calls
    pool[0]["hard_status"] = "pass"
    settings.semantic_max_input_chars = 1000
    crawl.tours[0].catalog_fields["itinerary"].value *= 100
    payload, excerpts, limited = prepare(r, pool, crawl, settings)
    assert limited and not any(e["complete"] for e in excerpts.values())
    assert len(json.dumps(payload, ensure_ascii=False)) <= settings.semantic_max_input_chars
    assert all("source_quotes" not in e for e in payload["excerpts"])


def test_party_duplicate_guard_preserves_other_unsupported_intents():
    base = dict(
        preference_updates=[],
        reference_urls_update=None,
        notes_update=None,
        party=dict(adults_raw="1", adults_quote="đi 1 người lớn", children=None, rooming_quote=None),
    )
    message = Message(id="m", text="đi 1 người lớn", received_at=now().isoformat())
    raw = InitialExtractionV2(
        **base,
        conditions=[
            dict(
                id="adults",
                field="unsupported",
                operator="unresolved",
                strength="soft",
                raw_values=["đi 1 người lớn"],
                quote="đi 1 người lớn",
            )
        ],
    )
    with pytest.raises(AppError) as exc:
        coverage_guard(raw, message, None)
    assert "adults" in exc.value.repair_hint
    raw.conditions[0].quote = "đi 1 người lớn cần hỗ trợ xe lăn"
    coverage_guard(raw, message.model_copy(update={"text": raw.conditions[0].quote}), None)


def test_catalog_separates_processing_and_strength(settings):
    with TestClient(create_app(settings)) as client:
        catalog = data(client.get("/v2/catalog"))
    fields = {f["id"]: f for f in catalog["fields"]}
    assert fields["departure_origin"]["processing_methods"] == ["structured"]
    assert fields["departure_origin"]["strength_choices"] == ["hard", "soft"]
    assert catalog["assessment_policy"]["strength_independent_of_processing"]


def prove(tour, column):
    proof = field_proof(tour)
    value = tour[column]
    raw = ", ".join(value) if isinstance(value, list) else value
    return {
        **proof,
        "field": column,
        "value": value,
        "raw_value": raw,
        "raw_quote": "Nguồn công bố: " + raw,
        "completeness": "complete",
    }


@pytest.mark.parametrize(
    "first_origin,proven,static_rejected", [("Hải Phòng", True, 1), ("Hải Phòng", False, 0)]
)
def test_supabase_filter_before_pool_and_unknown_not_excluded(
    rows, config, first_origin, proven, static_rejected
):
    p, first, offer = copy.deepcopy(rows)
    first["departure_city"] = first_origin
    second = {
        **copy.deepcopy(first),
        "id": 2,
        "record_key": "d" * 64,
        "url": p["website"] + "/second",
        "departure_city": "Hồ Chí Minh",
    }
    for t in [first, second]:
        t["evidence"] = {"fields": {"destinations": prove(t, "destinations")}}
    if proven:
        first["evidence"]["fields"]["departure_city"] = prove(first, "departure_city")
    second["evidence"]["fields"]["departure_city"] = prove(second, "departure_city")
    engine = Engine((p, first, offer))
    engine.tours = [first, second]
    engine.offers.append({**offer, "id": 2, "record_key": "e" * 64, "tour_id": 2})
    repo = SupabaseRepository(config, engine=engine)
    req, r = crawl_request(repo)
    r.conditions.append(
        Condition(
            id="origin",
            field="departure_origin",
            operator="in",
            strength="hard",
            value=SetValue(items=["city:vn:hcmc"]),
            sources=[SourceReference(kind="form", field_path="origin")],
        )
    )
    r.hard_tree = Tree(kind="all", children=[Tree(kind="predicate", condition_id=c.id) for c in r.conditions])
    req.query = QuerySpec.from_requirement(r)
    out = asyncio.run(
        repo.collect(req, conditions=r.conditions, requirement=r, registry=repo.registry(), candidate_limit=1)
    )
    assert len(out.tours) == 1 and out.tours[0].tour_id == "catalog_tour_" + second["record_key"]
    assert out.retrieval["static_rejected"] == static_rejected
    queried = next(params["ids"] for sql, params in engine.calls if "SELECT offers.*" in sql)
    assert set(queried) == ({2} if proven else {1, 2})
    assert out.offer_coverage[out.tours[0].snapshot_id]


def test_single_truncated_failing_offer_does_not_exclude_tour(settings):
    r, t, a, _ = options_case(settings)
    out = assess_options(r, t, [a], fixture_registry()[0], now().isoformat(), True, complete=False)
    assert out["hard_status"] == "unknown" and out["selected"] is None


def test_refresh_keeps_assessed_pool_when_expiry_changes_eligibility(settings):
    r, crawl, _ = semantic_case()
    sources = [
        s.model_copy(update={"freshness_seconds": {k: 1 for k in s.freshness_seconds}})
        for s in fixture_registry()
    ]
    prepared = prepare_candidates(r, crawl, sources, now().isoformat(), candidate_limit=1)
    assert prepared[0][0]["hard_status"] == "pass"
    refreshed = refresh_candidates(r, prepared, (now() + timedelta(seconds=2)).isoformat(), synthetic=True)
    assert [c["id"] for c in refreshed[0]] == [c["id"] for c in prepared[0]]
    assert refreshed[0][0]["hard_status"] == "unknown"


async def assessment_crawl(_gateway, r, deadline, **kwargs):
    crawl = CrawlResultV2.model_validate(fixture(r).model_dump())
    for tour in crawl.tours:
        text = "Ngày 2: đi bộ trong rừng và tham quan thác nước."
        eid = "itinerary_" + tour.snapshot_id
        crawl.evidence.append(
            EvidenceV2(
                id=eid,
                snapshot_id=tour.snapshot_id,
                url=tour.canonical_url,
                publisher=tour.supplier_id,
                method="synthetic_fixture",
                locator="#itinerary",
                raw_quote=text,
                observed_at=now().isoformat(),
            )
        )
        tour.catalog_fields["itinerary"] = Fact(
            value=text,
            raw_value=text,
            data_state="present",
            verification="supplier_published",
            completeness="complete",
            observed_at=now().isoformat(),
            evidence_ids=[eid],
        )
    return CrawlResultV2.model_validate(crawl.model_dump())


def assessment_form():
    body = form()
    body["input"]["form"]["conditions"][3]["strength"] = "hard"
    body["input"]["form"]["conditions"][3]["value"]["amount"] = 30000000
    body["input"]["form"]["conditions"].append(
        {
            "id": "nature",
            "field": "nature",
            "operator": "prefer",
            "strength": "soft",
            "scope": "itinerary",
            "value": {
                "kind": "qualitative",
                "concept": "nature",
                "raw": "gần thiên nhiên",
                "metric_policy": "nature-itinerary-tags-v1",
            },
        }
    )
    return body


@pytest.mark.parametrize("behavior,job_state", [("good", "succeeded"), ("timeout", "partial")])
def test_api_assessment_published_with_events_and_failure_degrades(
    settings, monkeypatch, behavior, job_state
):

    from data_access.v2 import GatewayV2

    monkeypatch.setattr(GatewayV2, "collect", assessment_crawl)
    gateway = SemanticGateway(behavior)
    app = create_app(settings, nim=Nim(), semantic_gateway=gateway)
    with TestClient(app) as client:
        client.headers["Authorization"] = "Bearer " + data(client.post("/v2/sessions"), 201)["token"]
        r = data(client.post("/v2/requirements", json=assessment_form()), 201)
        accepted, job, output = comparison(client, app, r)
        assert job["status"] == job_state, job
        report = output["result"]["analysis"]["semantic_assessment"]
        assert report["state"] == ("completed" if behavior == "good" else "partial")
        assert output["result"]["recommendations"]["candidate_ids"]
        events = data(client.get(f"/v2/jobs/{accepted['job_id']}/events"))["items"]
        assert any(e["stage"] == "hard_filter" for e in events)
        assert any(
            e["stage"] == "semantic_assessment"
            and e["status"] == ("completed" if behavior == "good" else "partial")
            for e in events
        )
        ComparisonV2.model_validate(output["result"])


@pytest.mark.parametrize("mutation", ["cancel", "pause", "expire"])
def test_api_publication_rechecks_state_and_freshness_after_assessment(settings, monkeypatch, mutation):
    from sqlalchemy import select

    from api.v2 import service as service_module
    from api.v2 import state
    from data_access.v2 import GatewayV2

    monkeypatch.setattr(GatewayV2, "collect", assessment_crawl)
    settings.admin_token = "A" * 32
    gateway = SemanticGateway()
    app = create_app(settings, nim=Nim(), semantic_gateway=gateway)
    # A short source TTL makes expiry meaningful within the job's overall deadline.
    original_registry = app.state.worker.v2.registry

    def short_registry(connection=None):
        return [
            s.model_copy(update={"freshness_seconds": {k: 1 for k in s.freshness_seconds}})
            for s in original_registry(connection)
        ]

    if mutation == "expire":
        monkeypatch.setattr(app.state.worker.v2, "registry", short_registry)
    with TestClient(app) as client:
        client.headers["Authorization"] = "Bearer " + data(client.post("/v2/sessions"), 201)["token"]
        r = data(client.post("/v2/requirements", json=assessment_form()), 201)
        accepted = data(client.post("/v2/comparisons", json={"requirement_id": r["id"], "revision": 1}), 202)

        async def scenario():
            entered, release = asyncio.Event(), asyncio.Event()
            original_assess = gateway.assess

            async def delayed(payload, **kwargs):
                entered.set()
                await release.wait()
                return await original_assess(payload, **kwargs)

            gateway.assess = delayed
            task = asyncio.create_task(app.state.worker.run_once())
            await asyncio.wait_for(entered.wait(), 2)
            if mutation == "cancel":
                data(client.post(f"/v2/jobs/{accepted['job_id']}/cancel"))
            elif mutation == "pause":
                data(
                    client.patch(
                        "/v2/admin/sources/demo",
                        json={"expected_version": 1, "state": "paused"},
                        headers={"Authorization": "Bearer " + "A" * 32},
                    )
                )
            else:
                future = now() + timedelta(seconds=2)
                monkeypatch.setattr(service_module, "now", lambda: future)
            release.set()
            await task

        asyncio.run(scenario())
        job = data(client.get(f"/v2/jobs/{accepted['job_id']}"))
        output = data(client.get(f"/v2/comparisons/{accepted['comparison_id']}"))
        if mutation == "expire":
            assert job["status"] == "succeeded", job
            assert output["result"]["recommendations"]["candidate_ids"] == []
            assert output["result"]["empty_reason"] == "ONLY_UNVERIFIED"
            assert any(e["reason_code"] == "FIELD_STALE" for e in output["result"]["evaluations"])
        else:
            assert job["status"] == ("cancelled" if mutation == "cancel" else "failed"), job
            if mutation == "pause":
                assert job["error"]["code"] == "SOURCE_BLOCKED"
            assert output["result"] is None
            with app.state.store.engine.connect() as connection:
                assert not connection.execute(
                    select(state.snapshots.c.id).where(
                        state.snapshots.c.comparison_id == accepted["comparison_id"]
                    )
                ).first()


def test_reputation_quality_and_value_are_not_sent_to_llm(settings):
    r, crawl, pool = semantic_case()
    payload, _, _ = prepare(r, pool, crawl, settings)
    assert {p["field"] for p in payload["pairs"]} == {"nature"}


def test_requirement_revision_change_invalidates_assessment_replay(settings):
    r, crawl, pool = semantic_case()
    gateway = SemanticGateway()
    assessor = SemanticAssessor(settings, gateway)
    deadline = (now() + timedelta(seconds=10)).isoformat()
    saved = asyncio.run(assessor.run(r, pool, crawl, deadline))
    r.revision += 1
    next_report = asyncio.run(assessor.run(r, pool, crawl, deadline, previous=saved.model_dump()))
    assert len(gateway.calls) == 2 and saved.fingerprint != next_report.fingerprint
