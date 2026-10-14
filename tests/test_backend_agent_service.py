"""Decision completion remains reliable when OpenCode omits tool output."""

import asyncio
import json
import re

from backend.agent.mcp_server import AgentTools
from backend.agent.service import AgentService
from backend.data.catalog import FixtureCatalog
from backend.data.sessions import SessionStore
from backend.models import uid
from backend.workflows import TourWorkflows


def test_decision_uses_persisted_result_when_opencode_turn_errors_after_tools(settings):
    settings = settings.model_copy(update={"database_url": "sqlite:///:memory:"})
    store = SessionStore(settings.database_url)
    service = AgentService(settings, store)
    owner_id = store.create_session(3600)["id"]
    local_id = store.create_agent_session(owner_id)
    catalog = FixtureCatalog()
    workflows = TourWorkflows(settings, catalog)
    requirement = workflows.requirement(
        "Tour Phú Quốc, thích công viên",
        [
            {
                "id": "h1",
                "field": "destination",
                "operator": "contains",
                "value": "Phú Quốc",
                "strength": "hard",
                "quote": "Phú Quốc",
            },
            {
                "id": "s1",
                "field": "preference",
                "operator": "contains",
                "value": "công viên",
                "strength": "soft",
                "quote": "thích công viên",
                "weight_percent": 100,
            },
        ],
        requirement_id=uid("req"),
        require_weights=True,
    )
    tools = AgentTools(settings, catalog, workflows, result_store=store)

    async def fake_events(message, _session_id):
        run_match = re.search(r"DECISION_RUN_ID=(dec_[0-9a-f]{32})", message)
        assert run_match is not None
        run_id = run_match.group(1)
        requirement_data = json.loads(message.split("REQUIREMENT_JSON=", 1)[1])
        params = {
            key: requirement_data[key]
            for key in ("raw_text", "conditions", "travelers", "ranking")
            if key in requirement_data
        }
        params["requirement_id"] = requirement_data["id"]
        params["decision_run_id"] = run_id

        query_result = json.loads(tools.query_tours(**params))
        yield {
            "type": "tool",
            "part": {
                "tool": "tour-catalog_query_tours",
                "state": {"status": "completed", "input": params},
            },
        }

        while "soft_review" in query_result:
            review = query_result["soft_review"]
            verdicts = [
                {
                    "offer_id": candidate["offer_id"],
                    "condition_id": condition["id"],
                    "verdict": "unknown",
                }
                for candidate in review["candidates"]
                for condition in review["soft_conditions"]
            ]
            tool_output = json.loads(tools.score_soft(review["context_id"], verdicts))
            yield {
                "type": "tool",
                "part": {
                    "tool": "tour-catalog_score_soft",
                    "state": {"status": "completed", "input": {"verdicts": verdicts}},
                },
            }
            query_result = tool_output

        assert query_result["ranking_complete"] is True
        assert "comparison" not in query_result
        yield {
            "type": "error",
            "error": {"data": {"statusCode": 502}},
        }

    service.runner.events = fake_events

    async def collect():
        return [
            event async for event in service.stream_decision(owner_id, local_id, requirement)
        ]

    events = asyncio.run(collect())
    response = next(event["response"] for event in events if event.get("type") == "result")

    assert response["comparison"]["requirement"]["id"] == requirement.id
    assert response["comparison"]["decision_views"]
    saved = store.get_comparison(response["comparison"]["id"], owner_id)
    assert saved.requirement == requirement
    store.close()
