"""Transport boundaries log safe metadata and suppress unexpected details."""

import logging

from fastapi.testclient import TestClient

from backend.agent.mcp_server import _guard_tool
from backend.agent.runner import OpenCodeRunner
from backend.api import create_app
from backend.data.catalog import FixtureCatalog
from backend.errors import AppError


def _client(tmp_path):
    from backend.settings import Settings

    settings = Settings.load(
        database_url=f"sqlite:///{tmp_path / 'errors.db'}",
        opencode_server_url="http://127.0.0.1:4098",
    )
    return TestClient(create_app(settings))


def _error_records(caplog):
    return [record for record in caplog.records if record.name == "mlai.backend.errors"]


def test_http_does_not_log_client_errors(tmp_path, caplog):
    caplog.set_level(logging.WARNING, logger="mlai.backend.errors")
    response = _client(tmp_path).post("/comparisons", json={})
    assert response.status_code == 422
    assert _error_records(caplog) == []


def test_http_logs_retryable_app_error_once_without_message(tmp_path, monkeypatch, caplog):
    def unavailable(_self):
        raise AppError("CATALOG_UNAVAILABLE", "secret connection detail", 502, retryable=True)

    monkeypatch.setattr(FixtureCatalog, "list_destinations", unavailable)
    caplog.set_level(logging.WARNING, logger="mlai.backend.errors")
    response = _client(tmp_path).get("/catalog")
    records = _error_records(caplog)
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "CATALOG_UNAVAILABLE"
    assert len(records) == 1
    assert "CATALOG_UNAVAILABLE" in records[0].getMessage()
    assert "secret connection detail" not in records[0].getMessage()


def test_http_normalizes_unexpected_exception_and_logs_safe_metadata(tmp_path, monkeypatch, caplog):
    def broken(_self):
        raise RuntimeError("secret token detail")

    monkeypatch.setattr(FixtureCatalog, "list_destinations", broken)
    caplog.set_level(logging.ERROR, logger="mlai.backend.errors")
    response = _client(tmp_path).get("/catalog")
    records = _error_records(caplog)
    assert response.status_code == 500
    assert response.json() == {"error": {"code": "INTERNAL_ERROR", "message": "An internal error occurred."}}
    assert len(records) == 1
    assert "RuntimeError" in records[0].getMessage()
    assert "secret token detail" not in records[0].getMessage()


def test_sse_normalizes_unexpected_agent_error_once(tmp_path, monkeypatch, caplog):
    async def broken_events(_self, _message, _session_id):
        raise RuntimeError("provider secret detail")
        yield {}

    monkeypatch.setattr(OpenCodeRunner, "_executable", lambda _self: "opencode")
    monkeypatch.setattr(OpenCodeRunner, "events", broken_events)
    caplog.set_level(logging.ERROR, logger="mlai.backend.errors")
    client = _client(tmp_path)
    guest = client.post("/sessions").json()
    headers = {"Authorization": f"Bearer {guest['token']}"}
    agent_id = client.post("/agent/sessions", headers=headers).json()["agent_session_id"]
    response = client.post(
        f"/agent/sessions/{agent_id}/messages",
        headers={**headers, "Accept": "text/event-stream"},
        json={"message": "Tìm tour"},
    )
    records = _error_records(caplog)
    assert response.status_code == 200
    assert (
        'event: error\ndata: {"code":"INTERNAL_ERROR","message":"An internal error occurred."}'
        in response.text
    )
    assert len(records) == 1
    assert "provider secret detail" not in records[0].getMessage()


def test_sse_logs_retryable_app_error_once(tmp_path, monkeypatch, caplog):
    async def failed_events(_self, _message, _session_id):
        raise AppError("OPENCODE_RUN_FAILED", "OpenCode failed safely.", 502, retryable=True)
        yield {}

    monkeypatch.setattr(OpenCodeRunner, "_executable", lambda _self: "opencode")
    monkeypatch.setattr(OpenCodeRunner, "events", failed_events)
    caplog.set_level(logging.WARNING, logger="mlai.backend.errors")
    client = _client(tmp_path)
    guest = client.post("/sessions").json()
    headers = {"Authorization": f"Bearer {guest['token']}"}
    agent_id = client.post("/agent/sessions", headers=headers).json()["agent_session_id"]
    response = client.post(
        f"/agent/sessions/{agent_id}/messages",
        headers={**headers, "Accept": "text/event-stream"},
        json={"message": "Tìm tour"},
    )
    records = _error_records(caplog)
    assert '"code":"OPENCODE_RUN_FAILED"' in response.text
    assert len(records) == 1
    assert "OPENCODE_RUN_FAILED" in records[0].getMessage()


def test_mcp_boundary_logs_retryable_error_and_returns_safe_payload(caplog):
    def broken():
        raise AppError("CATALOG_UNAVAILABLE", "secret database detail", 503, retryable=True)

    caplog.set_level(logging.WARNING, logger="mlai.backend.errors")
    result = _guard_tool("catalog_facets", broken)()
    records = _error_records(caplog)
    assert '"code":"CATALOG_UNAVAILABLE"' in result
    assert len(records) == 1
    assert "secret database detail" not in records[0].getMessage()


def test_mcp_boundary_suppresses_unexpected_exception_details(caplog):
    def broken():
        raise RuntimeError("secret provider detail")

    caplog.set_level(logging.ERROR, logger="mlai.backend.errors")
    result = _guard_tool("query_tours", broken)()
    records = _error_records(caplog)
    assert '"code":"INTERNAL_ERROR"' in result
    assert len(records) == 1
    assert "RuntimeError" in records[0].getMessage()
    assert "secret provider detail" not in records[0].getMessage()


def test_mcp_boundary_does_not_log_non_retryable_client_error(caplog):
    def invalid():
        raise AppError("REQUIREMENT_INVALID", "Invalid requirement.", 422)

    caplog.set_level(logging.WARNING, logger="mlai.backend.errors")
    result = _guard_tool("query_tours", invalid)()
    assert '"code":"REQUIREMENT_INVALID"' in result
    assert _error_records(caplog) == []
