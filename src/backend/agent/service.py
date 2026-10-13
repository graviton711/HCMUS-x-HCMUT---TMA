"""Owner-scoped OpenCode sessions and grounded request/response turns."""

from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator
from typing import Any

from backend.agent.results import json_candidates, limit_comparison
from backend.agent.runner import OpenCodeRunner, raise_for_error_event
from backend.data.sessions import BaseStore
from backend.errors import AppError
from backend.models import Comparison, Requirement
from backend.settings import Settings

_LOCAL_ID = re.compile(r"^agt_[A-Za-z0-9]{16,40}$")
_OPENCODE_ID = re.compile(r"^ses_[A-Za-z0-9_-]{8,120}$")


class AgentService:
    def __init__(self, settings: Settings, store: BaseStore):
        self.settings = settings
        self.store = store
        self.runner = OpenCodeRunner(settings)
        self._locks: dict[tuple[str, str], asyncio.Lock] = {}

    @property
    def available(self) -> bool:
        if not self.runner.configured:
            return False
        try:
            self.runner._executable()
        except AppError:
            return False
        return True

    def create_session(self, owner_id: str) -> dict[str, str]:
        if not self.available:
            raise AppError("AGENT_DISABLED", "OpenCode agent is not configured.", 503)
        return {"agent_session_id": self.store.create_agent_session(owner_id)}

    async def message(self, owner_id: str, local_id: str, message: str) -> dict[str, Any]:
        response: dict[str, Any] | None = None
        async for event in self.stream_message(owner_id, local_id, message):
            if event.get("type") == "result" and isinstance(event.get("response"), dict):
                response = event["response"]
        if response is None:
            raise AppError(
                "OPENCODE_RESPONSE_EMPTY",
                "OpenCode completed without returning a message or tool result.",
                502,
                retryable=True,
            )
        return response

    async def stream_message(
        self, owner_id: str, local_id: str, message: str
    ) -> AsyncIterator[dict[str, Any]]:
        if not _LOCAL_ID.fullmatch(local_id):
            raise AppError("AGENT_SESSION_INVALID", "Invalid agent session ID.", 400)
        if (
            not isinstance(message, str)
            or not message.strip()
            or len(message) > self.settings.agent_max_message_chars
        ):
            raise AppError("MESSAGE_INVALID", "Message is empty or too long.", 422)

        key = (owner_id, local_id)
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            async for event in self._message_events(owner_id, local_id, message.strip()):
                yield event

    async def _message_events(
        self, owner_id: str, local_id: str, message: str
    ) -> AsyncIterator[dict[str, Any]]:
        assistant_text: list[str] = []
        tool_calls: list[dict[str, str]] = []
        active_tool_ids: dict[str, str] = {}
        tool_messages: dict[str, str] = {}
        tool_sequence = 0
        choices: dict[str, Any] | None = None
        final_requirement: Requirement | None = None
        final_comparison: Comparison | None = None

        try:
            session_id = self.store.get_agent_session(local_id, owner_id)
            yield {"type": "progress", "status": "working"}
            async for event in self.runner.events(message, session_id):
                raise_for_error_event(event)
                properties = event.get("properties")
                properties = properties if isinstance(properties, dict) else {}
                observed_id = event.get("sessionID") or properties.get("sessionID")
                if isinstance(observed_id, str) and _OPENCODE_ID.fullmatch(observed_id):
                    if session_id is None:
                        self.store.save_agent_session(local_id, owner_id, observed_id)
                        session_id = observed_id

                part = event.get("part") or properties.get("part")
                if not isinstance(part, dict):
                    continue
                kind = event.get("type")
                if kind == "text" and isinstance(part.get("text"), str):
                    metadata = part.get("metadata")
                    metadata = metadata if isinstance(metadata, dict) else {}
                    provider_metadata = metadata.get("openai")
                    provider_metadata = provider_metadata if isinstance(provider_metadata, dict) else {}
                    if provider_metadata.get("phase") == "commentary":
                        continue
                    assistant_text.append(part["text"])
                    continue

                tool = part.get("tool") or part.get("name")
                if not isinstance(tool, str):
                    continue
                tool_name = _tool_name(tool)
                state = part.get("state")
                state = state if isinstance(state, dict) else {}
                status = str(state.get("status", "running"))
                tool_calls.append({"name": tool_name, "status": status})
                call_id = part.get("callID") or part.get("call_id") or part.get("id")
                if not isinstance(call_id, str) or not call_id:
                    terminal = status in {"completed", "success", "error", "failed"}
                    call_id = active_tool_ids.get(tool_name, "")
                    if not call_id:
                        tool_sequence += 1
                        call_id = f"tool-{tool_sequence}"
                    if not terminal:
                        active_tool_ids[tool_name] = call_id
                tool_input = state.get("input")
                if not isinstance(tool_input, dict):
                    tool_input = part.get("input") or part.get("arguments")
                if not isinstance(tool_input, dict):
                    tool_input = {}
                message_summary = _tool_progress_message(tool_name, tool_input)
                if message_summary:
                    tool_messages[call_id] = message_summary
                yield {
                    "type": "tool",
                    "id": call_id,
                    "name": tool_name,
                    "message": tool_messages.get(call_id, ""),
                    "status": (
                        "completed" if status in {"completed", "success"} else
                        "error" if status in {"error", "failed"} else "running"
                    ),
                }
                if status in {"completed", "success", "error", "failed"}:
                    active_tool_ids.pop(tool_name, None)
                    tool_messages.pop(call_id, None)
                if status not in {"completed", "success"}:
                    continue
                output = state.get("output", part.get("output"))
                for payload in json_candidates(output):
                    if tool_name == "ask_choice" and _valid_choice(payload):
                        choices = {
                            "question": payload["question"],
                            "options": payload["options"],
                            "allow_custom": bool(payload.get("allow_custom", True)),
                        }
                    result = _comparison_result(payload)
                    if result is None:
                        continue
                    requirement, comparison = result
                    final_requirement = requirement
                    final_comparison = comparison
        except AppError:
            raise

        response: dict[str, Any] = {
            "assistant_text": "".join(assistant_text).strip(),
            "tool_calls": _deduplicate_calls(tool_calls),
        }
        if choices is not None:
            response["choices"] = choices
        if final_requirement is not None:
            self.store.save_requirement(final_requirement, owner_id)
            response["requirement"] = final_requirement.model_dump(mode="json")
        if final_comparison is not None:
            if final_requirement is None:
                final_requirement = final_comparison.requirement
                self.store.save_requirement(final_requirement, owner_id)
                response["requirement"] = final_requirement.model_dump(mode="json")
            final_comparison = limit_comparison(final_comparison)
            self.store.save_comparison(final_comparison, owner_id)
            response["comparison"] = final_comparison.model_dump(mode="json")
        if not any((response["assistant_text"], response["tool_calls"], choices, final_requirement,
                    final_comparison)):
            raise AppError(
                "OPENCODE_RESPONSE_EMPTY",
                "OpenCode completed without returning a message or tool result.",
                502,
                retryable=True,
            )
        if not response["assistant_text"] and choices is None and final_comparison is None:
            # Tools ran (possibly with errors) but produced nothing user-facing.
            # Never hand the UI an empty turn; the user can simply retry.
            response["assistant_text"] = (
                "Tôi chưa lấy được kết quả vừa rồi. Bạn thử gửi lại nhé."
            )
        yield {"type": "result", "response": response}


