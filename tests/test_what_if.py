"""Counterexamples for conditional analysis; no real network or credentials."""

import asyncio
import copy
import json
from datetime import timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select, update
from test_supabase import Engine, crawl_request, field_proof
from test_supabase import config as config
from test_supabase import rows as rows
from test_v2 import Nim, comparison, data, finish, form
from test_v2_edges import fixture

from api.app import create_app
from api.store import dump, jobs
from api.v2 import state
from api.v2.models import RequirementV2
from data_access.fixtures import fixture_registry
from data_access.supabase.reader import SupabaseRepository
from decision.candidates import prepare_candidates, tour_identity
from decision.what_if import build_analysis, condition_groups, plan_analysis, scenario_requirement
from domain.common import AppError, now
from domain.crawl_v2 import CrawlResultV2
from domain.requirements import DateValue, SourceReference, Tree
from domain.semantic import ConditionV2, QualitativeValue
from domain.what_if import CreateWhatIf, RestrictionRatio, WhatIfAnalysis
from semantic_assessment.what_if import InsightSelection, NimWhatIfGateway, WhatIfExplainer


@pytest.fixture
def app(settings):
    return create_app(settings, nim=Nim())


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        c.headers["Authorization"] = "Bearer " + data(c.post("/v2/sessions"), 201)["token"]
        yield c


@pytest.fixture
def case(client):
    body = form()
    body["input"]["form"]["conditions"][3]["value"]["amount"] = 11000000
    r = RequirementV2.model_validate(data(client.post("/v2/requirements", json=body), 201))
    crawl = CrawlResultV2.model_validate(fixture(r).model_dump())
    return r, crawl


def analysis(case, **options):
    r, crawl = case
    at = now().isoformat()
    settings = CreateWhatIf(expected_revision=r.revision, **options)
    plan = plan_analysis(r, crawl, fixture_registry(), at, settings)
    return build_analysis("analysis_test", "comparison_test", r, crawl, at, plan)


def scenario(result, field, kind="remove_hard_group"):
    gids = {g.id for g in result.groups if field in g.fields}
    return next(s for s in result.scenarios if s.kind == kind and set(s.group_ids) & gids)


def tour(crawl, slug):
    return next(t for t in crawl.tours if t.canonical_url.endswith(slug))


def offer(crawl, slug):
    return next(o for o in crawl.offers if o.tour_snapshot_id == tour(crawl, slug).snapshot_id)


def test_budget_removal_opens_tour_outside_original_pool(case):
    r, crawl = case
    pool, _ = prepare_candidates(r, crawl, fixture_registry(), now().isoformat(), candidate_limit=1)
    assert len(pool) == 1
    before = r.model_dump_json()
    result = analysis(case)
    s = scenario(result, "estimated_cost")
    assert result.baseline.eligible == 1 and s.population.eligible == 2
    assert s.proven_blocked_candidate_ids == [tour_identity(tour(crawl, "tour-c"))]
    assert s.restriction_ratio.percent == 50
    assert s.restriction_ratio.numerator == 1 and s.restriction_ratio.denominator == 2
    assert all(s.witnesses[0].evidence_ids)
    assert r.model_dump_json() == before
    diagnostics = next(d for d in result.scope["condition_diagnostics"] if d["condition_id"] == "budget")
    assert sum(diagnostics["counts"].values()) == len(result.candidates)
    assert diagnostics["counts"]["fail"] == 1 and diagnostics["unknown_reason_counts"] == {}
    assert diagnostics["offer_counts"]["fail"] == 1 and diagnostics["offer_unknown_reason_counts"] == {}


def test_actionable_budget_bound_uses_actual_price_and_keeps_basis(case):
    result = analysis(case)
    s = scenario(result, "estimated_cost", "relax_bound")
    changed = s.edits[0]["condition"]
    assert changed["value"]["amount"] == 12000000
    assert changed["value"]["basis"] == "per_adult"
    assert changed["value"]["coverage"] == "tour_price" and changed["strength"] == "hard"
    assert s.population.eligible == 2
    assert s.tradeoffs[0]["before"]["value"]["amount"] == 11000000


