"""MCP contract: schema-grounded catalog tools, exact quotes and hard-pass gating."""

import asyncio
import json
from secrets import token_hex

import pytest
from sample_rows import StaticCatalog

from backend.agent.mcp_server import AgentTools, QueryConditionInput, create_server
from backend.agent.results import limit_comparison
from backend.data.sessions import SessionStore
from backend.decide.engine import select_soft_review_candidates
from backend.errors import AppError
from backend.models import (
    Comparison,
    Evaluation,
    OfferSnapshot,
    RankedCandidate,
    Requirement,
    TourRow,
    TourSnapshot,
)
from backend.workflows import TourWorkflows


def _tools(settings):
    catalog = StaticCatalog()
    return AgentTools(settings, catalog, TourWorkflows(settings, catalog))


def _pop_decision_result(database_url, run_id):
    store = SessionStore(database_url)
    try:
        return store.pop_decision_result(run_id)
    finally:
        store.close()


def _query(tools, **kwargs):
    run_id = f"dec_{token_hex(16)}"
    result = json.loads(tools.query_tours(decision_run_id=run_id, **kwargs))
    while result.get("soft_review") and not result["soft_review"].get("soft_conditions"):
        result = _score_soft(tools, result["soft_review"]["context_id"], [])
    if result.get("ranking_complete"):
        comparison = _pop_decision_result(tools.settings.database_url, run_id)
        if comparison is not None:
            result["comparison"] = comparison.model_dump(mode="json")
    return result


def _score_soft(tools, context_id, verdicts):
    context = tools._ranking_contexts[context_id]
    batch = context.batches[context.batch_index]
    metric_facts = [
        {"tour_id": tour.id}
        for tour, _offer_id in batch
        if tour.id not in context.metric_facts
    ]
    result = json.loads(tools.score_soft(context_id, verdicts, metric_facts))
    run_id = result.get("decision_run_id")
    if result.get("ranking_complete") and isinstance(run_id, str):
        comparison = _pop_decision_result(tools.settings.database_url, run_id)
        if comparison is not None:
            result["comparison"] = comparison.model_dump(mode="json")
    return result


@pytest.mark.parametrize("count", [0, 1, 15, 16])
def test_soft_review_sample_cardinality_and_stability(count):
    candidates = []
    for index in range(count):
        tour_id = f"tour-{count - index:02d}"
        offer_id = f"offer-{count - index:02d}"
        tour = TourSnapshot(
            id=tour_id,
            supplier=f"Supplier {index % 3}",
            destinations=[f"Destination {index % 4}"],
            duration_days=3,
            offers=[OfferSnapshot(
                id=offer_id,
                tour_id=tour_id,
                departure_date=f"2027-{index % 12 + 1:02d}-01",
                price=1_000_000 + index * 10_000,
                currency="VND",
            )],
        )
        candidates.append((tour, offer_id))
    requirement = Requirement(
        id="req_sampler",
        ranking={"order_by": [{"field": "duration_days", "direction": "asc"}]},
    )

    first = select_soft_review_candidates(requirement, candidates)
    second = select_soft_review_candidates(requirement, candidates)

    assert len(first) == min(15, count)
    assert [tour.id for tour, _offer_id in first] == [tour.id for tour, _offer_id in second]
    assert len({tour.id for tour, _offer_id in first}) == len(first)
    if count:
        assert first[0][0].id == f"tour-{count:02d}"


def test_soft_review_ranking_ties_prefer_comparable_price_then_departure_date():
    candidates = []
    for tour_id, offer_id, departure_date in [
        ("a-later", "offer-a", "2027-05-01"),
        ("z-earlier", "offer-z", "2027-04-01"),
    ]:
        candidates.append((
            TourSnapshot(
                id=tour_id,
                duration_days=3,
                offers=[OfferSnapshot(
                    id=offer_id,
                    tour_id=tour_id,
                    departure_date=departure_date,
                    price=1_000_000,
                    currency="VND",
                )],
            ),
            offer_id,
        ))
    requirement = Requirement(
        id="req_tie_break",
        ranking={"order_by": [{"field": "duration_days", "direction": "asc"}]},
    )

    ranked = select_soft_review_candidates(requirement, candidates)

    assert [tour.id for tour, _offer_id in ranked] == ["z-earlier", "a-later"]


