"""API: health → requirement → comparison → fetch. Static offline catalog."""

import logging

from fastapi.testclient import TestClient
from sample_rows import StaticCatalog

from backend.agent.runner import OpenCodeRunner
from backend.agent.service import AgentService
from backend.api import create_app


def _client(tmp_path, **overrides):
    from unittest.mock import patch

    from backend.settings import Settings

    settings = Settings.load(database_url=f"sqlite:///{tmp_path / 'api.db'}", **overrides)
    assert settings.data_provider == "supabase"
    with patch("backend.api.for_settings", return_value=StaticCatalog()):
        return TestClient(create_app(settings))


def test_health_includes_a_correlated_request_id(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="mlai.backend.request")
    client = _client(tmp_path)

    response = client.get("/health")
    request_id = response.headers["x-request-id"]

    assert response.json()["status"] == "ok"
    assert response.json()["version"]
    assert len(request_id) == 32
    assert any(getattr(record, "request_id", None) == request_id for record in caplog.records)


def test_full_compare_flow(tmp_path):
    client = _client(tmp_path)
    req = client.post(
        "/requirements",
        json={"text": "ignored free text", "form": {
            "destinations": ["Đà Lạt"], "duration_days": 3, "departure_city": "Sài Gòn",
            "budget_max": 8_000_000,
        }},
    ).json()["requirement"]
    assert req["id"]
    assert "destination" not in req["missing"]

    comp = client.post("/comparisons", json={"requirement_id": req["id"]}).json()["comparison"]
    assert comp["ranked"], "sample Đà Lạt under 8tr must rank"
    assert comp["tour_snapshots"]
    assert comp["analysis"]["benefits"]
    assert comp["decision_trace"]["scanned_tours"] == comp["candidates_considered"]
    assert comp["decision_trace"]["scanned_offers"] >= comp["decision_trace"]["eligible_offers"]

    page = client.get(f"/comparisons/{comp['id']}/eliminated?limit=1").json()
    assert page["total"] == comp["decision_trace"]["excluded_offers"]
    if page["items"]:
        assert page["items"][0]["conditions"]
        assert page["items"][0]["conditions"][0]["state"] in {"pass", "fail", "unknown"}
    if page["next_cursor"]:
        next_page = client.get(
            f"/comparisons/{comp['id']}/eliminated?limit=1&cursor={page['next_cursor']}"
        ).json()
        assert next_page["items"][0]["offer"]["id"] != page["items"][0]["offer"]["id"]

    filtered = client.get(
        f"/comparisons/{comp['id']}/eliminated?condition_id=h1"
    ).json()
    assert filtered["total"] >= 1
    assert filtered["total"] == len(filtered["items"])
    for item in filtered["items"]:
        assert any(
            condition["condition_id"] == "h1" for condition in item["conditions"]
        )
    empty = client.get(
        f"/comparisons/{comp['id']}/eliminated?condition_id=nope"
    ).json()
    assert empty == {"comparison_id": comp["id"], "items": [], "limit": 25,
                     "next_cursor": None, "total": 0}

    cost_scenario = client.post(
        f"/comparisons/{comp['id']}/scenarios",
        json={"kind": "cost", "assumptions": {
            "travelers": 1, "traveler_mix": {"adult": 1}, "rooms": 1,
            "single_rooms": 0, "nights": 2,
        }},
    )
    assert cost_scenario.status_code == 200
    assert cost_scenario.json()["scenario"]["source_comparison_id"] == comp["id"]
    assert cost_scenario.json()["scenario"]["items"]

    again = client.get(f"/comparisons/{comp['id']}").json()["comparison"]
    assert again["id"] == comp["id"]
    assert again["tour_snapshots"] == comp["tour_snapshots"]