@pytest.mark.parametrize("kind", ["from", "unverified", "foreign", "stale"])
def test_no_actionable_price_from_unqualified_data(case, kind):
    r, crawl = case
    # This test checks guarantees on payable cost; listed "from" amounts have separate semantics.
    r = r.model_copy(
        update={
            "conditions": [
                c.model_copy(update={"value": c.value.model_copy(update={"measure": "payable"})})
                if c.field == "estimated_cost"
                else c
                for c in r.conditions
            ]
        }
    )
    case = r, crawl
    q = offer(crawl, "tour-c").price_quotes[0]
    if kind == "from":
        q.value.kind = "from"
    elif kind == "foreign":
        q.value = q.value.model_copy(update={"currency": "USD", "amount": "500"})
    elif kind == "unverified":
        raw = crawl.model_dump(mode="json")
        raw["origin"] = "source"
        for evidence in raw["evidence"]:
            evidence["method"] = "html"
        case = (case[0], CrawlResultV2.model_validate(raw))
    else:
        q.observed_at = (now() - timedelta(days=2)).isoformat()
    result = analysis(case)
    gids = {g.id for g in result.groups if "estimated_cost" in g.fields}
    assert not any(s.kind == "relax_bound" and set(s.group_ids) & gids for s in result.scenarios)


def test_unknown_to_pass_is_not_proven_blocking_percentage(case):
    _, crawl = case
    crawl.offer_coverage[tour(crawl, "tour-c").snapshot_id] = False
    result = analysis(case)
    s = scenario(result, "estimated_cost")
    assert s.previously_unknown_candidate_ids
    assert not s.proven_blocked_candidate_ids
    assert s.restriction_ratio.percent is None
    assert s.restriction_ratio.reason_code == "ORIGINAL_ELIGIBILITY_UNKNOWN"


def test_empty_cohort_has_null_percentage(case):
    r, _ = case
    budget = next(c for c in r.conditions if c.id == "budget")
    budget.value.amount = 1
    result = analysis(case)
    s = scenario(result, "departure_origin")
    assert s.population.eligible == 0 and s.restriction_ratio.percent is None
    assert s.restriction_ratio.reason_code == "EMPTY_ELIGIBLE_COHORT"


def test_two_joint_blockers_and_same_offer_witness(case):
    _, crawl = case
    o = offer(crawl, "tour-c")
    o.fields["departure_date"].value = "2026-11-11"
    result = analysis(case)
    assert not scenario(result, "estimated_cost").additional_candidate_ids
    assert not scenario(result, "departure_date").additional_candidate_ids
    both = next(
        s
        for s in result.scenarios
        if s.kind == "remove_hard_pair" and tour_identity(tour(crawl, "tour-c")) in s.additional_candidate_ids
    )
    assert both.minimal_within_tested_subsets
    assert {e["field"] for e in both.witnesses[0].original_evaluations if e["status"] == "fail"} == {
        "estimated_cost",
        "departure_date",
    }
    assert both.witnesses[0].offer_snapshot_id == o.snapshot_id


def test_date_window_is_measured_not_auto_assumed(case):
    r, crawl = case
    offer(crawl, "tour-c").price_quotes[0].value.amount = 10000000
    offer(crawl, "tour-c").fields["departure_date"].value = "2026-11-12"
    result = analysis(case)
    s = scenario(result, "departure_date", "relax_bound")
    c = s.edits[0]["condition"]
    assert c["operator"] == "between" and c["value"] == {
        "kind": "date",
        "value": "2026-11-10",
        "upper": "2026-11-12",
    }
    assert s.population.eligible == 2
    assert next(c for c in r.conditions if c.id == "date").operator == "eq"
    limited = analysis(case, max_date_shift_days=1)
    assert not any(s.kind == "relax_bound" and s.condition_ids == ["date"] for s in limited.scenarios)