class _RecordingCatalog:
    def __init__(self):
        self.catalog = StaticCatalog()
        self.limits = []

    def list_tours(self, limit):
        self.limits.append(limit)
        return self.catalog.list_tours(limit)


def _phu_requirement():
    return {
        "raw_text": "Muốn đi Phú Quốc, thích công viên",
        "travelers": 1,
        "conditions": [
            {"id": "h1", "field": "destination", "operator": "contains", "value": "Phú Quốc",
             "strength": "hard", "quote": "Phú Quốc"},
            {"id": "s1", "field": "preference", "operator": "contains", "value": "công viên",
             "strength": "soft", "quote": "thích công viên", "weight_percent": 100},
        ],
    }


def test_query_tours_mcp_schema_requires_complete_condition_contract(settings, monkeypatch):
    import backend.agent.mcp_server as mcp_server

    monkeypatch.setattr(mcp_server, "for_settings", lambda _settings: StaticCatalog())
    tools = asyncio.run(create_server(settings).list_tools())
    schema = next(tool.inputSchema for tool in tools if tool.name == "query_tours")
    condition = schema["$defs"]["QueryConditionInput"]

    assert set(condition["required"]) == {
        "id", "field", "operator", "value", "strength", "quote",
    }
    assert condition["additionalProperties"] is False
    assert "decision_run_id" in schema["required"]
    discover = next(tool.inputSchema for tool in tools if tool.name == "discover_destinations")
    top = discover["properties"]
    for param in ("raw_text", "conditions", "travelers", "traveler_mix", "conversation_id"):
        assert top[param].get("description"), param
    assert "exact quote" in top["conditions"]["description"]
    assert "adult" in top["traveler_mix"]["description"]
    tools_by_name = {tool.name: tool.inputSchema for tool in tools}
    score_props = tools_by_name["score_soft"]["properties"]
    assert "offer_id" in score_props["verdicts"].get("description", "")
    assert "tour_id" in score_props["metric_facts"].get("description", "")
    assert "relax_criterion" not in {tool.name for tool in tools}
    assert "discover_destinations" in {tool.name for tool in tools}


def test_scenario_query_reuses_retained_snapshot_instead_of_live_catalog(settings):
    from backend.models import Condition

    tools = _tools(settings)
    source_requirement = tools.workflows.requirement(
        "Đi Đà Lạt",
        [Condition(id="source", field="destination", operator="contains", value="Đà Lạt", strength="hard",
                   quote="Đà Lạt").model_dump()],
        1,
        requirement_id="req_source",
    )
    baseline = tools.workflows.comparison(source_requirement, settings.supabase_scan_limit)
    run_id = f"dec_{token_hex(16)}"
    store = SessionStore(settings.database_url)
    try:
        store.save_scenario_snapshot_handoff(run_id, baseline)
        tools.result_store = store

        class EmptyCatalog:
            def list_tours(self, limit):
                return []

            def list_destinations(self):
                return []

        tools.catalog = EmptyCatalog()
        tools.workflows = TourWorkflows(settings, tools.catalog)
        result = json.loads(tools.query_tours(
            raw_text="Đà Lạt",
            conditions=[{
                "id": "destination", "field": "destination", "operator": "contains",
                "value": "Đà Lạt", "strength": "hard", "quote": "Đà Lạt",
            }],
            decision_run_id=run_id,
            travelers=1,
            requirement_id="req_scenario",
            snapshot_comparison_id=baseline.id,
        ))

        context_id = result["soft_review"]["context_id"]
        context = tools._ranking_contexts[context_id]
        assert context.comparison.scenario_source_comparison_id == baseline.id
        assert [tour.id for tour in context.comparison.tour_snapshots] == [
            tour.id for tour in baseline.tour_snapshots
        ]
        assert result["scanned_tours"] == len(baseline.tour_snapshots)
    finally:
        store.close()


def test_catalog_facets_only_returns_values_from_active_catalog(settings):
    result = json.loads(_tools(settings).catalog_facets())
    assert result["destinations"] == ["Hạ Long", "Phú Quốc", "Đà Lạt"]
    assert result["departure_cities"] == ["Hà Nội", "Sài Gòn"]
    assert "2026-12-26" in result["departure_dates"]
    assert 12_900_000 in result["prices_vnd"]
    assert result["scanned_tours"] == 3
    assert result["scan_limit"] == settings.supabase_scan_limit


