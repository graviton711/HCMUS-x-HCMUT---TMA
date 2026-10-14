"""MCP contract: schema-grounded catalog tools, exact quotes and hard-pass gating."""

import asyncio
import json

import pytest

from backend.agent.mcp_server import AgentTools, create_server
from backend.agent.results import limit_comparison
from backend.data.catalog import FixtureCatalog
from backend.errors import AppError
from backend.models import Comparison, Evaluation, RankedCandidate, TourSnapshot
from backend.workflows import TourWorkflows


def _tools(settings):
    catalog = FixtureCatalog()
    return AgentTools(settings, catalog, TourWorkflows(settings, catalog))


class _RecordingCatalog:
    def __init__(self):
        self.fixture = FixtureCatalog()
        self.limits = []

    def list_tours(self, limit):
        self.limits.append(limit)
        return self.fixture.list_tours(limit)


def _phu_requirement():
    return {
        "raw_text": "Muốn đi Phú Quốc, thích công viên",
        "travelers": 1,
        "conditions": [
            {"id": "h1", "field": "destination", "operator": "contains", "value": "Phú Quốc",
             "strength": "hard", "quote": "Phú Quốc"},
            {"id": "s1", "field": "preference", "operator": "contains", "value": "công viên",
             "strength": "soft", "quote": "thích công viên"},
        ],
    }


def test_query_tours_mcp_schema_requires_complete_condition_contract(settings):
    tools = asyncio.run(create_server(settings).list_tools())
    schema = next(tool.inputSchema for tool in tools if tool.name == "query_tours")
    condition = schema["$defs"]["QueryConditionInput"]

    assert set(condition["required"]) == {
        "id", "field", "operator", "value", "strength", "quote",
    }
    assert condition["additionalProperties"] is False


def test_catalog_facets_only_returns_values_from_active_fixture(settings):
    result = json.loads(_tools(settings).catalog_facets())
    assert result["destinations"] == ["Hạ Long", "Phú Quốc", "Đà Lạt"]
    assert "2026-12-26" in result["departure_dates"]
    assert 12_900_000 in result["prices_vnd"]
    assert result["scanned_tours"] == 3
    assert result["scan_limit"] == settings.supabase_scan_limit


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
    tools.query_tours(
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
    result = json.loads(tools.query_tours(
        raw_text="Việt Nam",
        travelers=1,
        conditions=[{
            "id": "h1", "field": "destination", "operator": "any", "value": labels,
            "strength": "hard", "quote": "Việt Nam",
        }],
    ))

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
        tour_snapshots=[TourSnapshot(id=f"tour-{letter}") for letter in "abc"],
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
    assert {item.offer_id for item in limited.evaluations} == {"a1", "b1", "c1"}


def test_query_keeps_candidate_payload_bounded(settings):
    tools = _tools(settings)
    result = json.loads(tools.query_tours(
        raw_text="Ngân sách tối đa 10 triệu VND",
        travelers=1,
        conditions=[{
            "id": "h1", "field": "budget_max", "operator": "lte", "value": 10_000_000,
            "strength": "hard", "quote": "10 triệu VND",
        }],
    ))
    assert "candidates" not in result
    assert result["scanned_tours"] == 3
    assert result["comparison"]["candidates_considered"] == 3
    assert result["comparison"]["ranked"]


def test_score_soft_accepts_verbatim_quote_for_hard_pass_offer(settings):
    tools = _tools(settings)
    query = json.loads(tools.query_tours(**_phu_requirement()))
    review = query["soft_review"]
    candidate = review["candidates"][0]
    result = json.loads(tools.score_soft(review["context_id"], [{
        "offer_id": candidate["offer_id"],
        "condition_id": "s1",
        "verdict": "fit",
        "quote": "VinWonders",
        "reason": "Có điểm vui chơi VinWonders trong lịch trình.",
    }]))
    evaluation = next(
        item for item in result["comparison"]["evaluations"]
        if item["offer_id"] == candidate["offer_id"] and item["condition_id"] == "s1"
    )
    assert evaluation["state"] == "pass"
    assert evaluation["quote"] == "VinWonders"


def test_score_soft_rejects_quote_not_present_verbatim(settings):
    tools = _tools(settings)
    query = json.loads(tools.query_tours(**_phu_requirement()))
    review = query["soft_review"]
    candidate = review["candidates"][0]
    result = json.loads(tools.score_soft(review["context_id"], [{
        "offer_id": candidate["offer_id"],
        "condition_id": "s1",
        "verdict": "fit",
        "quote": "Có nhiều trò chơi tuyệt vời",
        "reason": "Nội dung nói tour có công viên.",
    }]))
    evaluation = next(
        item for item in result["comparison"]["evaluations"]
        if item["offer_id"] == candidate["offer_id"] and item["condition_id"] == "s1"
    )
    assert evaluation["state"] == "unknown"
    assert evaluation["quote"] == ""


def test_score_soft_does_not_accept_verdict_for_hard_rejected_offer(settings):
    tools = _tools(settings)
    query = json.loads(tools.query_tours(**_phu_requirement()))
    review = query["soft_review"]
    with pytest.raises(AppError) as error:
        tools.score_soft(review["context_id"], [{
            "offer_id": "sgt-halong-3n-20261227",
            "condition_id": "s1",
            "verdict": "fit",
            "quote": "Ngày 2: Vịnh Lan Hạ",
            "reason": "Có hoạt động tham quan trên vịnh.",
        }])
    assert error.value.code == "SOFT_BATCH_INCOMPLETE"


def test_relax_removes_only_the_requested_hard_condition(settings):
    tools = _tools(settings)
    requirement = {
        "raw_text": "Phú Quốc giá tối đa 1000000 VND",
        "travelers": 1,
        "conditions": [
            {"id": "h1", "field": "destination", "operator": "contains", "value": "Phú Quốc",
             "strength": "hard", "quote": "Phú Quốc"},
            {"id": "h2", "field": "budget_max", "operator": "lte", "value": 1_000_000,
             "strength": "hard", "quote": "1000000 VND"},
        ],
    }
    result = json.loads(tools.relax_criterion(requirement, "h2"))
    assert [condition["id"] for condition in result["requirement"]["conditions"]] == ["h1"]
    assert result["removed_condition"]["id"] == "h2"


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
            "part": {"tool": "tour-catalog_task",
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