def _tool_name(value: str) -> str:
    if value.startswith("tour-catalog_"):
        return value.removeprefix("tour-catalog_")
    if "." in value:
        return value.rsplit(".", 1)[-1]
    return value


def _tool_progress_message(name: str, value: dict[str, Any]) -> str:
    """Build a user-safe activity summary from the tool operation and structured inputs."""
    if name == "ask_choice":
        question = _summary_text(value.get("question"), 120)
        return f"Chuẩn bị lựa chọn: {question}" if question else "Chuẩn bị câu hỏi lựa chọn"
    if name == "catalog_facets":
        return "Kiểm tra điểm đến, giá và ngày khởi hành trong dữ liệu"
    if name == "query_tours":
        conditions = value.get("conditions")
        summaries = [
            item for item in (_condition_activity(condition) for condition in conditions[:3])
            if item
        ] if isinstance(conditions, list) else []
        return f"Đối chiếu tour theo: {' · '.join(summaries)}" if summaries else "Đối chiếu tour theo điều kiện"
    if name == "tour_detail":
        return "Đọc chi tiết tour và dữ kiện nguồn"
    if name == "score_soft":
        verdicts = value.get("verdicts")
        count = len(verdicts) if isinstance(verdicts, list) else 0
        return f"Đánh giá mức phù hợp qua {count} lượt đối chiếu" if count else "Đánh giá mức độ phù hợp"
    if name == "relax_criterion":
        requirement = value.get("requirement")
        conditions = requirement.get("conditions") if isinstance(requirement, dict) else None
        condition_id = value.get("condition_id")
        condition = next((item for item in conditions if isinstance(item, dict)
                          and item.get("id") == condition_id), None) if isinstance(conditions, list) else None
        summary = _condition_activity(condition) if condition else "một điều kiện"
        return f"Tìm lại sau khi nới {summary}"
    if name == "clarify_date":
        calendar = value.get("calendar")
        year, month, day = (value.get(field) for field in ("year", "month", "day"))
        if all(isinstance(item, int) and not isinstance(item, bool) for item in (year, month, day)):
            calendar_label = "ngày âm lịch" if calendar == "lunar" else "ngày dương lịch"
            return f"Đổi {calendar_label} {year:04d}-{month:02d}-{day:02d}"
        return "Kiểm tra và đổi ngày lịch"
    return "Đang kiểm tra dữ kiện"


