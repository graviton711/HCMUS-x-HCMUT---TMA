"""Decision completion remains reliable when OpenCode omits tool output."""

import asyncio
import json
import logging
import re

import pytest
from sample_rows import StaticCatalog

from backend.agent.codex_runner import normalize_codex_event
from backend.agent.mcp_server import AgentTools
from backend.agent.service import (
    AgentService,
    _tool_invocations,
    _tool_name,
    _tool_progress_message,
)
from backend.data.sessions import SessionStore
from backend.errors import AppError
from backend.models import uid
from backend.workflows import TourWorkflows


def test_draft_requirement_progress_has_a_specific_user_facing_label():
    tool_name = _tool_name("tour_catalog_draft_requirement")
    assert _tool_progress_message(tool_name, {}) == "Chuẩn bị bản điều kiện để bạn xem"


def test_discovery_progress_describes_the_catalog_filter():
    assert _tool_name("tour_catalog_discover_destinations") == "discover_destinations"
    assert _tool_progress_message("discover_destinations", {}) == "Lọc điểm đến theo các điều kiện đã biết"


def test_message_uses_final_text_message_and_deduplicates_parts(settings, caplog):
    settings = settings.model_copy(update={"database_url": "sqlite:///:memory:"})
    store = SessionStore(settings.database_url)
    service = AgentService(settings, store)
    owner_id = store.create_session(3600)["id"]
    local_id = store.create_agent_session(owner_id)

    async def fake_events(_message, _session_id):
        yield {"type": "text", "part": {
            "id": "part-1", "messageID": "message-1", "text": "Chào bạn, tôi sẽ kiểm tra."
        }}
        yield {"type": "text", "part": {
            "id": "part-2", "messageID": "message-2", "text": "Chào bạn, tôi sẵn sàng hỗ trợ."
        }}
        final_part = {
            "id": "part-3", "messageID": "message-3", "text": "Chào bạn, rất vui được hỗ trợ."
        }
        yield {"type": "text", "part": final_part}
        yield {"type": "text", "part": final_part}
        yield {"type": "text", "part": {
            "id": "part-4", "messageID": "message-3", "text": "Bạn muốn đi đâu?"
        }}
        yield {"type": "text", "part": {
            "id": "synthetic", "messageID": "message-3", "text": "internal", "synthetic": True
        }}
        yield {"type": "text", "part": {
            "id": "ignored", "messageID": "message-3", "text": "ignored", "ignored": True
        }}
        yield {"type": "text", "part": {
            "id": "commentary", "messageID": "message-3", "text": "working",
            "metadata": {"openai": {"phase": "commentary"}},
        }}

    service.runner.events = fake_events
    caplog.set_level(logging.INFO, logger="mlai.backend.agent.service")

    response = asyncio.run(service.message(owner_id, local_id, "chào"))

    assert response["assistant_text"] == "Chào bạn, rất vui được hỗ trợ.\n\nBạn muốn đi đâu?"
    assert "tôi sẽ kiểm tra" not in response["assistant_text"]
    assert "tôi sẵn sàng hỗ trợ" not in response["assistant_text"]
    assert "agent_text_aggregation message_count=3 part_count=4 duplicate_events=1 filtered_parts=3" in caplog.text
    assert "Chào bạn" not in caplog.text
    assert "Bạn muốn đi đâu?" not in caplog.text
    store.close()


def test_codex_thread_is_reused_for_follow_up_messages(settings):
    settings = settings.model_copy(update={
        "database_url": "sqlite:///:memory:",
        "agent_provider": "codex",
    })
    store = SessionStore(settings.database_url)
    service = AgentService(settings, store)
    owner_id = store.create_session(3600)["id"]
    local_id = store.create_agent_session(owner_id)
    thread_id = "01900123-abcd-4567-8901-234567890123"
    resumed_with: list[str | None] = []

    async def fake_events(_message, received_thread_id):
        resumed_with.append(received_thread_id)
        if received_thread_id is None:
            yield {"type": "session", "sessionID": thread_id}
        yield {"type": "text", "part": {
            "id": "part-1", "messageID": f"message-{len(resumed_with)}", "text": "Đã hiểu."
        }}

    service.runner.events = fake_events
    asyncio.run(service.message(owner_id, local_id, "Tin nhắn đầu"))
    asyncio.run(service.message(owner_id, local_id, "Tin nhắn tiếp theo"))

    assert resumed_with == [None, thread_id]
    assert store.get_agent_session(local_id, owner_id, "codex") == thread_id
    store.close()


