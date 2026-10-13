"""OpenCode subprocess lifetime: no total deadline, cleanup on cancellation."""

import asyncio
import json

import pytest

from backend.agent.runner import OpenCodeRunner


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


class _Process:
    def __init__(self, stdout):
        self.stdout = stdout
        self.returncode = None
        self.killed = False

    def kill(self):
        self.killed = True
        self.returncode = -9

    async def wait(self):
        if self.returncode is None:
            self.returncode = 0
        return self.returncode


def _runner(settings):
    configured = settings.model_copy(update={"opencode_server_url": "http://127.0.0.1:4098"})
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