def test_catalog_facets_can_avoid_sending_unrequested_value_groups(settings):
    result = json.loads(_tools(settings).catalog_facets(["destinations"]))
    assert result["destinations"] == ["Hạ Long", "Phú Quốc", "Đà Lạt"]
    assert result["scanned_tours"] == 3
    assert "departure_cities" not in result
    assert "prices_vnd" not in result
    assert "departure_dates" not in result


def test_discover_destinations_returns_only_hard_matching_catalog_options(settings):
    result = json.loads(_tools(settings).discover_destinations(
        raw_text="Đi từ Sài Gòn 3 ngày",
        travelers=5,
        conditions=[
            {
                "id": "h1", "field": "departure_city", "operator": "contains",
                "value": "Sài Gòn", "strength": "hard", "quote": "Sài Gòn",
            },
            {
                "id": "h2", "field": "duration_days", "operator": "eq",
                "value": 3, "strength": "hard", "quote": "3 ngày",
            },
        ],
    ))

    assert result["status"] == "matching_options_found"
    assert result["matching_tour_count"] == 1
    assert [item["destination"] for item in result["matching_destinations"]] == ["Đà Lạt"]
    assert result["matching_destinations"][0]["examples"][0]["tour_name"] == "Đà Lạt 3 ngày 2 đêm"
    assert result["party_size_checked"] is False


def test_discovery_returns_live_location_labels_for_agent_resolution(settings):
    result = json.loads(_tools(settings).discover_destinations(
        raw_text="Khởi hành từ TP.HCM",
        travelers=1,
        conditions=[{
            "id": "h1", "field": "departure_city", "operator": "contains",
            "value": "TP.HCM", "strength": "hard", "quote": "TP.HCM",
        }],
    ))

    assert result["status"] == "resolve_catalog_labels"
    assert result["unresolved"] == [{"field": "departure_city", "values": ["TP.HCM"]}]
    assert result["available_departure_cities"] == ["Hà Nội", "Sài Gòn"]


def test_discovery_accepts_multiple_observed_departure_labels(settings):
    result = json.loads(_tools(settings).discover_destinations(
        raw_text="Đi từ Sài Gòn hoặc Hà Nội tour 3 ngày",
        conditions=[
            {
                "id": "h1", "field": "departure_city", "operator": "any",
                "value": ["Sài Gòn", "Hà Nội"], "strength": "hard",
                "quote": "Sài Gòn hoặc Hà Nội",
            },
            {
                "id": "h2", "field": "duration_days", "operator": "eq",
                "value": 3, "strength": "hard", "quote": "3 ngày",
            },
        ],
    ))

    assert result["matching_tour_count"] == 2
    assert {item["destination"] for item in result["matching_destinations"]} == {"Đà Lạt", "Hạ Long"}


def test_ask_choice_restores_catalog_destination_spelling(settings):
    result = json.loads(_tools(settings).ask_choice(
        "Bạn muốn đi đâu?",
        [
            {"label": "Da Lat", "value": "Da Lat"},
            {"label": "Phu Quoc", "value": "Phu Quoc"},
            {"label": "Sapa", "value": "Sapa"},
        ],
    ))

    assert result["options"] == [
        {"label": "Đà Lạt", "value": "Đà Lạt"},
        {"label": "Phú Quốc", "value": "Phú Quốc"},
        {"label": "Sapa", "value": "Sapa"},
    ]


def test_agent_catalog_tools_use_data_scan_limit_not_api_default(settings):
    settings.candidate_limit = 1
    catalog = _RecordingCatalog()
    tools = AgentTools(settings, catalog, TourWorkflows(settings, catalog))

    facets = json.loads(tools.catalog_facets())
    _query(tools,
        raw_text="Muốn đi Phú Quốc",
        travelers=1,
        conditions=[{
            "id": "h1", "field": "destination", "operator": "contains", "value": "Phú Quốc",
            "strength": "hard", "quote": "Phú Quốc",
        }],
    )

    assert facets["scanned_tours"] == 3
    assert catalog.limits == [settings.supabase_scan_limit, settings.supabase_scan_limit]