def test_expired_codex_thread_is_cleared_before_retry_starts_a_new_thread(settings):
    settings = settings.model_copy(update={
        "database_url": "sqlite:///:memory:",
        "agent_provider": "codex",
    })
    store = SessionStore(settings.database_url)
    service = AgentService(settings, store)
    owner_id = store.create_session(3600)["id"]
    local_id = store.create_agent_session(owner_id)
    store.save_agent_session(local_id, owner_id, "01900123-abcd-4567-8901-234567890123", "codex")

    async def fake_events(_message, thread_id):
        if thread_id:
            yield {
                "type": "error",
                "error": {"code": "CODEX_THREAD_EXPIRED", "message": "expired"},
            }
            return
        yield {"type": "session", "sessionID": "01900124-abcd-4567-8901-234567890123"}
        yield {"type": "text", "part": {"id": "p1", "messageID": "m1", "text": "Mình sẽ tiếp tục."}}

    service.runner.events = fake_events
    with pytest.raises(AppError) as exc:
        asyncio.run(service.message(owner_id, local_id, "tiếp tục"))
    assert exc.value.code == "CODEX_THREAD_EXPIRED"
    assert store.get_agent_session(local_id, owner_id, "codex") is None

    response = asyncio.run(service.message(owner_id, local_id, "tiếp tục"))
    assert response["assistant_text"] == "Mình sẽ tiếp tục."
    assert store.get_agent_session(local_id, owner_id, "codex") == "01900124-abcd-4567-8901-234567890123"
    store.close()


def test_departure_date_range_progress_does_not_call_the_upper_bound_a_return_date():
    from backend.agent.service import _condition_activity

    assert _condition_activity({"field": "date_from", "value": "2026-11-21"}) == (
        "ngày đi 2026-11-21"
    )
    assert _condition_activity({"field": "date_to", "value": "2026-11-30"}) == (
        "ngày khởi hành đến 2026-11-30"
    )


def test_normalizes_opencode_sanitized_mcp_tool_names():
    assert _tool_name("tour_catalog_draft_requirement") == "draft_requirement"
    assert _tool_name("tour-catalog_query_tours") == "query_tours"
    assert _tool_name("tour-catalog.draft_requirement") == "draft_requirement"


def test_code_mode_execute_recovers_nested_draft_result(settings, caplog):
    caplog.set_level(logging.INFO, logger="mlai.backend.agent.service")
    settings = settings.model_copy(update={"database_url": "sqlite:///:memory:"})
    store = SessionStore(settings.database_url)
    service = AgentService(settings, store)
    owner_id = store.create_session(3600)["id"]
    local_id = store.create_agent_session(owner_id)
    catalog = StaticCatalog()
    workflows = TourWorkflows(settings, catalog)
    tools = AgentTools(settings, catalog, workflows, result_store=store)
    raw_text = "Group of five, duration 2 days, departing TP.HCM."
    params = {
        "raw_text": raw_text,
        "travelers": 5,
        "conditions": [
            {
                "id": "c1",
                "field": "departure_city",
                "operator": "contains",
                "value": "TP.HCM",
                "strength": "hard",
                "quote": "TP.HCM",
            },
            {
                "id": "c2",
                "field": "duration_days",
                "operator": "eq",
                "value": 2,
                "strength": "hard",
                "quote": "2 days",
            },
        ],
    }
    draft_payload = json.loads(tools.draft_requirement(**params))

    async def fake_events(_message, _session_id):
        # OpenCode Code Mode first attempted its wrapper without the required `code` field.
        yield {
            "type": "tool",
            "part": {
                "name": "execute",
                "id": "execute-invalid",
                "state": {
                    "status": "error",
                    "error": {"type": "tool.execution", "message": "Missing key: code"},
                },
            },
        }
        # Current OpenCode nests Code Mode calls one level below metadata and
        # returns the wrapper output as a JSON string.
        yield {
            "type": "tool_use",
            "part": {
                "type": "tool",
                "tool": "execute",
                "callID": "execute-draft",
                "state": {
                    "status": "completed",
                    "input": {"code": "call draft_requirement"},
                    "metadata": {
                        "metadata": {
                            "toolCalls": [
                                {
                                    "tool": "tour-catalog.draft_requirement",
                                    "status": "completed",
                                    "input": params,
                                }
                            ]
                        }
                    },
                    "output": json.dumps({"result": draft_payload}),
                },
            },
        }
        yield {"type": "text", "part": {"text": "Bản điều kiện đã sẵn sàng."}}

    service.runner.events = fake_events

    async def collect():
        return [event async for event in service.stream_message(owner_id, local_id, raw_text)]

    events = asyncio.run(collect())
    response = next(event["response"] for event in events if event.get("type") == "result")
    tool_events = [event for event in events if event.get("type") == "tool"]

    assert response["decision_draft"]["travelers"] == 5
    assert [call["name"] for call in response["tool_calls"]] == ["draft_requirement"]
    assert [(event["name"], event["status"]) for event in tool_events] == [
        ("draft_requirement", "completed")
    ]
    assert "agent_tool name=draft_requirement status=completed" in caplog.text
    assert "agent_draft_parse valid=True" in caplog.text
    assert "agent_turn_completed operation=message decision_draft_attached=True" in caplog.text
    assert raw_text not in caplog.text
    store.close()