def test_criteria_scenario_uses_baseline_snapshot_without_replacing_it(tmp_path, monkeypatch):
    calls = {}

    async def fake_decision(_self, owner_id, agent_session_id, requirement, snapshot_comparison_id=None):
        calls.update(
            owner_id=owner_id,
            agent_session_id=agent_session_id,
            requirement_id=requirement.id,
            source_id=snapshot_comparison_id,
        )
        return {
            "comparison": {
                "id": "scenario-comparison",
                "scenario_source_comparison_id": snapshot_comparison_id,
            }
        }

    monkeypatch.setattr(AgentService, "decision", fake_decision)
    monkeypatch.setattr(OpenCodeRunner, "_executable", lambda _self: "opencode")
    client = _client(tmp_path, opencode_server_url="http://127.0.0.1:4098")
    session = client.post("/sessions").json()
    headers = {"Authorization": f"Bearer {session['token']}"}
    requirement = client.post(
        "/requirements", headers=headers, json={"form": {"destinations": ["Da Lat"]}}
    ).json()["requirement"]
    baseline = client.post(
        "/comparisons", headers=headers, json={"requirement_id": requirement["id"]}
    ).json()["comparison"]
    agent_id = client.post("/agent/sessions", headers=headers).json()["agent_session_id"]

    response = client.post(
        f"/comparisons/{baseline['id']}/scenarios",
        headers=headers,
        json={
            "kind": "criteria",
            "agent_session_id": agent_id,
            "requirement": baseline["requirement"],
        },
    )

    assert response.status_code == 200
    assert response.json()["comparison"]["scenario_source_comparison_id"] == baseline["id"]
    assert calls["owner_id"] == session["session_id"]
    assert calls["agent_session_id"] == agent_id
    assert calls["source_id"] == baseline["id"]
    assert calls["requirement_id"] != baseline["requirement"]["id"]
    unchanged = client.get(f"/comparisons/{baseline['id']}", headers=headers).json()["comparison"]
    assert unchanged["id"] == baseline["id"]
    assert unchanged["requirement"] == baseline["requirement"]


