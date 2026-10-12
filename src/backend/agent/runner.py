"""Async adapter for `opencode run --attach --format json`."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from backend.errors import AppError
from backend.settings import Settings
from shared import get_logger

log = get_logger("agent.opencode")


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


class OpenCodeRunner:
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def configured(self) -> bool:
        return bool(self.settings.opencode_server_url.strip())

    def _executable(self) -> str:
        binary = self.settings.opencode_binary.strip() or "opencode"
        resolved = shutil.which(binary) or (binary if Path(binary).is_file() else None)
        if resolved is None:
            raise AppError("OPENCODE_UNAVAILABLE", "OpenCode CLI is not installed.", 503)
        path = Path(resolved)
        if os.name == "nt" and path.suffix.lower() in {".cmd", ".bat"}:
            native = path.parent / "node_modules" / "opencode-ai" / "bin" / "opencode.exe"
            if native.is_file():
                return str(native)
        return str(path)

    async def events(self, message: str, session_id: str | None) -> AsyncIterator[dict[str, Any]]:
        if not self.configured:
            raise AppError("AGENT_DISABLED", "OpenCode agent is not configured.", 503)
        project_root = Path(__file__).resolve().parents[3]
        remote_dir = self.settings.opencode_project_dir.strip()
        args = [
            self._executable(),
            "run",
            "--attach",
            self.settings.opencode_server_url.rstrip("/"),
            "--dir",
            remote_dir or str(project_root),
            "--agent",
            self.settings.opencode_agent,
            "--format",
            "json",
        ]
        if self.settings.opencode_model.strip():
            args.extend(["--model", self.settings.opencode_model.strip()])
        if session_id:
            args.extend(["--session", session_id])
        args.append(message)

        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                cwd=project_root,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                limit=2 * 1024 * 1024,
            )
        except OSError as exc:
            raise AppError("OPENCODE_UNAVAILABLE", "Could not start OpenCode CLI.", 503) from exc

        assert proc.stdout is not None
        try:
            async with asyncio.timeout(self.settings.opencode_timeout_seconds):
                while line := await proc.stdout.readline():
                    try:
                        event = json.loads(line.decode("utf-8", errors="replace"))
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        continue
                    if isinstance(event, dict):
                        raise_for_error_event(event)
                        yield event
                return_code = await proc.wait()
            if return_code != 0:
                log.warning("OpenCode exited with code %s.", return_code)
                raise AppError("OPENCODE_RUN_FAILED", "OpenCode could not complete this turn.", 502,
                               retryable=True)
        except TimeoutError as exc:
            proc.kill()
            await proc.wait()
            raise AppError("OPENCODE_TIMEOUT", "OpenCode took too long to respond.", 504,
                           retryable=True) from exc
        finally:
            if proc.returncode is None:
                proc.kill()
                await proc.wait()