def test_code_mode_preserves_real_nested_mcp_failures():
    part = {
        "name": "execute",
        "id": "execute-with-mcp-error",
        "state": {
            "status": "completed",
            "metadata": {
                "toolCalls": [
                    {
                        "tool": "tour-catalog.catalog_facets",
                        "status": "error",
                        "input": {},
                    }
                ]
            },
        },
    }

    invocations = _tool_invocations(part, part["state"])

    assert invocations == [
        {
            "id": "execute-with-mcp-error-0",
            "name": "catalog_facets",
            "status": "error",
            "input": {},
        }
    ]


def test_decision_uses_persisted_result_when_codex_turn_errors_after_tools(settings):
    settings = settings.model_copy(update={
        "database_url": "sqlite:///:memory:",
        "agent_provider": "codex",
    })
    store = SessionStore(settings.database_url)
    service = AgentService(settings, store)
    owner_id = store.create_session(3600)["id"]
    local_id = store.create_agent_session(owner_id)
    catalog = StaticCatalog()
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

    def codex_tool_event(call_id, name, arguments, result):
        raw_event = {
            "type": "item.completed",
            "turn_id": "turn-12345678",
            "item": {
                "id": call_id,
                "type": "mcp_tool_call",
                "server": "tour-catalog",
                "tool": name,
                "arguments": arguments,
                "result": [{"type": "text", "text": json.dumps(result)}],
                "status": "completed",
            },
        }
        return normalize_codex_event(raw_event)

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
        for event in codex_tool_event("tool-query-1", "query_tours", params, query_result):
            yield event

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
            metric_facts = [
                {"tour_id": candidate["tour_id"], "reviewed_fields": []}
                for candidate in review["candidates"]
            ]
            tool_output = json.loads(tools.score_soft(review["context_id"], verdicts, metric_facts))
            for event in codex_tool_event(
                f"tool-score-{review['context_id']}",
                "score_soft",
                {"verdicts": verdicts, "metric_facts": metric_facts},
                tool_output,
            ):
                yield event
            query_result = tool_output

        assert query_result["ranking_complete"] is True
        assert "comparison" not in query_result
        yield {"type": "session", "sessionID": "01900123-abcd-4567-8901-234567890123"}
        yield normalize_codex_event({
            "type": "turn.failed",
            "error": {"http_status": 502, "message": "transient provider error"},
        })[0]

    service.runner.events = fake_events

    async def collect():
        return [
            event async for event in service.stream_decision(owner_id, local_id, requirement)
        ]

    events = asyncio.run(collect())
    response = next(event["response"] for event in events if event.get("type") == "result")

    assert response["comparison"]["requirement"]["id"] == requirement.id
    assert response["comparison"]["decision_views"]
    assert store.get_agent_session(local_id, owner_id, "codex") == "01900123-abcd-4567-8901-234567890123"
    saved = store.get_comparison(response["comparison"]["id"], owner_id)
    assert saved.requirement == requirement
    store.close()
def test_message_saves_turn_and_passes_conversation_header(settings):
    settings = settings.model_copy(update={"database_url": "sqlite:///:memory:"})
    store = SessionStore(settings.database_url)
    service = AgentService(settings, store)
    owner_id = store.create_session(3600)["id"]
    local_id = store.create_agent_session(owner_id)
    seen: list[str] = []

    async def fake_events(message, _session_id):
        seen.append(message)
        yield {"type": "text", "part": {"id": "p1", "messageID": "m1", "text": "ok"}}

    service.runner.events = fake_events
    asyncio.run(service.message(owner_id, local_id, "Đi Đà Lạt"))

    assert store.get_conversation_text(local_id) == "Đi Đà Lạt"
    assert seen[0].startswith(f"Conversation {local_id}")
    assert seen[0].endswith("Đi Đà Lạt")
    store.close()
