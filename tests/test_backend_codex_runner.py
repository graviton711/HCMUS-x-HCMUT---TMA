"""Codex JSONL adaptation, tool isolation and cancellation behavior."""

import asyncio
import json
import sys

import pytest

from backend.agent.codex_runner import normalize_codex_event
from backend.codex_gateway import CodexGatewayState, TurnRequest, _classify_error


def test_normalizes_thread_mcp_assistant_and_usage_events():
    assert normalize_codex_event({"type": "thread.started", "thread_id": "01900123-abcd-4567"}) == [
        {"type": "session", "sessionID": "01900123-abcd-4567"}
    ]
    started = normalize_codex_event({
        "type": "item.started",
        "item": {
            "id": "call-1",
            "type": "mcp_tool_call",
            "server": "tour-catalog",
            "tool": "catalog_facets",
            "arguments": "{}",
            "status": "in_progress",
        },
    })
    assert started[0]["part"]["tool"] == "tour-catalog.catalog_facets"
    assert started[0]["part"]["state"]["status"] == "running"
    assert started[0]["part"]["state"]["input"] == {}

    completed = normalize_codex_event({
        "type": "item.completed",
        "item": {
            "id": "call-1",
            "type": "mcp_tool_call",
            "server": "tour-catalog",
            "tool": "catalog_facets",
            "arguments": {"include": ["destinations"]},
            "result": [{"type": "text", "text": "{\"destinations\": []}"}],
            "status": "completed",
        },
    })
    assert completed[0]["part"]["state"]["status"] == "completed"
    assert completed[0]["part"]["state"]["output"][0]["text"] == '{"destinations": []}'

    message = normalize_codex_event({
        "type": "item.completed",
        "turn_id": "turn-1",
        "item": {"id": "message-1", "type": "agent_message", "text": "Mình đã kiểm tra."},
    })
    assert message[0]["part"]["text"] == "Mình đã kiểm tra."
    assert message[0]["part"]["messageID"] == "turn-1"
    assert normalize_codex_event({"type": "turn.completed", "usage": {"input_tokens": 12}}) == [
        {"type": "usage", "usage": {"input_tokens": 12}}
    ]


@pytest.mark.parametrize(
    ("event", "expected"),
    [
        ({"type": "turn.failed", "error": {"http_status": 401}}, "CODEX_AUTH_REQUIRED"),
        ({"type": "turn.failed", "error": {"http_status": 429}}, "CODEX_RATE_LIMIT"),
        ({"type": "turn.failed", "error": {"message": "Thread not found"}}, "CODEX_THREAD_EXPIRED"),
        ({"type": "turn.failed", "error": {"http_status": 502}}, "CODEX_RUN_FAILED"),
    ],
)
def test_normalizes_auth_rate_limit_and_provider_errors(event, expected):
    normalized = normalize_codex_event(event)
    assert normalized[0]["type"] == "error"
    assert normalized[0]["error"]["code"] == expected


def test_ignores_non_result_jsonl_and_classifies_safe_gateway_errors():
    assert normalize_codex_event({"type": "turn.started"}) == []
    assert normalize_codex_event({"type": "item.completed", "item": {"type": "reasoning"}}) == []
    assert _classify_error("HTTP 429 rate limit") == "CODEX_RATE_LIMIT"
    assert _classify_error("please login") == "CODEX_AUTH_REQUIRED"
    assert _classify_error("thread not found") == "CODEX_THREAD_EXPIRED"
    assert _classify_error("provider crashed") == "CODEX_RUN_FAILED"


def test_command_uses_only_project_mcp_and_read_only_chatgpt_configuration(settings, tmp_path):
    configured = settings.model_copy(update={"codex_server_url": "http://127.0.0.1:4099"})
    state = CodexGatewayState(configured)
    state.command = ["codex"]
    state.workspace = tmp_path

    command = state.command_for_turn("01900123-abcd-4567-8901-234567890123")
    joined = " ".join(command)
    assert command[:4] == ["codex", "exec", "resume", "01900123-abcd-4567-8901-234567890123"]
    assert "--cd" not in command
    assert "--model gpt-6-luna" in joined
    assert "model_reasoning_effort=\"medium\"" in joined
    assert 'sandbox_mode="read-only"' in joined
    assert "--disable shell_tool" in joined
    assert "--disable multi_agent" in joined
    assert "mcp_servers.tour-catalog" in joined
    assert 'mcp_servers."tour-catalog"' not in joined
    assert "enabled_tools" in joined
    assert 'default_tools_approval_mode="approve"' in joined
    assert "--ignore-user-config" in joined
    overrides = [command[index + 1] for index, value in enumerate(command[:-1]) if value == "--config"]
    config_values = {item.split("=", 1)[0]: item.split("=", 1)[1] for item in overrides}
    assert json.loads(config_values["mcp_servers.tour-catalog.command"]) == sys.executable
    assert json.loads(config_values["mcp_servers.tour-catalog.args"]) == [
        "-m", "backend.agent.mcp_server"
    ]
    assert "uv" not in config_values["mcp_servers.tour-catalog.command"]
    assert json.loads(config_values["mcp_servers.tour-catalog.default_tools_approval_mode"]) == "approve"
    assert "@openai/codex" not in joined

    new_thread_command = state.command_for_turn(None)
    assert new_thread_command[:2] == ["codex", "exec"]
    assert "resume" not in new_thread_command
    assert "--cd" not in new_thread_command


class _FakeInput:
    def write(self, _value):
        pass

    async def drain(self):
        pass

    def close(self):
        pass


class _FakeOutput:
    def __init__(self, started, killed):
        self.started = started
        self.killed = killed

    async def readline(self):
        await self.killed.wait()
        return b""

    async def read(self, _size):
        await self.killed.wait()
        return b""


class _FakeProcess:
    def __init__(self, started):
        self.started = started
        self.killed = asyncio.Event()
        self.stdin = _FakeInput()
        self.stdout = _FakeOutput(started, self.killed)
        self.stderr = _FakeOutput(started, self.killed)
        self.returncode = None

    def kill(self):
        self.killed.set()
        self.returncode = -9

    async def wait(self):
        self.killed.set()
        return self.returncode


def test_cancelling_gateway_turn_kills_codex_process(settings, tmp_path, monkeypatch):
    state = CodexGatewayState(settings)
    state.command = ["codex"]
    state.workspace = tmp_path
    state.authenticated = True
    started = asyncio.Event()
    process = _FakeProcess(started)

    async def fake_start(*_args, **_kwargs):
        started.set()
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_start)

    async def consume():
        return [chunk async for chunk in state.stream_turn(TurnRequest(message="chào"))]

    async def run():
        task = asyncio.create_task(consume())
        await started.wait()
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())
    assert process.returncode == -9
