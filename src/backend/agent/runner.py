"""Async adapter for `opencode run --server <URL> --format json`."""

from __future__ import annotations

import asyncio
import json
import os
import re
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from backend.errors import AppError
from backend.opencode_binary import resolve_opencode_binary
from backend.settings import Settings
from shared import get_logger

_log = get_logger("backend.agent.runner")
_STDERR_TAIL_BYTES = 32 * 1024
_STDERR_LOG_CHARS = 2_000
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_BEARER_TOKEN = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_PROVIDER_TOKEN = re.compile(r"\b(?:sk-[A-Za-z0-9_-]{12,}|nvapi-[A-Za-z0-9_-]{12,})\b")
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b([\w.-]*(?:password|token|api[_-]?key|secret|authorization)[\w.-]*\s*[:=]\s*)"
    r"(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)"
)
_URL_CREDENTIALS = re.compile(r"(?i)(https?://)[^/\s:@]+:[^@\s/]+@")


def raise_for_error_event(event: dict[str, Any]) -> None:
    if event.get("type") != "error":
        return
    error = event.get("error")
    error = error if isinstance(error, dict) else {}
    data = error.get("data")
    data = data if isinstance(data, dict) else {}
    status = data.get("statusCode")
    if status in (401, 403):
        raise AppError(
            "OPENCODE_MODEL_ACCESS_DENIED",
            "OpenCode rejected access to the configured model for this CLI run.",
            502,
        )
    raise AppError(
        "OPENCODE_RUN_FAILED",
        "OpenCode returned an error before completing this turn.",
        502,
        retryable=True,
    )


class _TailBuffer:
    """Keep only the final bounded number of subprocess stderr bytes."""

    def __init__(self, max_bytes: int = _STDERR_TAIL_BYTES):
        self.max_bytes = max_bytes
        self.data = bytearray()

    def append(self, chunk: bytes) -> None:
        self.data.extend(chunk)
        if len(self.data) > self.max_bytes:
            del self.data[: len(self.data) - self.max_bytes]


async def _collect_stderr(stream: asyncio.StreamReader, tail: _TailBuffer) -> None:
    while chunk := await stream.read(4096):
        tail.append(chunk)


def _safe_stderr_tail(raw: bytes, *, password: str, message: str) -> str:
    text = raw.decode("utf-8", errors="replace")
    text = _ANSI_ESCAPE.sub("", text)
    text = _BEARER_TOKEN.sub("Bearer [REDACTED]", text)
    text = _PROVIDER_TOKEN.sub("[REDACTED]", text)
    text = _URL_CREDENTIALS.sub(r"\1[REDACTED]@", text)
    text = _SECRET_ASSIGNMENT.sub(r"\1[REDACTED]", text)
    if password:
        text = text.replace(password, "[REDACTED]")
    normalized_message = " ".join(message.split())
    if normalized_message:
        text = text.replace(normalized_message, "[REDACTED_INPUT]")
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[-_STDERR_LOG_CHARS:]


async def _stop_process(proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is None:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        await proc.wait()


class OpenCodeRunner:
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def configured(self) -> bool:
        return bool(self.settings.opencode_server_url.strip())

    def _executable(self) -> str:
        binary = self.settings.opencode_binary.strip() or "opencode"
        try:
            return resolve_opencode_binary(binary)
        except FileNotFoundError as exc:
            raise AppError("OPENCODE_UNAVAILABLE", "OpenCode CLI is not installed.", 503) from exc

    async def events(self, message: str, session_id: str | None) -> AsyncIterator[dict[str, Any]]:
        if not self.configured:
            raise AppError("AGENT_DISABLED", "OpenCode agent is not configured.", 503)
        project_root = Path(__file__).resolve().parents[3]
        configured_dir = self.settings.opencode_project_dir.strip()
        working_dir = Path(configured_dir) if configured_dir else project_root
        if not working_dir.is_absolute():
            working_dir = project_root / working_dir
        working_dir = working_dir.resolve()
        if not working_dir.is_dir():
            raise AppError(
                "OPENCODE_PROJECT_DIR_INVALID",
                "Configured OpenCode project directory is unavailable.",
                503,
            )
        model = self.settings.opencode.model
        args = [
            self._executable(),
            "run",
            "--server",
            self.settings.opencode_server_url.rstrip("/"),
            "--agent",
            self.settings.opencode_agent,
            "--model",
            model,
            "--format",
            "json",
        ]
        if session_id:
            args.extend(["--session", session_id])
        args.append(message)

        process_env = os.environ.copy()
        if self.settings.opencode_server_password:
            process_env["OPENCODE_SERVER_PASSWORD"] = self.settings.opencode_server_password
            # Current OpenCode CLI authenticates with OPENCODE_PASSWORD.
            process_env["OPENCODE_PASSWORD"] = self.settings.opencode_server_password

        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                cwd=working_dir,
                env=process_env,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=2 * 1024 * 1024,
            )
        except OSError as exc:
            raise AppError("OPENCODE_UNAVAILABLE", "Could not start OpenCode CLI.", 503) from exc

        assert proc.stdout is not None
        stderr_tail = _TailBuffer()
        proc_stderr = getattr(proc, "stderr", None)
        stderr_task = (
            asyncio.create_task(_collect_stderr(proc_stderr, stderr_tail)) if proc_stderr is not None else None
        )
        _log.info(
            "opencode_run_started agent=%s model=%s resumed=%s",
            self.settings.opencode_agent,
            model,
            bool(session_id),
        )
        try:
            while line := await proc.stdout.readline():
                try:
                    event = json.loads(line.decode("utf-8", errors="replace"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                if isinstance(event, dict):
                    raise_for_error_event(event)
                    yield event
            return_code = await proc.wait()
            if stderr_task is not None:
                await stderr_task
            _log.info("opencode_run_finished exit_code=%d", return_code)
            if return_code != 0:
                raise AppError(
                    "OPENCODE_RUN_FAILED", "OpenCode could not complete this turn.", 502, retryable=True
                )
        except AppError as error:
            await _stop_process(proc)
            if stderr_task is not None:
                await stderr_task
            safe_tail = _safe_stderr_tail(
                bytes(stderr_tail.data),
                password=self.settings.opencode_server_password,
                message=message,
            )
            _log.error(
                "opencode_run_failed code=%s exit_code=%s stderr_tail=%s",
                error.code,
                proc.returncode,
                safe_tail or "<empty>",
            )
            raise
        except asyncio.CancelledError:
            await _stop_process(proc)
            if stderr_task is not None:
                await stderr_task
            _log.warning("opencode_run_cancelled exit_code=%s", proc.returncode)
            raise
        finally:
            await _stop_process(proc)
            if stderr_task is not None and not stderr_task.done():
                await stderr_task