def test_free_text_is_not_interpreted_without_explicit_fields(tmp_path):
    client = _client(tmp_path)
    response = client.post("/requirements", json={"text": "Phú Quốc 4 ngày"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "REQUIREMENT_INVALID"

    req = client.post("/requirements", json={"form": {"destinations": ["Phú Quốc"]}}).json()["requirement"]
    comp = client.post("/comparisons", json={"requirement_id": req["id"]}).json()["comparison"]
    assert comp["candidates_considered"] == 3
    assert {c["tour_id"] for c in comp["ranked"]} == {"vtr-phuquoc-4n"}


def test_unknown_requirement_id_is_404(tmp_path):
    response = _client(tmp_path).post("/comparisons", json={"requirement_id": "req_nope"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_guest_session_scopes_requirements_and_history(tmp_path):
    client = _client(tmp_path)
    guest_a = client.post("/sessions")
    guest_b = client.post("/sessions")
    assert guest_a.status_code == guest_b.status_code == 201
    token_a = guest_a.json()["token"]
    token_b = guest_b.json()["token"]

    created = client.post(
        "/requirements",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"form": {"destinations": ["Đà Lạt"]}},
    )
    assert created.status_code == 200
    requirement_id = created.json()["requirement"]["id"]

    own = client.get(
        f"/requirements/{requirement_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    foreign = client.get(
        f"/requirements/{requirement_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert own.status_code == 200
    assert foreign.status_code == 404

    own_history = client.get("/history", headers={"Authorization": f"Bearer {token_a}"})
    foreign_history = client.get("/history", headers={"Authorization": f"Bearer {token_b}"})
    assert own_history.status_code == 200
    assert [item["id"] for item in own_history.json()["items"]] == [requirement_id]
    assert foreign_history.json()["items"] == []


def test_history_requires_valid_guest_session_and_catalog_is_read_only(tmp_path):
    client = _client(tmp_path)
    assert client.get("/history").status_code == 401
    assert client.get("/history", headers={"Authorization": "Bearer invalid"}).status_code == 401

    catalog = client.get("/catalog")
    assert catalog.status_code == 200
    assert catalog.json()["destinations"]


def _cors_client(tmp_path):
    from unittest.mock import patch

    from backend.settings import Settings

    settings = Settings.load(
        database_url=f"sqlite:///{tmp_path / 'cors.db'}",
        cors_origins=["https://app.example.test"],
        cors_origin_regex=r"https://[a-z0-9-]+\.vercel\.app",
    )
    with patch("backend.api.for_settings", return_value=StaticCatalog()):
        return TestClient(create_app(settings))


def test_cors_allows_configured_origin_and_vercel_previews(tmp_path):
    client = _cors_client(tmp_path)
    preflight = client.options(
        "/requirements",
        headers={
            "Origin": "https://app.example.test",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "https://app.example.test"

    preview = client.get("/health", headers={"Origin": "https://preview-42.vercel.app"})
    assert preview.headers["access-control-allow-origin"] == "https://preview-42.vercel.app"


def test_cors_rejects_unknown_origin(tmp_path):
    client = _cors_client(tmp_path)
    response = client.get("/health", headers={"Origin": "https://evil.example.test"})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_history_cursor_and_detail_are_owner_scoped(tmp_path):
    client = _client(tmp_path)
    session = client.post("/sessions").json()
    headers = {"Authorization": f"Bearer {session['token']}"}
    requirement_ids = []
    for destination in ("Đà Lạt", "Phú Quốc"):
        response = client.post(
            "/requirements", headers=headers, json={"form": {"destinations": [destination]}}
        )
        requirement_ids.append(response.json()["requirement"]["id"])

    first = client.get("/history?limit=1", headers=headers)
    assert first.status_code == 200
    assert len(first.json()["items"]) == 1
    assert first.json()["next_cursor"]
    second = client.get("/history?limit=1&cursor=" + first.json()["next_cursor"], headers=headers)
    assert second.status_code == 200
    assert second.json()["next_cursor"] is None
    assert first.json()["items"][0]["id"] != second.json()["items"][0]["id"]

    item_id = first.json()["items"][0]["id"]
    detail = client.get(f"/history/{item_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["resource"]["id"] == item_id

    other = client.post("/sessions").json()
    forbidden = client.get(f"/history/{item_id}", headers={"Authorization": f"Bearer {other['token']}"})
    assert forbidden.status_code == 404

    invalid = client.get("/history?cursor=not-a-cursor", headers=headers)
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "CURSOR_INVALID"


def test_error_messages_are_ascii_english(tmp_path):
    """Error envelopes stay ASCII so no mojibake can ship; codes stay stable."""
    client = _client(tmp_path)
    session = client.post("/sessions").json()
    headers = {"Authorization": f"Bearer {session['token']}"}
    bodies = [
        client.get("/history").json(),
        client.get("/history", headers={"Authorization": "Bearer invalid"}).json(),
        client.get("/history?cursor=not-a-cursor", headers=headers).json(),
        client.post("/comparisons", json={"requirement_id": "req_nope"}).json(),
    ]
    assert bodies
    for body in bodies:
        message = body["error"]["message"]
        assert message and message.isascii(), message


def test_agent_session_is_owner_scoped_and_uses_request_response(tmp_path, monkeypatch):
    monkeypatch.setattr(OpenCodeRunner, "_executable", lambda _self: "opencode")

    async def fake_events(_self, message, session_id):
        assert message == "Tôi muốn đi Phú Quốc"
        assert session_id is None
        yield {
            "type": "text",
            "part": {
                "text": "Để tôi kiểm tra.",
                "metadata": {"openai": {"phase": "commentary"}},
            },
        }
        yield {
            "type": "text",
            "sessionID": "ses_abcdefgh12345678",
            "part": {"text": "Bạn muốn đi vào tháng nào?"},
        }

    monkeypatch.setattr(OpenCodeRunner, "events", fake_events)
    client = _client(tmp_path, opencode_server_url="http://127.0.0.1:4098")
    owner = client.post("/sessions").json()
    other = client.post("/sessions").json()
    own_headers = {"Authorization": f"Bearer {owner['token']}"}
    other_headers = {"Authorization": f"Bearer {other['token']}"}

    assert client.post("/agent/sessions").status_code == 401
    created = client.post("/agent/sessions", headers=own_headers)
    assert created.status_code == 201
    agent_id = created.json()["agent_session_id"]
    response = client.post(
        f"/agent/sessions/{agent_id}/messages",
        headers=own_headers,
        json={"message": "Tôi muốn đi Phú Quốc"},
    )
    assert response.status_code == 200
    assert response.json()["assistant_text"] == "Bạn muốn đi vào tháng nào?"
    assert client.post(
        f"/agent/sessions/{agent_id}/messages", headers=other_headers,
        json={"message": "Xin chào"},
    ).status_code == 404
    assert client.get("/history", headers=own_headers).json()["items"] == []


def test_agent_decision_endpoint_rejects_unbalanced_soft_weights(tmp_path, monkeypatch):
    monkeypatch.setattr(OpenCodeRunner, "_executable", lambda _self: "opencode")
    client = _client(tmp_path, opencode_server_url="http://127.0.0.1:4098")
    guest = client.post("/sessions").json()
    headers = {"Authorization": f"Bearer {guest['token']}"}
    agent_id = client.post("/agent/sessions", headers=headers).json()["agent_session_id"]
    requirement = {
        "id": "req_reviewed",
        "raw_text": "Thích thiên nhiên và biển",
        "travelers": 1,
        "conditions": [
            {"id": "s1", "field": "preference", "operator": "contains", "value": "thiên nhiên",
             "strength": "soft", "quote": "thiên nhiên", "weight_percent": 60},
            {"id": "s2", "field": "preference", "operator": "contains", "value": "biển",
             "strength": "soft", "quote": "biển", "weight_percent": 30},
        ],
    }

    response = client.post(
        f"/agent/sessions/{agent_id}/decisions",
        headers=headers,
        json={"requirement": requirement},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "REQUIREMENT_INVALID"


def test_agent_sse_includes_safe_tool_activity_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(OpenCodeRunner, "_executable", lambda _self: "opencode")

    async def fake_events(_self, _message, _session_id):
        part = {
            "tool": "tour-catalog_query_tours",
            "callID": "call-1",
            "state": {
                "status": "running",
                "input": {"conditions": [{"field": "destination", "value": "Đà Lạt"}]},
            },
        }
        yield {"type": "tool_use", "part": part}
        yield {"type": "text", "part": {"text": "Đã đối chiếu."}}

    monkeypatch.setattr(OpenCodeRunner, "events", fake_events)
    client = _client(tmp_path, opencode_server_url="http://127.0.0.1:4098")
    guest = client.post("/sessions").json()
    headers = {"Authorization": f"Bearer {guest['token']}"}
    agent_id = client.post("/agent/sessions", headers=headers).json()["agent_session_id"]

    response = client.post(
        f"/agent/sessions/{agent_id}/messages",
        headers={**headers, "Accept": "text/event-stream"},
        json={"message": "Tìm tour Đà Lạt"},
    )

    assert response.status_code == 200
    assert 'event: tool\ndata: {"id":"call-1","name":"query_tours","message":"Đối chiếu tour theo: điểm đến Đà Lạt","status":"running"}' in response.text


def test_agent_surfaces_model_access_errors_instead_of_empty_success(tmp_path, monkeypatch):
    monkeypatch.setattr(OpenCodeRunner, "_executable", lambda _self: "opencode")

    async def fake_events(_self, _message, _session_id):
        yield {
            "type": "error",
            "error": {
                "name": "APIError",
                "data": {"statusCode": 403, "message": "provider denied the free-tier model"},
            },
        }

    monkeypatch.setattr(OpenCodeRunner, "events", fake_events)
    client = _client(tmp_path, opencode_server_url="http://127.0.0.1:4098")
    owner = client.post("/sessions").json()
    headers = {"Authorization": f"Bearer {owner['token']}"}
    agent_id = client.post("/agent/sessions", headers=headers).json()["agent_session_id"]
    response = client.post(
        f"/agent/sessions/{agent_id}/messages",
        headers=headers,
        json={"message": "chào"},
    )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "OPENCODE_MODEL_ACCESS_DENIED"


def test_agent_rejects_empty_opencode_response(tmp_path, monkeypatch):
    monkeypatch.setattr(OpenCodeRunner, "_executable", lambda _self: "opencode")

    async def fake_events(_self, _message, _session_id):
        if False:
            yield {}

    monkeypatch.setattr(OpenCodeRunner, "events", fake_events)
    client = _client(tmp_path, opencode_server_url="http://127.0.0.1:4098")
    owner = client.post("/sessions").json()
    headers = {"Authorization": f"Bearer {owner['token']}"}
    agent_id = client.post("/agent/sessions", headers=headers).json()["agent_session_id"]
    response = client.post(
        f"/agent/sessions/{agent_id}/messages",
        headers=headers,
        json={"message": "chào"},
    )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "OPENCODE_RESPONSE_EMPTY"