def test_query_accepts_country_expansion_as_any_catalog_destination(settings):
    tools = _tools(settings)
    facets = json.loads(tools.catalog_facets())
    labels = facets["destinations"]
    result = _query(tools,
        raw_text="Việt Nam",
        travelers=1,
        conditions=[{
            "id": "h1", "field": "destination", "operator": "any", "value": labels,
            "strength": "hard", "quote": "Việt Nam",
        }],
    )

    assert len(labels) >= 2
    assert {item["tour_id"] for item in result["comparison"]["ranked"]} == {
        "dlv-dalat-3n", "vtr-phuquoc-4n", "sgt-halong-3n",
    }


def test_limited_comparison_shows_each_tour_once_across_departure_offers(settings):
    tools = _tools(settings)
    requirement = tools.workflows.requirement("Phú Quốc", [
        {"id": "h1", "field": "destination", "operator": "contains", "value": "Phú Quốc",
         "strength": "hard", "quote": "Phú Quốc"},
    ])
    comparison = Comparison(
        id="cmp_test",
        requirement=requirement,
        ranked=[
            RankedCandidate(tour_id="tour-a", offer_id="a1", score=1),
            RankedCandidate(tour_id="tour-a", offer_id="a2", score=1),
            RankedCandidate(tour_id="tour-b", offer_id="b1", score=1),
        ],
        near_miss=[
            RankedCandidate(tour_id="tour-a", offer_id="a3", score=1),
            RankedCandidate(tour_id="tour-c", offer_id="c1", score=1),
        ],
        tour_snapshots=[
            TourSnapshot(id="tour-a", offers=[
                OfferSnapshot(id=offer_id, tour_id="tour-a") for offer_id in ("a1", "a2", "a3")
            ]),
            TourSnapshot(id="tour-b", offers=[OfferSnapshot(id="b1", tour_id="tour-b")]),
            TourSnapshot(id="tour-c", offers=[OfferSnapshot(id="c1", tour_id="tour-c")]),
        ],
        evaluations=[
            Evaluation(offer_id=offer_id, condition_id="h1", state="pass")
            for offer_id in ("a1", "a2", "a3", "b1", "c1")
        ],
    )

    limited = limit_comparison(comparison, limit=5)

    assert [(item.tour_id, item.offer_id) for item in limited.ranked] == [
        ("tour-a", "a1"), ("tour-b", "b1"),
    ]
    assert [(item.tour_id, item.offer_id) for item in limited.near_miss] == [
        ("tour-c", "c1"),
    ]
    assert {tour.id for tour in limited.tour_snapshots} == {"tour-a", "tour-b", "tour-c"}
    assert {
        tour.id: {offer.id for offer in tour.offers}
        for tour in limited.tour_snapshots
    } == {"tour-a": {"a1"}, "tour-b": {"b1"}, "tour-c": {"c1"}}
    assert {item.offer_id for item in limited.evaluations} == {"a1", "b1", "c1"}


def test_query_keeps_candidate_payload_bounded(settings):
    tools = _tools(settings)
    result = _query(tools,
        raw_text="Ngân sách tối đa 10 triệu VND",
        travelers=1,
        conditions=[{
            "id": "h1", "field": "budget_max", "operator": "lte", "value": 10_000_000,
            "strength": "hard", "quote": "10 triệu VND",
        }],
    )
    assert "candidates" not in result
    assert result["scanned_tours"] == 3
    assert result["comparison"]["candidates_considered"] == 3
    assert result["comparison"]["ranked"]


def test_draft_requirement_does_not_query_catalog_and_assigns_equal_weights(settings):
    catalog = _RecordingCatalog()
    tools = AgentTools(settings, catalog, TourWorkflows(settings, catalog))
    result = json.loads(tools.draft_requirement(
        raw_text="Thích thiên nhiên và lịch trình nhẹ nhàng",
        travelers=1,
        conditions=[
            {"id": "s1", "field": "preference", "operator": "contains", "value": "thiên nhiên",
             "strength": "soft", "quote": "thiên nhiên"},
            {"id": "s2", "field": "preference", "operator": "contains", "value": "nhẹ nhàng",
             "strength": "soft", "quote": "lịch trình nhẹ nhàng"},
        ],
    ))

    assert result["requirement_draft"]["conditions"][0]["weight_percent"] == 50
    assert result["requirement_draft"]["conditions"][1]["weight_percent"] == 50
    assert catalog.limits == []