def test_or_is_one_group_not_deleted_branch(case):
    r, _ = case
    r.hard_tree = Tree(
        kind="all",
        children=[
            Tree(
                kind="any",
                children=[
                    Tree(kind="predicate", condition_id="budget"),
                    Tree(kind="predicate", condition_id="date"),
                ],
            ),
            Tree(kind="predicate", condition_id="destination"),
            Tree(kind="predicate", condition_id="origin"),
        ],
    )
    grouped = next(g for g in condition_groups(r) if "budget" in g["condition_ids"])
    assert set(grouped["condition_ids"]) == {"date", "budget"}
    changed = scenario_requirement(r, grouped["condition_ids"])
    assert {c.id for c in changed.conditions if c.strength == "hard"} == {"origin", "destination"}
    result = analysis(case, condition_ids=["budget"])
    assert all(set(s.condition_ids) == {"date", "budget"} for s in result.scenarios)


def test_travel_start_end_bounds_are_one_group(case):
    r, _ = case
    extra = ConditionV2(
        id="return",
        field="return_date",
        operator="lte",
        value=DateValue(value="2026-11-20"),
        strength="hard",
        sources=[SourceReference(kind="form", field_path="conditions.return")],
    )
    r.conditions.append(extra)
    r.hard_tree.children.append(Tree(kind="predicate", condition_id="return"))
    g = next(g for g in condition_groups(r) if "date" in g["condition_ids"])
    assert set(g["condition_ids"]) == {"date", "return"}


def test_cross_offer_prices_and_dates_not_combined(case):
    _, crawl = case
    first = offer(crawl, "tour-c")
    second = first.model_copy(deep=True)
    second.snapshot_id = "second_offer"
    second.fields["departure_date"].value = "2026-11-11"
    second.price_quotes[0].value.amount = 9000000
    crawl.offers.append(second)
    crawl.source_results[0].offer_snapshot_ids.append(second.snapshot_id)
    result = analysis(case)
    assert tour_identity(tour(crawl, "tour-c")) not in result.baseline.eligible_candidate_ids
    s = scenario(result, "estimated_cost", "relax_bound")
    w = s.witnesses[0]
    assert w.offer_snapshot_id == first.snapshot_id
    assert all(e["offer_snapshot_id"] == first.snapshot_id for e in w.scenario_evaluations)


def test_unsupported_soft_is_unknown_not_zero_influence(case):
    r, _ = case
    r.conditions.append(
        ConditionV2(
            id="quality",
            field="service_quality",
            operator="prefer",
            value=QualitativeValue(concept="service_quality", raw="dịch vụ tốt"),
            strength="soft",
            sources=[SourceReference(kind="form", field_path="conditions.quality")],
        )
    )
    r.preference_tree.children.append(Tree(kind="predicate", condition_id="quality"))
    result = analysis(case)
    s = scenario(result, "service_quality", "remove_soft_group")
    assert s.state == "insufficient_data" and s.restriction_ratio.percent is None


def test_soft_removal_changes_ranking_without_changing_hard(case):
    r, _ = case
    next(c for c in r.conditions if c.id == "budget").value.amount = 35000000
    r.conditions.append(
        ConditionV2(
            id="hotel",
            field="hotel_stars_min",
            operator="prefer_high",
            value={"kind": "number", "amount": 5},
            strength="soft",
            sources=[SourceReference(kind="form", field_path="conditions.hotel")],
        )
    )
    r.preference_tree.children.append(Tree(kind="predicate", condition_id="hotel"))
    result = analysis(case)
    s = scenario(result, "hotel_stars_min", "remove_soft_group")
    assert s.population.eligible_candidate_ids == result.baseline.eligible_candidate_ids
    assert s.top_changed and len(s.rank_changes) == 2
    assert {c.rank_delta for c in s.rank_changes} == {-1, 1}
    assert s.restriction_ratio.state == "not_applicable"


def test_scope_limits_and_exclusions_are_explicit(case):
    r, crawl = case
    options = CreateWhatIf(expected_revision=1, max_scenarios=1)
    at = now().isoformat()
    excluded = [tour_identity(tour(crawl, "tour-a"))]
    plan = plan_analysis(r, crawl, fixture_registry(), at, options, exclusions=excluded)
    result = build_analysis("analysis_test", "comparison_test", r, crawl, at, plan, exclusions=excluded)
    assert result.limits["scenarios_truncated"] and len(result.scenarios) == 1
    assert result.scope["baseline"] == "recomputed_on_analysis_snapshot"
    assert not set(excluded) & {c["candidate_id"] for c in result.candidates}


