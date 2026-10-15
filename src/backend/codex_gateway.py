"""HTTP gateway that runs the pinned Codex CLI and streams its JSONL events."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from backend.codex_binary import resolve_codex_command
from backend.settings import Settings

_log = logging.getLogger("mlai.backend.codex_gateway")
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PINNED_VERSION = "0.162.1"
_AUTH_REQUIRED = {
    "error": {
        "code": "CODEX_AUTH_REQUIRED",
        "message": "Codex gateway needs ChatGPT device-code login. Check the gateway log and retry.",
    }
}
_SAFE_ERRORS = {
    "CODEX_RATE_LIMIT": "Codex account usage is temporarily rate limited. Retry later.",
    "CODEX_AUTH_REQUIRED": _AUTH_REQUIRED["error"]["message"],
    "CODEX_THREAD_EXPIRED": "The saved Codex thread is unavailable. Retry to start a new conversation.",
    "CODEX_RUN_FAILED": "Codex could not complete this turn.",
}
_DEVICE_URL = re.compile(r"https://(?:auth\.openai\.com|chatgpt\.com)/[^\s<>\"']+", re.I)
_DEVICE_CODE = re.compile(
    r"(?i)(?:code|enter|one.time)[^A-Z0-9]{0,24}([A-Z0-9]{4,8}(?:-[A-Z0-9]{3,8})?)"
)
_RATE_LIMIT = re.compile(r"rate.?limit|too many requests|http.?429", re.I)
_AUTH_FAILURE = re.compile(
    r"unauthori[sz]ed|not logged in|(?:please\s+)?(?:log\s*in|login)(?:\s+required)?|http.?401|token expired",
    re.I,
)
_THREAD_EXPIRED = re.compile(
    r"(?:thread|session|conversation).{0,50}(?:not found|expired|does not exist|unknown)|"
    r"(?:not found|expired|does not exist|unknown).{0,50}(?:thread|session|conversation)",
    re.I,
)


class TurnRequest(BaseModel):
    message: str = Field(min_length=1, max_length=16_000)
    thread_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{8,160}$")


def _safe_process_environment() -> dict[str, str]:
    environment = os.environ.copy()
    # This gateway is intentionally ChatGPT-plan-only. Do not let CLI environment
    # credentials silently switch the run to API billing.
    for name in ("OPENAI_API_KEY", "CODEX_API_KEY", "CODEX_ACCESS_TOKEN", "OPENAI_BASE_URL"):
        environment.pop(name, None)
    return environment


def _codex_instructions() -> str:
    prompt_path = _PROJECT_ROOT / "configs" / "prompts" / "backend-agent.yaml"
    payload = yaml.safe_load(prompt_path.read_text(encoding="utf-8"))
    instructions = payload.get("system") if isinstance(payload, dict) else None
    if not isinstance(instructions, str) or not instructions.strip():
        raise RuntimeError("Codex travel-agent instructions are missing.")
    return instructions.strip()


def _workspace() -> Path:
    home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    path = home / "tourlens-workspace"
    path.mkdir(parents=True, exist_ok=True)
    prompt = "# TourLens decision agent\n\n" + _codex_instructions() + "\n"
    instruction_file = path / "AGENTS.md"
    if not instruction_file.is_file() or instruction_file.read_text(encoding="utf-8") != prompt:
        instruction_file.write_text(prompt, encoding="utf-8")
    return path


def _toml_string(value: str) -> str:
    # JSON string literals are a compatible subset of TOML basic strings.
    return json.dumps(value, ensure_ascii=True)


def _toml_array(values: list[str]) -> str:
    return "[" + ", ".join(_toml_string(value) for value in values) + "]"


class CodexGatewayState:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.command: list[str] | None = None
        self.workspace: Path | None = None
        self.authenticated = False
        self.startup_error = ""
        self._login_task: asyncio.Task[None] | None = None
        self._login_process: asyncio.subprocess.Process | None = None
        self._login_lock = asyncio.Lock()

    async def initialize(self) -> None:
        try:
            self.command = resolve_codex_command(self.settings.codex_binary)
            self.workspace = _workspace()
            version = await self._capture(self.command + ["--version"])
            if _PINNED_VERSION not in version:
                raise RuntimeError(f"Codex CLI {_PINNED_VERSION} is required.")
            self.authenticated = await self._chatgpt_login_status()
            _log.info(
                "codex_gateway_ready version=%s chatgpt_authenticated=%s",
                _PINNED_VERSION,
                self.authenticated,
            )
            if not self.authenticated:
                self.start_device_login()
        except (OSError, RuntimeError, ValueError) as exc:
            self.startup_error = str(exc)
            _log.error("codex_gateway_unavailable reason=%s", self.startup_error)

    async def shutdown(self) -> None:
        if self._login_task is not None:
            self._login_task.cancel()
            try:
                await self._login_task
            except asyncio.CancelledError:
                pass
        if self._login_process is not None and self._login_process.returncode is None:
            self._login_process.kill()
            await self._login_process.wait()

    async def _capture(self, command: list[str]) -> str:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            stdin=asyncio.subprocess.DEVNULL,
            env=_safe_process_environment(),
        )
        output, _ = await process.communicate()
        if process.returncode != 0:
            return ""
        return output.decode("utf-8", errors="replace")

    async def _chatgpt_login_status(self) -> bool:
        assert self.command is not None
        output = await self._capture(self.command + ["login", "status"])
        # Reject API-key auth even if it is stored in the Codex profile.
        return "chatgpt" in output.casefold() and "api key" not in output.casefold()

    def start_device_login(self) -> None:
        if self._login_task is None or self._login_task.done():
            self._login_task = asyncio.create_task(self._device_login())

    async def _device_login(self) -> None:
        async with self._login_lock:
            if self.command is None:
                return
            if await self._chatgpt_login_status():
                self.authenticated = True
                return
            _log.warning("codex_device_login_started method=device_code")
            try:
                process = await asyncio.create_subprocess_exec(
                    *self.command,
                    "login",
                    "--device-auth",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                    stdin=asyncio.subprocess.DEVNULL,
                    env=_safe_process_environment(),
                )
            except OSError:
                _log.error("codex_device_login_failed reason=process_unavailable")
                return
            self._login_process = process
            assert process.stdout is not None
            while line := await process.stdout.readline():
                self._log_device_instruction(line.decode("utf-8", errors="replace"))
            return_code = await process.wait()
            self._login_process = None
            if return_code == 0 and await self._chatgpt_login_status():
                self.authenticated = True
                _log.info("codex_device_login_completed")
            else:
                _log.error("codex_device_login_failed exit_code=%s", return_code)

    @staticmethod
    def _log_device_instruction(line: str) -> None:
        url_match = _DEVICE_URL.search(line)
        code_match = _DEVICE_CODE.search(line)
        if not url_match and not code_match:
            return
        url = url_match.group(0).rstrip(".,)") if url_match else ""
        code = code_match.group(1) if code_match else ""
        _log.warning("codex_device_authorization url=%s code=%s", url or "<see-code>", code or "<see-url>")

    def command_for_turn(self, thread_id: str | None) -> list[str]:
        if self.command is None or self.workspace is None:
            raise RuntimeError(self.startup_error or "Codex gateway is not ready.")

        command = self.command + ["exec"]
        if thread_id:
            command += ["resume", thread_id]
        command += [
            "--json",
            "--model",
            self.settings.codex.model,
            "--config",
            f"model_reasoning_effort={_toml_string(self.settings.codex.reasoning_effort)}",
            "--config",
            'sandbox_mode="read-only"',
            "--config",
            'approval_policy="never"',
            "--disable",
            "shell_tool",
            "--disable",
            "multi_agent",
            "--ignore-user-config",
            "--skip-git-repo-check",
        ]
        # Both exec and exec resume run with cwd=self.workspace below. The pinned
        # CLI rejects --cd on the resume subcommand, so keep cwd in process options.
        # CLI `--config` overrides parse dotted paths directly; quote characters
        # here become part of the MCP server name, so keep this TOML bare key.
        mcp_prefix = "mcp_servers.tour-catalog"
        mcp_args = ["-m", "backend.agent.mcp_server"]
        config = [
            (f"{mcp_prefix}.command", _toml_string(sys.executable)),
            (f"{mcp_prefix}.args", _toml_array(mcp_args)),
            (f"{mcp_prefix}.cwd", _toml_string(str(_PROJECT_ROOT))),
            (f"{mcp_prefix}.env_vars", _toml_array([
                "SUPABASE_TOUR_DB_URL",
                "DATABASE_URL",
                "DATA_PROVIDER",
                "SUPABASE_SCAN_LIMIT",
            ])),
            (f"{mcp_prefix}.startup_timeout_sec", "60"),
            (f"{mcp_prefix}.tool_timeout_sec", "120"),
            (f"{mcp_prefix}.default_tools_approval_mode", '"approve"'),
            (f"{mcp_prefix}.enabled_tools", _toml_array([
                "ask_choice",
                "catalog_facets",
                "discover_destinations",
                "draft_requirement",
                "query_tours",
                "tour_detail",
                "score_soft",
                "clarify_date",
            ])),
            (f"{mcp_prefix}.enabled", "true"),
            (f"{mcp_prefix}.required", "true"),
        ]
        for key, value in config:
            command += ["--config", f"{key}={value}"]
        command.append("-")
        return command

    async def stream_turn(self, request: TurnRequest) -> AsyncIterator[bytes]:
        if self.startup_error:
            yield _json_line({"type": "error", "error": {
                "code": "CODEX_UNAVAILABLE", "message": "Codex CLI is unavailable or unsupported."
            }})
            return
        if not self.authenticated:
            self.start_device_login()
            yield _json_line(_AUTH_REQUIRED)
            return
        try:
            command = self.command_for_turn(request.thread_id)
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=self.workspace,
                env=_safe_process_environment(),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=2 * 1024 * 1024,
            )
        except (OSError, RuntimeError) as exc:
            _log.error("codex_turn_start_failed error_type=%s", type(exc).__name__)
            yield _json_line({"type": "error", "error": {
                "code": "CODEX_UNAVAILABLE", "message": "Codex CLI could not be started."
            }})
            return

        assert process.stdin is not None and process.stdout is not None
        process.stdin.write(request.message.encode("utf-8"))
        await process.stdin.drain()
        process.stdin.close()
        stderr_tail = bytearray()
        stderr_task = asyncio.create_task(_read_stderr(process.stderr, stderr_tail)) if process.stderr else None
        saw_error = False
        try:
            while line := await process.stdout.readline():
                try:
                    event = json.loads(line.decode("utf-8", errors="replace"))
                except json.JSONDecodeError:
                    continue
                if not isinstance(event, dict):
                    continue
                if event.get("type") in {"turn.failed", "error"}:
                    saw_error = True
                    event = _safe_codex_error(event)
                yield _json_line(event)
            exit_code = await process.wait()
            if stderr_task is not None:
                await stderr_task
            if exit_code != 0 and not saw_error:
                safe_tail = _safe_stderr(bytes(stderr_tail), request.message)
                _log.error("codex_turn_failed exit_code=%s stderr_tail=%s", exit_code, safe_tail or "<empty>")
                code = _classify_error(safe_tail)
                if code == "CODEX_AUTH_REQUIRED":
                    self.authenticated = False
                    self.start_device_login()
                yield _json_line({"type": "error", "error": {
                    "code": code, "message": _SAFE_ERRORS[code]
                }})
        except asyncio.CancelledError:
            if process.returncode is None:
                process.kill()
                await process.wait()
            if stderr_task is not None:
                await stderr_task
            _log.info("codex_turn_cancelled")
            raise
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
            if stderr_task is not None and not stderr_task.done():
                await stderr_task


async def _read_stderr(stream: asyncio.StreamReader, tail: bytearray) -> None:
    while chunk := await stream.read(4096):
        tail.extend(chunk)
        if len(tail) > 32 * 1024:
            del tail[: len(tail) - 32 * 1024]


def _safe_stderr(raw: bytes, message: str) -> str:
    from backend.agent.runner import _safe_stderr_tail

    return _safe_stderr_tail(raw, password="", message=message)


def _classify_error(value: Any) -> str:
    if isinstance(value, dict):
        status = value.get("http_status") or value.get("status") or value.get("status_code")
        if status == 429:
            return "CODEX_RATE_LIMIT"
        if status in (401, 403):
            return "CODEX_AUTH_REQUIRED"
        message = str(value.get("message", ""))
    else:
        message = str(value or "")
    if _RATE_LIMIT.search(message):
        return "CODEX_RATE_LIMIT"
    if _THREAD_EXPIRED.search(message):
        return "CODEX_THREAD_EXPIRED"
    if _AUTH_FAILURE.search(message):
        return "CODEX_AUTH_REQUIRED"
    return "CODEX_RUN_FAILED"


def _safe_codex_error(event: dict[str, Any]) -> dict[str, Any]:
    detail = event.get("error")
    code = _classify_error(detail)
    return {"type": "error", "error": {"code": code, "message": _SAFE_ERRORS[code]}}


def _json_line(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def create_app(settings: Settings | None = None, state: CodexGatewayState | None = None) -> FastAPI:
    gateway_state = state or CodexGatewayState(settings or Settings.load())

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        await gateway_state.initialize()
        try:
            yield
        finally:
            await gateway_state.shutdown()

    app = FastAPI(title="TourLens Codex gateway", lifespan=lifespan)
    app.state.gateway = gateway_state

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "codex_ready": not bool(gateway_state.startup_error),
            "chatgpt_authenticated": gateway_state.authenticated,
        }

    @app.post("/turns")
    async def turn(body: TurnRequest):
        if gateway_state.startup_error:
            return JSONResponse(
                status_code=503,
                content={"error": {"code": "CODEX_UNAVAILABLE", "message": "Codex CLI is unavailable or unsupported."}},
            )
        if not gateway_state.authenticated:
            gateway_state.start_device_login()
            return JSONResponse(status_code=503, content=_AUTH_REQUIRED)
        return StreamingResponse(
            gateway_state.stream_turn(body),
            media_type="application/x-ndjson",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app