def test_soft_review_covers_every_hard_pass_tour_not_just_top_five(settings):
    class ManyTours:
        def list_tours(self, limit):
            return [TourRow(
                tour={
                    "record_key": f"tour-{index}",
                    "tour_name": f"Tour {index}",
                    "destinations": ["Đà Lạt"],
                    "itinerary": f"Lịch trình tour {index}",
                    "price_type": "fixed",
                },
                offers=[{
                    "record_key": f"offer-{index}",
                    "price": 1_000_000 + index,
                    "currency": "VND",
                    "departure_date": "2027-01-01",
                }],
            ) for index in range(7)][:limit]

    catalog = ManyTours()
    tools = AgentTools(settings, catalog, TourWorkflows(settings, catalog))
    result = _query(tools,
        raw_text="Tôi thích thiên nhiên",
        travelers=1,
        conditions=[{"id": "s1", "field": "preference", "operator": "contains",
                     "value": "thiên nhiên", "strength": "soft", "quote": "thiên nhiên",
                     "weight_percent": 100}],
    )

    assert result["soft_review"]["review_candidate_count"] == 7
    assert len(result["soft_review"]["candidates"]) == 5
    first_batch = result["soft_review"]
    next_batch = _score_soft(tools, first_batch["context_id"], [
        {"offer_id": item["offer_id"], "condition_id": "s1", "verdict": "unknown"}
        for item in first_batch["candidates"]
    ])["soft_review"]
    assert next_batch["batch_count"] == 2
    assert next_batch["review_candidate_count"] == 7
    assert len(next_batch["candidates"]) == 2


def test_soft_review_limits_each_group_and_expands_from_the_same_snapshot(settings):
    class ManyTours:
        def list_tours(self, limit):
            return [TourRow(
                provider={"display_name": f"Supplier {index % 4}"},
                tour={
                    "record_key": f"tour-{index}",
                    "tour_name": f"Tour {index}",
                    "destinations": ["Đà Lạt"],
                    "duration_days": 2 + index % 3,
                    "itinerary": f"Lịch trình tour {index}",
                    "price_type": "fixed",
                },
                offers=[{
                    "record_key": f"offer-{index}",
                    "price": 1_000_000 + index * 100_000,
                    "currency": "VND",
                    "departure_date": f"2027-{index % 12 + 1:02d}-01",
                }],
            ) for index in range(20)][:limit]

    catalog = ManyTours()
    tools = AgentTools(settings, catalog, TourWorkflows(settings, catalog))
    request = {
        "raw_text": "Đà Lạt, thích thiên nhiên",
        "travelers": 1,
        "ranking": {"order_by": [{"field": "price", "direction": "desc"}]},
        "conditions": [
            {"id": "h1", "field": "destination", "operator": "contains", "value": "Đà Lạt",
             "strength": "hard", "quote": "Đà Lạt"},
            {"id": "s1", "field": "preference", "operator": "contains", "value": "thiên nhiên",
             "strength": "soft", "quote": "thiên nhiên", "weight_percent": 100},
        ],
    }

    first_run = f"dec_{token_hex(16)}"
    first = json.loads(tools.query_tours(decision_run_id=first_run, **request))
    first_context = tools._ranking_contexts[first["soft_review"]["context_id"]]
    first_tour_ids = [tour.id for tour, _offer_id in first_context.candidates]
    assert first["soft_review"]["eligible_tours"] == 20
    assert first["soft_review"]["review_candidate_count"] == 15
    assert len(first_tour_ids) == 15
    assert len(set(first_tour_ids)) == 15
    assert first_tour_ids[0] == "tour-19"
    assert len({tour.supplier for tour, _offer_id in first_context.candidates}) > 1
    assert len({tour.offers[0].departure_date[:7] for tour, _offer_id in first_context.candidates}) > 1
    assert len({tour.duration_days for tour, _offer_id in first_context.candidates}) > 1

    while first.get("soft_review"):
        context = tools._ranking_contexts[first["soft_review"]["context_id"]]
        batch = context.batches[context.batch_index]
        first = _score_soft(tools, context.id, [
            {"offer_id": offer_id, "condition_id": "s1", "verdict": "unknown"}
            for _tour, offer_id in batch
        ])
    baseline = Comparison.model_validate(first["comparison"])
    assert baseline.soft_review is not None
    assert baseline.soft_review.evaluated_tours == 15
    assert baseline.soft_review.remaining_tours == 5
    assert baseline.decision_trace is not None
    assert baseline.decision_trace.scanned_tours == 20
    assert baseline.decision_trace.eligible_tours == 20

    owner = SessionStore(settings.database_url)
    owner_id = owner.create_session(3600)["id"]
    owner.save_decision_snapshot(baseline, owner_id)
    expansion_run = f"dec_{token_hex(16)}"
    owner.save_scenario_snapshot_handoff(expansion_run, baseline)
    expansion = json.loads(tools.query_tours(
        decision_run_id=expansion_run,
        snapshot_comparison_id=baseline.id,
        expand_soft_review=True,
        requirement_id=baseline.requirement.id,
        **request,
    ))
    expansion_context = tools._ranking_contexts[expansion["soft_review"]["context_id"]]
    next_tour_ids = [tour.id for tour, _offer_id in expansion_context.candidates]
    assert expansion["soft_review"]["eligible_tours"] == 20
    assert expansion["soft_review"]["evaluated_tours"] == 15
    assert expansion["soft_review"]["remaining_tours"] == 5
    assert len(next_tour_ids) == 5
    assert set(first_tour_ids).isdisjoint(next_tour_ids)

    while expansion.get("soft_review"):
        context = tools._ranking_contexts[expansion["soft_review"]["context_id"]]
        batch = context.batches[context.batch_index]
        expansion = _score_soft(tools, context.id, [
            {"offer_id": offer_id, "condition_id": "s1", "verdict": "unknown"}
            for _tour, offer_id in batch
        ])
    expanded = Comparison.model_validate(expansion["comparison"])
    assert expanded.expanded_from_comparison_id == baseline.id
    assert expanded.soft_review is not None
    assert expanded.soft_review.evaluated_tours == 20
    assert expanded.soft_review.remaining_tours == 0
    assert len(expanded.ranked) == 20
    assert expanded.decision_trace is not None
    assert expanded.decision_trace.scanned_tours == 20
    assert expanded.decision_trace.eligible_tours == 20
    assert baseline.soft_review.evaluated_tours == 15
    assert {item.tour_id for item in baseline.ranked} == set(first_tour_ids)
    owner.close()