@pytest.mark.parametrize(
    "state,numerator,denominator,percent",
    [("computed", 1, 0, 0.0), ("computed", 1, 2, 25.0), ("blocked", 1, 2, 50.0)],
)
def test_invalid_percentages_rejected(state, numerator, denominator, percent):
    with pytest.raises(ValidationError):
        RestrictionRatio(state=state, numerator=numerator, denominator=denominator, percent=percent)


def start_analysis(client, app, case, **opts):
    r, _ = case
    accepted, _, _ = comparison(client, app, r.model_dump(mode="json"))
    request = client.post(
        f"/v2/comparisons/{accepted['comparison_id']}/what-if",
        json={"expected_revision": r.revision, **opts},
        headers={"Idempotency-Key": "what-if-test"},
    )
    created = data(request, 202)
    finish(app)
    job = data(client.get(f"/v2/jobs/{created['job_id']}"))
    published = data(client.get(f"/v2/what-if/{created['analysis_id']}"))
    assert job["status"] in {"succeeded", "partial"}, job
    return accepted, created, WhatIfAnalysis.model_validate(published["result"])


def test_api_end_to_end_idempotency_evidence_and_apply(client, app, case):
    parent, created, result = start_analysis(client, app, case)
    again = data(
        client.post(
            f"/v2/comparisons/{parent['comparison_id']}/what-if",
            json={"expected_revision": 1},
            headers={"Idempotency-Key": "what-if-test"},
        ),
        202,
    )
    assert again == created
    assert result.baseline.eligible == 1
    s = scenario(result, "estimated_cost", "relax_bound")
    assert data(client.get(f"/v2/evidence/{s.witnesses[0].evidence_ids[0]}"))["id"]
    p = data(
        client.post(
            f"/v2/what-if/{created['analysis_id']}/scenarios/{s.id}/proposals", json={"expected_revision": 1}
        )
    )
    assert p["preview"]["readiness"]["can_confirm"]
    assert data(client.get(f"/v2/requirements/{result.requirement_id}"))["revision"] == 1
    confirmed = data(
        client.post(
            f"/v2/proposals/{p['id']}/confirm",
            json={"expected_revision": 1, "expected_proposal_version": p["version"]},
        )
    )
    assert confirmed["revision"] == 2
    response = client.post(
        f"/v2/what-if/{created['analysis_id']}/scenarios/{s.id}/proposals", json={"expected_revision": 1}
    )
    assert response.status_code == 409 and response.json()["error"]["code"] == "REVISION_CONFLICT"


def test_api_removing_required_budget_creates_incomplete_proposal(client, app, case):
    _, created, result = start_analysis(client, app, case)
    s = scenario(result, "estimated_cost")
    p = data(
        client.post(
            f"/v2/what-if/{created['analysis_id']}/scenarios/{s.id}/proposals", json={"expected_revision": 1}
        )
    )
    assert not p["preview"]["readiness"]["can_confirm"]
    assert (
        client.post(
            f"/v2/proposals/{p['id']}/confirm",
            json={"expected_revision": 1, "expected_proposal_version": p["version"]},
        ).status_code
        == 409
    )


def test_api_owner_and_invalid_condition_guard(client, app, case):
    parent, created, result = start_analysis(client, app, case)
    other = data(client.post("/v2/sessions"), 201)["token"]
    headers = {"Authorization": "Bearer " + other}
    assert client.get(f"/v2/what-if/{created['analysis_id']}", headers=headers).status_code == 404
    assert (
        client.post(
            f"/v2/comparisons/{parent['comparison_id']}/what-if",
            json={"expected_revision": 1},
            headers=headers,
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/v2/what-if/{created['analysis_id']}/scenarios/{result.scenarios[0].id}/proposals",
            json={"expected_revision": 1},
            headers=headers,
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/v2/comparisons/{parent['comparison_id']}/what-if",
            json={"expected_revision": 1, "condition_ids": ["not-a-condition"]},
        ).status_code
        == 422
    )


