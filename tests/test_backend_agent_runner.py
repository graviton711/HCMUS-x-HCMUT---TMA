"""OpenCode subprocess lifetime: no total deadline, cleanup on cancellation."""

import asyncio
import json
import logging

import pytest

from backend.agent.runner import OpenCodeRunner
from backend.errors import AppError


class _Stdout:
    def __init__(self, lines=(), started=None):
        self.lines = iter(lines)
        self.started = started

    async def readline(self):
        if self.started is not None:
            self.started.set()
            await asyncio.Future()
        await asyncio.sleep(0)
        return next(self.lines, b"")


class _Stderr:
    def __init__(self, data=b""):
        self.data = data

    async def read(self, _size):
        data, self.data = self.data, b""
        await asyncio.sleep(0)
        return data


class _Process:
    def __init__(self, stdout, *, exit_code=0, stderr=None):
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.returncode = None
        self.killed = False

    def kill(self):
        self.killed = True
        self.returncode = -9

    async def wait(self):
        if self.returncode is None:
            self.returncode = self.exit_code
        return self.returncode


def _runner(settings):
    configured = settings.model_copy(update={
        "opencode_server_url": "http://127.0.0.1:4098",
        "opencode_model": "provider/test-model",
    })
    return OpenCodeRunner(configured)


def test_agent_runner_completes_without_a_total_timeout(settings, monkeypatch):
    line = json.dumps({"type": "text", "part": {"text": "done"}}).encode() + b"\n"
    process = _Process(_Stdout([line]))
    monkeypatch.setattr(OpenCodeRunner, "_executable", lambda _self: "opencode")

    async def spawn(*_args, **_kwargs):
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(
        asyncio,
        "timeout",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("agent timeout used")),
        raising=False,
    )

    async def collect():
        return [event async for event in _runner(settings).events("hello", None)]

    events = asyncio.run(collect())
    assert events == [{"type": "text", "part": {"text": "done"}}]
    assert process.returncode == 0
    assert not process.killed


def test_agent_runner_kills_process_when_client_cancels(settings, monkeypatch):
    async def exercise():
        started = asyncio.Event()
        process = _Process(_Stdout(started=started))
        monkeypatch.setattr(OpenCodeRunner, "_executable", lambda _self: "opencode")

        async def spawn(*_args, **_kwargs):
            return process

        monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
        task = asyncio.create_task(_runner(settings).events("hello", None).__anext__())
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert process.killed
        assert process.returncode == -9

    asyncio.run(exercise())


def test_agent_runner_logs_safe_stderr_and_exit_code(settings, monkeypatch, caplog):
    configured = settings.model_copy(update={
        "opencode_server_url": "http://127.0.0.1:4098",
        "opencode_server_password": "server-password-secret",
        "opencode_model": "provider/test-model",
    })
    process = _Process(
        _Stdout(),
        exit_code=17,
        stderr=_Stderr(
            b"API_KEY=provider-secret Authorization: Bearer bearer-secret "
            b"nvapi-abcdefghijklmnop server-password-secret user wrote this private sentence"
        ),
    )
    monkeypatch.setattr(OpenCodeRunner, "_executable", lambda _self: "opencode")

    async def spawn(*_args, **_kwargs):
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    caplog.set_level(logging.INFO, logger="mlai.backend.agent.runner")

    async def collect():
        return [
            event
            async for event in OpenCodeRunner(configured).events(
                "user wrote this private sentence", None
            )
        ]

    with pytest.raises(AppError) as error:
        asyncio.run(collect())

    assert error.value.code == "OPENCODE_RUN_FAILED"
    assert "opencode_run_started" in caplog.text
    assert "opencode_run_failed code=OPENCODE_RUN_FAILED exit_code=17" in caplog.text
    assert "API_KEY=[REDACTED]" in caplog.text
    assert "[REDACTED_INPUT]" in caplog.text
    assert "provider-secret" not in caplog.text
    assert "bearer-secret" not in caplog.text
    assert "nvapi-abcdefghijklmnop" not in caplog.text
    assert "server-password-secret" not in caplog.text
    assert "user wrote this private sentence" not in caplog.text