def test_score_soft_accepts_verbatim_quote_for_hard_pass_offer(settings):
    tools = _tools(settings)
    query = _query(tools, **_phu_requirement())
    review = query["soft_review"]
    candidate = review["candidates"][0]
    result = _score_soft(tools, review["context_id"], [{
        "offer_id": candidate["offer_id"],
        "condition_id": "s1",
        "verdict": "fit",
        "quote": "VinWonders",
        "reason": "Có điểm vui chơi VinWonders trong lịch trình.",
    }])
    evaluation = next(
        item for item in result["comparison"]["evaluations"]
        if item["offer_id"] == candidate["offer_id"] and item["condition_id"] == "s1"
    )
    assert evaluation["state"] == "pass"
    assert evaluation["quote"] == "VinWonders"


def test_score_soft_rejects_quote_not_present_verbatim(settings):
    tools = _tools(settings)
    query = _query(tools, **_phu_requirement())
    review = query["soft_review"]
    candidate = review["candidates"][0]
    result = _score_soft(tools, review["context_id"], [{
        "offer_id": candidate["offer_id"],
        "condition_id": "s1",
        "verdict": "fit",
        "quote": "Có nhiều trò chơi tuyệt vời",
        "reason": "Nội dung nói tour có công viên.",
    }])
    evaluation = next(
        item for item in result["comparison"]["evaluations"]
        if item["offer_id"] == candidate["offer_id"] and item["condition_id"] == "s1"
    )
    assert evaluation["state"] == "unknown"
    assert evaluation["quote"] == ""


def test_score_soft_does_not_accept_verdict_for_hard_rejected_offer(settings):
    tools = _tools(settings)
    query = _query(tools, **_phu_requirement())
    review = query["soft_review"]
    with pytest.raises(AppError) as error:
        tools.score_soft(review["context_id"], [{
            "offer_id": "sgt-halong-3n-20261227",
            "condition_id": "s1",
            "verdict": "fit",
            "quote": "Ngày 2: Vịnh Lan Hạ",
            "reason": "Có hoạt động tham quan trên vịnh.",
        }], [])
    assert error.value.code == "SOFT_BATCH_INCOMPLETE"