def test_api_cancelled_job_never_publishes(client, app, case):
    r, _ = case
    parent, _, _ = comparison(client, app, r.model_dump(mode="json"))
    created = data(
        client.post(f"/v2/comparisons/{parent['comparison_id']}/what-if", json={"expected_revision": 1}), 202
    )
    data(client.post(f"/v2/jobs/{created['job_id']}/cancel"))
    assert not asyncio.run(app.state.worker.run_once())
    result = data(client.get(f"/v2/what-if/{created['analysis_id']}"))
    assert result["status"] == "cancelled" and result["result"] is None


def test_url_only_analysis_keeps_reference_scope_without_personalized_claim(client, app):
    accepted = data(
        client.post(
            "/v2/requirements",
            json={
                "input": {"kind": "urls"},
                "reference_urls": ["https://tour-demo.invalid/tour-a", "https://tour-demo.invalid/tour-c"],
            },
        ),
        201,
    )
    p = data(client.get(f"/v2/proposals/{accepted['proposal_id']}"))
    r = data(
        client.post(
            f"/v2/proposals/{p['id']}/confirm",
            json={"expected_revision": 0, "expected_proposal_version": p["version"]},
        )
    )
    parent, _, _ = comparison(client, app, r)
    created = data(
        client.post(f"/v2/comparisons/{parent['comparison_id']}/what-if", json={"expected_revision": 1}), 202
    )
    finish(app)
    resource = data(client.get(f"/v2/what-if/{created['analysis_id']}"))
    result = WhatIfAnalysis.model_validate(resource["result"])
    assert result.scope["retrieval"]["upstream_scope"] == "reference_urls"
    assert len(result.candidates) == 2 and not result.baseline.has_hard_constraints
    assert result.scenarios == [] and result.explanation["reason_code"] == "NO_MEASURED_CHANGE"


def test_pending_proposal_blocks_new_analysis(client, app, case):
    parent, created, result = start_analysis(client, app, case)
    s = scenario(result, "estimated_cost")
    data(
        client.post(
            f"/v2/what-if/{created['analysis_id']}/scenarios/{s.id}/proposals", json={"expected_revision": 1}
        )
    )
    response = client.post(
        f"/v2/comparisons/{parent['comparison_id']}/what-if", json={"expected_revision": 1}
    )
    assert response.status_code == 409 and response.json()["error"]["code"] == "PROPOSAL_NOT_CONFIRMED"


@pytest.mark.parametrize("outcome", ["cancel", "pause", "policy"])
def test_publication_guards_after_final_model_wait(client, app, case, monkeypatch, outcome):
    class Gateway:
        async def select(self, payload, *, timeout):
            if outcome == "cancel":
                with app.state.store.transaction() as c:
                    row = c.execute(select(jobs).where(jobs.c.kind == "v2_what_if")).mappings().first()
                    app.state.store.cancel(c, row["owner"], row["id"])
            else:
                with app.state.store.transaction() as c:
                    row = c.execute(select(state.source_registry)).mappings().first()
                    saved = json.loads(row["payload"])
                    if outcome == "pause":
                        saved["state"] = "paused"
                    else:
                        saved["capability"]["freshness_seconds"]["price"] = 60
                    c.execute(
                        update(state.source_registry)
                        .where(state.source_registry.c.id == row["id"])
                        .values(payload=dump(saved))
                    )
            return InsightSelection(insight_ids=[payload["insights"][0]["id"]])

    app.state.worker.v2.explainer = WhatIfExplainer(app.state.store.settings, Gateway())
    r, _ = case
    parent, _, _ = comparison(client, app, r.model_dump(mode="json"))
    created = data(
        client.post(f"/v2/comparisons/{parent['comparison_id']}/what-if", json={"expected_revision": 1}), 202
    )
    finish(app)
    status = data(client.get(f"/v2/what-if/{created['analysis_id']}"))
    assert status["result"] is None
    assert status["status"] == ("cancelled" if outcome == "cancel" else "failed")
    if outcome == "policy":
        job = data(client.get(f"/v2/jobs/{created['job_id']}"))
        assert job["error"]["code"] == "SOURCE_POLICY_CHANGED"