def _condition_activity(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    field = value.get("field")
    labels = {
        "destination": "điểm đến",
        "departure_city": "nơi khởi hành",
        "date_from": "ngày đi",
        "date_to": "ngày về",
        "budget_max": "ngân sách tối đa",
        "duration_days": "thời lượng",
        "transport": "phương tiện",
        "accommodation": "lưu trú",
        "preference": "sở thích",
    }
    label = labels.get(field)
    if label is None:
        return ""
    raw = value.get("value")
    if isinstance(raw, list):
        raw = " hoặc ".join(text for item in raw if (text := _summary_text(item, 50)))
    elif isinstance(raw, int) and not isinstance(raw, bool):
        raw = f"{raw:,}".replace(",", ".")
        if field == "budget_max":
            raw = f"{raw} VND"
        elif field == "duration_days":
            raw = f"{raw} ngày"
    else:
        raw = _summary_text(raw, 60)
    return f"{label} {raw}" if raw else label


def _summary_text(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    cleaned = re.sub(r"[\x00-\x1f\x7f]", " ", value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:limit]


def _valid_choice(value: dict[str, Any]) -> bool:
    options = value.get("options")
    return (
        isinstance(value.get("question"), str)
        and isinstance(options, list)
        and bool(options)
        and all(isinstance(item, dict) for item in options)
    )


def _comparison_result(value: dict[str, Any]) -> tuple[Requirement, Comparison] | None:
    if not isinstance(value.get("requirement"), dict) or not isinstance(value.get("comparison"), dict):
        return None
    try:
        requirement = Requirement.model_validate(value["requirement"])
        comparison = Comparison.model_validate(value["comparison"])
    except (TypeError, ValueError):
        return None
    if comparison.requirement.id != requirement.id or comparison.requirement.raw_text != requirement.raw_text:
        return None
    if len({tour.id for tour in comparison.tour_snapshots}) > 5:
        return None
    return requirement, comparison


def _deduplicate_calls(values: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    out = []
    for item in values:
        key = (item["name"], item["status"])
        if key not in seen:
            out.append(item)
            seen.add(key)
    return out