def test_clarify_date_resolves_lunar_dates_to_iso(settings):
    result = json.loads(_tools(settings).clarify_date("lunar", 2026, 12, 27))
    assert result == {"calendar": "lunar", "iso_date": "2027-02-03", "valid": True}


def test_ask_choice_limits_to_distinct_options(settings):
    result = json.loads(_tools(settings).ask_choice(
        "Bạn muốn đi đâu?",
        [{"label": "Đà Lạt", "value": "dalat"}, {"label": "Đà Lạt 2", "value": "dalat"},
         {"label": "Phú Quốc", "value": "phuquoc"}],
    ))
    assert [item["value"] for item in result["options"]] == ["dalat", "phuquoc"]
    assert result["allow_custom"] is True


def test_empty_turn_falls_back_to_retry_text(settings):
    """A turn whose tools all error must still hand the UI a message."""
    from backend.agent.service import AgentService
    from backend.data.sessions import SessionStore

    async def fake_events(message, session_id):
        yield {
            "type": "message",
            "part": {"tool": "query_tours",
                     "state": {"status": "error", "input": {}}},
        }

    async def collect(stream):
        return [event async for event in stream]

    service = AgentService(settings, SessionStore(settings.database_url))
    owner = service.store.create_session(3600)["id"]
    local_id = service.store.create_agent_session(owner)
    service.runner.events = fake_events
    events = asyncio.run(collect(service.stream_message(owner, local_id, "hello")))
    response = next(event["response"] for event in events if event.get("type") == "result")
    assert response["assistant_text"] != ""
    assert "comparison" not in response
    assert "choices" not in response
    service.store.close()


def test_snap_quote_expands_mid_word_cuts_to_word_boundaries():
    from backend.agent.mcp_server import _snap_quote

    source = "Du ngoạn sông nước miền Tây. Thưởng thức món ăn."
    assert (
        _snap_quote(source, "u ngoạn sông nước miền Tây. Thưởng thức món", 3)
        == "Du ngoạn sông nước miền Tây. Thưởng thức món"
    )
    assert _snap_quote("Thưởng thức", "ưởng thứ", 3) == "Thưởng thức"


def test_snap_quote_keeps_clean_quotes_byte_identical():
    from backend.agent.mcp_server import _snap_quote

    source = "Hủy trước 7 ngày hoàn 100%."
    assert _snap_quote(source, source, 3) == source


def test_snap_quote_rejects_absent_empty_and_over_cap_quotes():
    from backend.agent.mcp_server import _snap_quote

    source = "Ngày 1: đi. Ngày 2: về. Ngày 3: nghỉ. Ngày 4: về."
    assert _snap_quote(source, "không có trong nguồn", 3) is None
    assert _snap_quote(source, source, 3) is None
    assert _snap_quote(source, "   ", 3) is None


def _evaluation_for(result, candidate, condition_id):
    return next(
        item for item in result["comparison"]["evaluations"]
        if item["offer_id"] == candidate["offer_id"] and item["condition_id"] == condition_id
    )


def test_score_soft_snaps_mid_word_quote_to_word_boundaries(settings):
    tools = _tools(settings)
    query = _query(tools, **_phu_requirement())
    review = query["soft_review"]
    candidate = review["candidates"][0]
    result = _score_soft(tools, review["context_id"], [{
        "offer_id": candidate["offer_id"],
        "condition_id": "s1",
        "verdict": "fit",
        "quote": "ài Gòn - Phú Quốc, tắm biển Bãi S",
        "reason": "Lịch trình nêu tắm biển Bãi Sao.",
    }])
    evaluation = _evaluation_for(result, candidate, "s1")
    assert evaluation["state"] == "pass"
    assert evaluation["quote"] == "Sài Gòn - Phú Quốc, tắm biển Bãi Sao"


def test_score_soft_rejects_quote_over_sentence_cap(settings):
    tools = _tools(settings)
    query = _query(tools, **_phu_requirement())
    review = query["soft_review"]
    candidate = review["candidates"][0]
    long_quote = (
        "Ngày 1: Bay Sài Gòn - Phú Quốc, tắm biển Bãi Sao. "
        "Ngày 2: VinWonders, Safari. "
        "Ngày 3: Tour 4 đảo, lặn ngắm san hô. "
        "Ngày 4: Chợ Dương Đông, bay về."
    )
    result = _score_soft(tools, review["context_id"], [{
        "offer_id": candidate["offer_id"],
        "condition_id": "s1",
        "verdict": "fit",
        "quote": long_quote,
        "reason": "Lịch trình dài bốn ngày.",
    }])
    evaluation = _evaluation_for(result, candidate, "s1")
    assert evaluation["state"] == "unknown"
    assert evaluation["quote"] == ""