def test_redundant_pairs_consume_attempt_budget(case):
    result = analysis(case, max_scenarios=8)
    assert result.limits["attempted_scenarios"] == 8
    assert result.limits["redundant_pairs_skipped"] > 0
    assert result.limits["scenario_count"] < 8
    assert result.limits["scenarios_truncated"]


def test_no_change_with_unknown_candidates_is_not_zero_influence(case):
    _, crawl = case
    offer(crawl, "tour-c").price_quotes[0].observed_at = (now() - timedelta(days=2)).isoformat()
    result = analysis(case)
    s = scenario(result, "departure_origin")
    assert not s.additional_candidate_ids and s.population.eligible == 1
    assert s.restriction_ratio.percent is None
    assert s.restriction_ratio.reason_code == "UNVERIFIED_CANDIDATES"
    assert s.state == "insufficient_data"


def test_empty_analysis_universe_is_valid_and_explicit(case):
    r, crawl = case
    crawl.tours.clear()
    crawl.offers.clear()
    crawl.evidence.clear()
    crawl.offer_coverage.clear()
    for source in crawl.source_results:
        source.tour_snapshot_ids.clear()
        source.offer_snapshot_ids.clear()
    result = analysis((r, crawl))
    assert result.baseline.eligible == result.baseline.unknown == 0
    assert result.candidates == []
    assert all(
        s.state == "insufficient_data" and s.restriction_ratio.percent is None for s in result.scenarios
    )


@pytest.mark.parametrize("tampering", ["condition_group", "cohort", "ranking_interval", "rank_delta"])
def test_public_analysis_rejects_inconsistent_metrics(case, tampering):
    r, _ = case
    next(c for c in r.conditions if c.id == "budget").value.amount = 35000000
    r.conditions.append(
        ConditionV2(
            id="hotel",
            field="hotel_stars_min",
            operator="prefer_high",
            value={"kind": "number", "amount": 5},
            strength="soft",
            sources=[SourceReference(kind="form", field_path="conditions.hotel")],
        )
    )
    r.preference_tree.children.append(Tree(kind="predicate", condition_id="hotel"))
    raw = analysis(case).model_dump(mode="json")
    s = next(
        s for s in raw["scenarios"] if s["kind"] == "remove_soft_group" and s["condition_ids"] == ["hotel"]
    )
    if tampering == "condition_group":
        s["condition_ids"] = ["origin"]
    elif tampering == "cohort":
        s["restriction_ratio"]["denominator"] += 1
    elif tampering == "ranking_interval":
        s["top_after"][0]["score_lower"] = 1
        s["top_after"][0]["score_upper"] = 0
    else:
        s["rank_changes"][0]["rank_delta"] += 1
    with pytest.raises(ValidationError):
        WhatIfAnalysis.model_validate(raw)


@pytest.mark.asyncio
async def test_disabling_final_explanation_retains_computed_templates(case, settings):
    class Gateway:
        async def select(self, payload, *, timeout):
            raise AssertionError("Disabled explanation must not call LLM")

    result = analysis(case)
    settings.what_if_explanation_enabled = False
    response = await WhatIfExplainer(settings, Gateway()).run(
        result, (now() + timedelta(seconds=60)).isoformat()
    )
    assert response["state"] == "skipped" and response["reason_code"] == "EXPLANATION_DISABLED"
    assert response["text"]


def test_volatile_facts_expire_during_explanation_and_metrics_refresh(client, app, case, monkeypatch):
    with app.state.store.transaction() as c:
        row = c.execute(select(state.source_registry)).mappings().first()
        saved = json.loads(row["payload"])
        saved["capability"]["freshness_seconds"] = {"departure_date": 30, "return_date": 30, "price": 30}
        c.execute(
            update(state.source_registry)
            .where(state.source_registry.c.id == row["id"])
            .values(payload=dump(saved))
        )

    class Gateway:
        async def select(self, payload, *, timeout):
            monkeypatch.setattr("api.v2.service.now", lambda: now() + timedelta(seconds=60))
            return InsightSelection(insight_ids=[payload["insights"][0]["id"]])

    app.state.worker.v2.explainer = WhatIfExplainer(app.state.store.settings, Gateway())
    _, _, result = start_analysis(client, app, case)
    assert result.baseline.eligible == 0 and result.baseline.unknown > 0
    assert not any(s.proven_blocked_candidate_ids for s in result.scenarios)
    assert result.explanation["reason_code"] == "DATA_CHANGED_DURING_EXPLANATION"


