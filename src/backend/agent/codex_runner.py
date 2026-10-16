"""HTTP adapter for the Codex gateway's JSONL turn stream."""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from typing import Any

import httpx

from backend.errors import AppError
from backend.settings import Settings
from shared import get_logger

_log = get_logger("backend.agent.codex_runner")

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


def _mcp_input(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return decoded if isinstance(decoded, dict) else {}
    return {}


def _error_code(value: Any) -> str:
    if isinstance(value, dict):
        code = value.get("code")
        if isinstance(code, str) and code.startswith("CODEX_"):
            return code
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


def normalize_codex_event(event: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert Codex JSONL items to the provider-neutral service event shape."""
    kind = event.get("type")
    if kind == "thread.started":
        thread_id = event.get("thread_id") or event.get("threadId")
        return [{"type": "session", "sessionID": thread_id}] if isinstance(thread_id, str) else []

    if kind in {"item.started", "item.updated", "item.completed"}:
        item = event.get("item")
        if not isinstance(item, dict):
            return []
        item_type = item.get("type")
        item_id = item.get("id")
        turn_id = event.get("turn_id") or event.get("turnId") or "codex-turn"
        if item_type in {"agent_message", "assistant_message"}:
            text = item.get("text")
            if not isinstance(text, str):
                return []
            return [{"type": "text", "part": {
                "id": str(item_id or "assistant-message"),
                "messageID": str(turn_id),
                "text": text,
            }}]
        if item_type != "mcp_tool_call":
            if item_type == "error" and kind == "item.completed":
                return [{"type": "error", "error": {
                    "code": _error_code(item.get("error") or item.get("message")),
                    "message": "Codex could not complete this turn.",
                }}]
            if item_type not in {"reasoning", "token_count"} and kind == "item.completed":
                _log.debug(
                    "codex_non_catalog_tool_call name=%s status=%s",
                    item.get("tool") or item.get("name"),
                    item.get("status"),
                )
            return []

        server = item.get("server") or item.get("server_name") or "tour-catalog"
        tool = item.get("tool") or item.get("name")
        if not isinstance(tool, str) or not tool:
            return []
        status = str(item.get("status", ""))
        if kind == "item.completed" and not item.get("error") and status not in {"failed", "error"}:
            status = "completed"
        elif item.get("error") or status in {"failed", "error"}:
            status = "error"
        else:
            status = "running"
        result = item.get("result")
        if result is None:
            result = item.get("content")
        state = {
            "status": status,
            "input": _mcp_input(item.get("arguments") or item.get("input")),
        }
        if result is not None:
            state["output"] = result
        return [{"type": "tool", "part": {
            "id": str(item_id or ""),
            "tool": f"{server}.{tool}",
            "state": state,
        }}]

    if kind == "turn.completed":
        usage = event.get("usage")
        return [{"type": "usage", "usage": usage}] if isinstance(usage, dict) else []

    if kind in {"turn.failed", "error"}:
        detail = event.get("error") or event.get("message")
        code = _error_code(detail)
        safe_message = {
            "CODEX_AUTH_REQUIRED": "Codex ChatGPT login is required.",
            "CODEX_RATE_LIMIT": "Codex account usage is temporarily rate limited.",
            "CODEX_THREAD_EXPIRED": "The saved Codex thread is unavailable. Retry to start a new conversation.",
        }.get(code, "Codex could not complete this turn.")
        return [{"type": "error", "error": {"code": code, "message": safe_message}}]

    return []


class CodexRunner:
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def configured(self) -> bool:
        return bool(self.settings.codex_server_url.strip())

    async def events(self, message: str, thread_id: str | None) -> AsyncIterator[dict[str, Any]]:
        if not self.configured:
            raise AppError("AGENT_DISABLED", "Codex gateway is not configured.", 503)
        url = self.settings.codex_server_url.rstrip("/") + "/turns"
        payload = {"message": message, "thread_id": thread_id}
        timeout = httpx.Timeout(timeout=None, connect=10.0)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", url, json=payload) as response:
                    if response.is_error:
                        body = await response.aread()
                        yield _gateway_error(response.status_code, body)
                        return
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            raw_event = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if not isinstance(raw_event, dict):
                            continue
                        for event in normalize_codex_event(raw_event):
                            yield event
        except httpx.TimeoutException as exc:
            raise AppError(
                "CODEX_GATEWAY_TIMEOUT", "The Codex gateway did not respond in time.", 504, retryable=True
            ) from exc
        except httpx.HTTPError as exc:
            raise AppError(
                "CODEX_GATEWAY_UNAVAILABLE", "The Codex gateway is unavailable.", 503, retryable=True
            ) from exc


def _gateway_error(status_code: int, body: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(body.decode("utf-8", errors="replace"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        payload = {}
    error = payload.get("error") if isinstance(payload, dict) else None
    error = error if isinstance(error, dict) else {}
    code = error.get("code") if isinstance(error.get("code"), str) else "CODEX_GATEWAY_UNAVAILABLE"
    message = error.get("message") if isinstance(error.get("message"), str) else "Codex gateway request failed."
    return {"type": "error", "error": {
        "code": code,
        "message": message,
        "statusCode": status_code,
    }}