def test_condition_operator_accepts_equals_alias():
    from backend.agent.mcp_server import QueryConditionInput

    item = QueryConditionInput.model_validate({
        "id": "c1",
        "field": "duration_days",
        "operator": "equals",
        "value": 2,
        "strength": "hard",
        "quote": "2 ngày",
    })
    assert item.operator == "eq"


def test_condition_operator_still_rejects_unknown_operators():
    from pydantic import ValidationError

    from backend.agent.mcp_server import QueryConditionInput

    with pytest.raises(ValidationError):
        QueryConditionInput.model_validate({
            "id": "c1",
            "field": "duration_days",
            "operator": "equal_to",
            "value": 2,
            "strength": "hard",
            "quote": "2 ngày",
        })
def _tools_with_store(settings):
    catalog = StaticCatalog()
    store = SessionStore(settings.database_url)
    tools = AgentTools(settings, catalog, TourWorkflows(settings, catalog), result_store=store)
    return tools, store


def test_draft_requirement_resolves_quotes_from_conversation_token(settings):
    tools, store = _tools_with_store(settings)
    try:
        store.save_conversation_turn("agt_conv1", "Nhóm 5 người lớn, đi Đà Lạt 2 ngày")
        store.save_conversation_turn("agt_conv1", "ok")
        result = json.loads(tools.draft_requirement(
            raw_text="ok",
            conditions=[{"id": "h1", "field": "duration_days", "operator": "eq",
                         "value": 2, "strength": "hard", "quote": "2 ngày"}],
            travelers=5,
            conversation_id="agt_conv1",
        ))
        assert result["requirement_draft"]["travelers"] == 5
    finally:
        store.close()


def test_unknown_conversation_token_falls_back_to_raw_text(settings):
    tools, store = _tools_with_store(settings)
    try:
        with pytest.raises(AppError, match="exact quote"):
            tools.draft_requirement(
                raw_text="ok",
                conditions=[{"id": "h1", "field": "duration_days", "operator": "eq",
                             "value": 2, "strength": "hard", "quote": "2 ngày"}],
                conversation_id="agt_unknown",
            )
    finally:
        store.close()


def test_tool_schema_exposes_enum_guidance_and_conversation_token(settings):
    import inspect

    fields = QueryConditionInput.model_fields
    assert all(tok in fields["operator"].description for tok in ("contains", "any", "eq", "lte"))
    assert "flight" in fields["value"].description
    assert "departure_dates" in AgentTools.catalog_facets.__doc__
    for name in ("discover_destinations", "draft_requirement", "query_tours"):
        assert "conversation_id" in inspect.signature(getattr(AgentTools, name)).parameters
def test_metric_facts_error_names_missing_tours_and_minimal_shape(settings):
    tools = _tools(settings)
    query = _query(tools, **_phu_requirement())
    review = query["soft_review"]
    context = tools._ranking_contexts[review["context_id"]]
    batch = context.batches[context.batch_index]
    verdicts = [
        {"offer_id": offer_id, "condition_id": condition.id,
         "verdict": "unknown", "quote": "", "reason": "x"}
        for _, offer_id in batch
        for condition in context.requirement.soft()
    ]
    with pytest.raises(AppError) as exc:
        tools.score_soft(review["context_id"], verdicts, [])
    assert exc.value.code == "METRIC_FACTS_INCOMPLETE"
    missing = {tour.id for tour, _ in batch}
    assert any(tour_id in exc.value.message for tour_id in missing)
    assert "reviewed_fields" in exc.value.message


def test_soft_batch_error_names_missing_verdict_pairs(settings):
    tools = _tools(settings)
    query = _query(tools, **_phu_requirement())
    review = query["soft_review"]
    with pytest.raises(AppError) as exc:
        tools.score_soft(review["context_id"], [], [{"tour_id": "t-nope"}])
    assert exc.value.code == "SOFT_BATCH_INCOMPLETE"
    assert "Missing" in exc.value.message