@pytest.mark.asyncio
@pytest.mark.parametrize("reply", ["valid", "invalid", "timeout"])
async def test_llm_only_selects_bound_insights_and_falls_back(case, settings, reply):
    result = analysis(case)

    class Gateway:
        async def select(self, payload, *, timeout):
            if reply == "timeout":
                raise AppError("LLM_TIMEOUT", "mock", 504)
            return {"insight_ids": [payload["insights"][0]["id"] if reply == "valid" else "made-up"]}

    response = await WhatIfExplainer(settings, Gateway()).run(
        result, (now() + timedelta(seconds=60)).isoformat()
    )
    assert response["state"] == ("completed" if reply == "valid" else "fallback")
    by_id = {s.id: s.insight for s in result.scenarios}
    assert response["text"] == [by_id[sid] for sid in response["insight_ids"]]


@pytest.mark.asyncio
async def test_nim_explanation_schema_enum_and_no_prose(settings):
    def handle(request):
        body = json.loads(request.content)
        assert body["response_format"]["json_schema"]["schema"]["properties"]["insight_ids"]["items"][
            "enum"
        ] == ["scenario_known"]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"finish_reason": "stop", "message": {"content": '{"insight_ids":["scenario_known"]}'}}
                ]
            },
        )

    output = await NimWhatIfGateway(settings, httpx.MockTransport(handle)).select(
        {"insights": [{"id": "scenario_known", "text": "computed"}]}, timeout=1
    )
    assert output.insight_ids == ["scenario_known"]


@pytest.mark.asyncio
async def test_catalog_analysis_keeps_static_fail_and_removes_date_anchor(rows, config):
    engine = Engine(rows)
    repo = SupabaseRepository(config, engine=engine)
    request, r = crawl_request(repo)
    rows[1]["evidence"]["fields"] = {"departure_city": field_proof(rows[1])}
    r = r.model_copy(
        update={
            "conditions": [
                ConditionV2(
                    id="origin",
                    field="departure_origin",
                    operator="in",
                    value={"kind": "set", "items": ["city:vn:haiphong"]},
                    strength="hard",
                    sources=[SourceReference(kind="form", field_path="origin")],
                )
            ],
            "hard_tree": Tree(kind="predicate", condition_id="origin"),
        }
    )
    out = await repo.collect(
        request,
        conditions=r.conditions,
        requirement=r,
        registry=repo.registry(),
        analysis=True,
        candidate_limit=500,
    )
    assert len(out.tours) == 1 and out.retrieval["static_rejected"] == 0
    assert out.retrieval["filtering"] == "unfiltered_analysis_universe"
    query = next(params for sql, params in engine.calls if "PARTITION BY tour_id" in sql)
    assert query["anchor"] is None


@pytest.mark.asyncio
async def test_analysis_catalog_limit_can_exceed_original_100(rows, config):
    engine = Engine(rows)
    engine.tours = [
        {
            **copy.deepcopy(rows[1]),
            "id": i,
            "record_key": f"{i:064x}",
            "url": f"https://catalog-example.invalid/tour-{i}",
        }
        for i in range(1, 111)
    ]
    engine.offers = []
    repo = SupabaseRepository(config, engine=engine)
    request, r = crawl_request(repo)
    out = await repo.collect(
        request,
        conditions=r.conditions,
        requirement=r,
        registry=repo.registry(),
        analysis=True,
        candidate_limit=110,
    )
    assert len(out.tours) == 110
    normal = await repo.collect(
        request, conditions=r.conditions, requirement=r, registry=repo.registry(), candidate_limit=110
    )
    assert len(normal.tours) == 100 and normal.retrieval["pool_truncated"]
