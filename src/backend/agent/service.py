"""Owner-scoped provider sessions and grounded request/response turns."""

from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator
from secrets import token_hex
from typing import Any

from backend.agent.codex_runner import CodexRunner
from backend.agent.results import json_candidates, limit_comparison
from backend.agent.runner import OpenCodeRunner, raise_for_error_event
from backend.data.sessions import BaseStore
from backend.errors import AppError
from backend.models import Comparison, Requirement
from backend.settings import Settings
from shared import get_logger

_LOCAL_ID = re.compile(r"^agt_[A-Za-z0-9]{16,40}$")
_OPENCODE_ID = re.compile(r"^ses_[A-Za-z0-9_-]{8,120}$")
_CODEX_THREAD_ID = re.compile(r"^[A-Za-z0-9_-]{8,160}$")
_MCP_TOOL_NAMES = (
    "draft_requirement",
    "catalog_facets",
    "discover_destinations",
    "query_tours",
    "tour_detail",
    "score_soft",
    "ask_choice",
    "clarify_date",
)
_log = get_logger("backend.agent.service")


class _AssistantTextCollector:
    """Collect final OpenCode text by message and part identity."""

    def __init__(self) -> None:
        self._messages: dict[str, dict[str, str]] = {}
        self.duplicate_events = 0
        self.filtered_parts = 0

    @property
    def message_count(self) -> int:
        return len(self._messages)

    @property
    def part_count(self) -> int:
        return sum(len(parts) for parts in self._messages.values())

    def add(self, part: dict[str, Any]) -> None:
        text = part.get("text")
        if not isinstance(text, str):
            return

        metadata = part.get("metadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        provider_metadata = metadata.get("openai")
        provider_metadata = provider_metadata if isinstance(provider_metadata, dict) else {}
        if (
            not text.strip()
            or part.get("synthetic")
            or part.get("ignored")
            or provider_metadata.get("phase") == "commentary"
        ):
            self.filtered_parts += 1
            return

        message_id = part.get("messageID")
        message_key = message_id if isinstance(message_id, str) and message_id else "__unattributed__"
        part_id = part.get("id")
        part_key = part_id if isinstance(part_id, str) and part_id else f"text:{text}"
        message_parts = self._messages.setdefault(message_key, {})
        if part_key in message_parts:
            self.duplicate_events += 1
        # OpenCode identifies updates with the same part ID. Replace the snapshot in place
        # instead of appending it as another copy of the assistant's text.
        message_parts[part_key] = text

    def render(self) -> str:
        # Earlier assistant messages can be intermediate drafts. The last completed
        # user-facing assistant message is the response for this CLI turn.
        for parts in reversed(tuple(self._messages.values())):
            text = "\n\n".join(value.strip() for value in parts.values() if value.strip())
            if text:
                return text
        return ""


class AgentService:
    def __init__(self, settings: Settings, store: BaseStore):
        self.settings = settings
        self.store = store
        self.runner = CodexRunner(settings) if settings.agent_provider == "codex" else OpenCodeRunner(settings)
        self._locks: dict[tuple[str, str], asyncio.Lock] = {}

    @property
    def available(self) -> bool:
        if not self.runner.configured:
            return False
        if isinstance(self.runner, OpenCodeRunner):
            try:
                self.runner._executable()
            except AppError:
                return False
        return True

    def create_session(self, owner_id: str) -> dict[str, str]:
        if not self.available:
            raise AppError("AGENT_DISABLED", "The configured agent provider is not available.", 503)
        return {"agent_session_id": self.store.create_agent_session(owner_id)}

    async def message(self, owner_id: str, local_id: str, message: str) -> dict[str, Any]:
        response: dict[str, Any] | None = None
        async for event in self.stream_message(owner_id, local_id, message):
            if event.get("type") == "result" and isinstance(event.get("response"), dict):
                response = event["response"]
        if response is None:
            raise AppError(
                self._response_empty_code,
                "The agent completed without returning a message or tool result.",
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
            self.store.save_conversation_turn(local_id, message.strip())
            headed = (
                f"Conversation {local_id} (pass as conversation_id in catalog tool calls).\n"
                f"{message.strip()}"
            )
            async for event in self._message_events(owner_id, local_id, headed):
                yield event

    async def decision(
        self,
        owner_id: str,
        local_id: str,
        requirement: Requirement,
        snapshot_comparison_id: str | None = None,
        expand_soft_review: bool = False,
    ) -> dict[str, Any]:
        response: dict[str, Any] | None = None
        async for event in self.stream_decision(
            owner_id,
            local_id,
            requirement,
            snapshot_comparison_id=snapshot_comparison_id,
            expand_soft_review=expand_soft_review,
        ):
            if event.get("type") == "result" and isinstance(event.get("response"), dict):
                response = event["response"]
        if response is None:
            raise AppError(
                self._response_empty_code,
                "The agent completed without returning a decision comparison.",
                502,
                retryable=True,
            )
        return response

    async def stream_decision(
        self,
        owner_id: str,
        local_id: str,
        requirement: Requirement,
        snapshot_comparison_id: str | None = None,
        expand_soft_review: bool = False,
    ) -> AsyncIterator[dict[str, Any]]:
        if not _LOCAL_ID.fullmatch(local_id):
            raise AppError("AGENT_SESSION_INVALID", "Invalid agent session ID.", 400)
        decision_run_id = f"dec_{token_hex(16)}"
        if snapshot_comparison_id is not None:
            snapshot = self.store.get_decision_snapshot(snapshot_comparison_id, owner_id)
            if not snapshot.decision_trace or not snapshot.decision_trace.snapshot_available:
                raise AppError(
                    "SCENARIO_SNAPSHOT_UNAVAILABLE",
                    "The original scan snapshot is unavailable. Rerun the original comparison first.",
                    409,
                )
            if expand_soft_review and snapshot.requirement != requirement:
                raise AppError(
                    "SOFT_REVIEW_REQUIREMENT_MISMATCH",
                    "A review expansion must use the original comparison criteria.",
                    409,
                )
            self.store.save_scenario_snapshot_handoff(decision_run_id, snapshot)
        payload = requirement.model_dump_json(exclude_none=True)
        if snapshot_comparison_id is None:
            message = (
                "[REVIEWED DECISION RUN]\n"
                "The user has reviewed and confirmed this requirement. Run it exactly as given; "
                "call query_tours with the same requirement_id and fields plus the exact "
                "decision_run_id below, then evaluate every soft-review batch using score_soft. "
                "The final tool call stores the comparison for the backend; do not repeat its full "
                "JSON or claim completion before the tools finish. "
                "Do not ask for more information unless a tool reports a real validation error.\n"
                f"DECISION_RUN_ID={decision_run_id}\n"
                f"REQUIREMENT_JSON={payload}"
            )
        elif expand_soft_review:
            message = (
                "[SOFT REVIEW EXPANSION]\n"
                "Continue the existing immutable comparison using its retained scan snapshot. "
                "Call query_tours with the exact requirement and decision_run_id below, set the exact "
                "snapshot_comparison_id, and set expand_soft_review=true. Do not rescan the catalog, "
                "change criteria, or re-evaluate tours already scored in this comparison. Evaluate every "
                "candidate returned in the next soft_review batch using score_soft. The backend will "
                "merge earlier validated verdicts and re-rank all evaluated tours into a new comparison "
                "version; do not repeat the full JSON or claim completion before the tools finish.\n"
                f"DECISION_RUN_ID={decision_run_id}\n"
                f"SNAPSHOT_COMPARISON_ID={snapshot_comparison_id}\n"
                f"REQUIREMENT_JSON={payload}"
            )
        else:
            message = (
                "[WHAT-IF SCENARIO RUN]\n"
                "This is a comparison-only scenario. Keep the baseline unchanged. Call query_tours "
                "with the exact requirement and decision_run_id below, and set the exact "
                "snapshot_comparison_id to the supplied source comparison. Evaluate every soft-review "
                "batch using score_soft before returning. Do not start a fresh catalog scan; the backend "
                "may hydrate selected source records only when their observed timestamps still match "
                "the retained scan snapshot. "
                "Do not ask for more information unless a tool reports a validation error.\n"
                f"DECISION_RUN_ID={decision_run_id}\n"
                f"SNAPSHOT_COMPARISON_ID={snapshot_comparison_id}\n"
                f"REQUIREMENT_JSON={payload}"
            )
        key = (owner_id, local_id)
        lock = self._locks.setdefault(key, asyncio.Lock())
        try:
            async with lock:
                headed = (
                    f"Conversation {local_id} (pass as conversation_id in catalog tool calls).\n"
                    f"{message}"
                )
                async for event in self._message_events(
                    owner_id,
                    local_id,
                    headed,
                    expected_requirement=requirement,
                    decision_run_id=decision_run_id,
                    snapshot_comparison_id=snapshot_comparison_id,
                    expand_soft_review=expand_soft_review,
                ):
                    yield event
        finally:
            try:
                self.store.delete_decision_result(decision_run_id)
                if snapshot_comparison_id is not None:
                    self.store.delete_scenario_snapshot_handoff(decision_run_id)
            except Exception:
                # Best-effort cleanup must not replace a completed response or cancellation.
                pass

    async def _message_events(
        self,
        owner_id: str,
        local_id: str,
        message: str,
        expected_requirement: Requirement | None = None,
        decision_run_id: str | None = None,
        snapshot_comparison_id: str | None = None,
        expand_soft_review: bool = False,
    ) -> AsyncIterator[dict[str, Any]]:
        operation = "decision" if expected_requirement is not None else "message"
        _log.info("agent_turn_started operation=%s", operation)
        assistant_text = _AssistantTextCollector()
        tool_calls: list[dict[str, str]] = []
        active_tool_ids: dict[str, str] = {}
        tool_messages: dict[str, str] = {}
        tool_sequence = 0
        choices: dict[str, Any] | None = None
        final_requirement: Requirement | None = None
        final_comparison: Comparison | None = None
        requirement_draft: Requirement | None = None

        try:
            provider = self.settings.agent_provider
            session_id = self.store.get_agent_session(local_id, owner_id, provider)
            yield {"type": "progress", "status": "working"}
            async for event in self.runner.events(message, session_id):
                raise_for_error_event(event)
                if event.get("type") == "usage":
                    usage = event.get("usage")
                    usage = usage if isinstance(usage, dict) else {}
                    input_tokens = _usage_count(usage, "input_tokens", "prompt_tokens")
                    output_tokens = _usage_count(usage, "output_tokens", "completion_tokens")
                    total_tokens = _usage_count(usage, "total_tokens")
                    _log.info(
                        "agent_usage provider=%s input_tokens=%s output_tokens=%s total_tokens=%s",
                        provider,
                        input_tokens,
                        output_tokens,
                        total_tokens,
                    )
                    continue
                properties = event.get("properties")
                properties = properties if isinstance(properties, dict) else {}
                observed_id = event.get("sessionID") or properties.get("sessionID")
                id_pattern = _CODEX_THREAD_ID if provider == "codex" else _OPENCODE_ID
                if isinstance(observed_id, str) and id_pattern.fullmatch(observed_id):
                    if session_id is None:
                        self.store.save_agent_session(local_id, owner_id, observed_id, provider)
                        session_id = observed_id

                part = event.get("part") or properties.get("part")
                if not isinstance(part, dict):
                    continue
                kind = event.get("type")
                if kind == "text" and isinstance(part.get("text"), str):
                    before = assistant_text.render()
                    assistant_text.add(part)
                    after = assistant_text.render()
                    if after and after != before:
                        yield {"type": "text", "text": after}
                    continue

                state = part.get("state")
                state = state if isinstance(state, dict) else {}
                invocations = _tool_invocations(part, state)
                successful_tool_names: set[str] = set()
                for invocation in invocations:
                    tool_name = invocation["name"]
                    status = invocation["status"]
                    log_status = (
                        "completed" if status in {"completed", "success"} else
                        "error" if status in {"error", "failed"} else "running"
                    )
                    _log.info("agent_tool name=%s status=%s", tool_name, log_status)
                    tool_calls.append({"name": tool_name, "status": status})
                    call_id = invocation["id"]
                    if not call_id:
                        terminal = status in {"completed", "success", "error", "failed"}
                        call_id = active_tool_ids.get(tool_name, "")
                        if not call_id:
                            tool_sequence += 1
                            call_id = f"tool-{tool_sequence}"
                        if not terminal:
                            active_tool_ids[tool_name] = call_id
                    message_summary = _tool_progress_message(tool_name, invocation["input"])
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
                    if status in {"completed", "success"}:
                        successful_tool_names.add(tool_name)

                if not successful_tool_names:
                    continue
                output = state.get("output", part.get("output"))
                if output is None:
                    output = state.get("content", part.get("content"))
                draft_parse_valid = False
                for payload in json_candidates(output):
                    if "ask_choice" in successful_tool_names and _valid_choice(payload):
                        choices = {
                            "question": payload["question"],
                            "options": payload["options"],
                            "allow_custom": bool(payload.get("allow_custom", True)),
                        }
                    if "draft_requirement" in successful_tool_names:
                        draft = _requirement_draft(payload)
                        if draft is not None:
                            requirement_draft = draft
                            draft_parse_valid = True
                    result = _comparison_result(payload)
                    if result is None:
                        continue
                    requirement, comparison = result
                    if expected_requirement is not None and requirement != expected_requirement:
                        raise AppError(
                            "DECISION_REQUIREMENT_MISMATCH",
                            "The agent returned a comparison for different criteria. Please run the reviewed brief again.",
                            502,
                        )
                    snapshot_mismatch = (
                        comparison.expanded_from_comparison_id != snapshot_comparison_id
                        if expand_soft_review
                        else comparison.scenario_source_comparison_id != snapshot_comparison_id
                    )
                    if snapshot_comparison_id is not None and snapshot_mismatch:
                        raise AppError(
                            "SCENARIO_SNAPSHOT_MISMATCH",
                            "The agent returned a comparison from a different scan snapshot.",
                            502,
                        )
                    final_requirement = requirement
                    final_comparison = comparison
                if "draft_requirement" in successful_tool_names:
                    _log.info("agent_draft_parse valid=%s", draft_parse_valid)
        except Exception as error:
            if (
                provider == "codex"
                and isinstance(error, AppError)
                and error.code == "CODEX_THREAD_EXPIRED"
            ):
                self.store.clear_agent_session(local_id, owner_id, provider)
            if expected_requirement is None or decision_run_id is None:
                raise
            persisted = self.store.pop_decision_result(decision_run_id)
            if persisted is None:
                raise
            final_requirement, final_comparison = self._validate_decision_result(
                persisted, expected_requirement, snapshot_comparison_id, expand_soft_review
            )
        finally:
            _log.info(
                "agent_text_aggregation message_count=%d part_count=%d duplicate_events=%d filtered_parts=%d",
                assistant_text.message_count,
                assistant_text.part_count,
                assistant_text.duplicate_events,
                assistant_text.filtered_parts,
            )

        if expected_requirement is not None and decision_run_id is not None and final_comparison is None:
            persisted = self.store.pop_decision_result(decision_run_id)
            if persisted is not None:
                final_requirement, final_comparison = self._validate_decision_result(
                    persisted, expected_requirement, snapshot_comparison_id, expand_soft_review
                )

        response: dict[str, Any] = {
            "assistant_text": assistant_text.render(),
            "tool_calls": _deduplicate_calls(tool_calls),
        }
        if choices is not None:
            response["choices"] = choices
        if final_requirement is not None:
            self.store.save_requirement(final_requirement, owner_id)
            response["requirement"] = final_requirement.model_dump(mode="json")
        elif requirement_draft is not None:
            self.store.save_requirement(requirement_draft, owner_id)
            response["requirement"] = requirement_draft.model_dump(mode="json")
            response["decision_draft"] = requirement_draft.model_dump(mode="json")
        if final_comparison is not None:
            if final_requirement is None:
                final_requirement = final_comparison.requirement
                self.store.save_requirement(final_requirement, owner_id)
                response["requirement"] = final_requirement.model_dump(mode="json")
            self.store.save_decision_snapshot(final_comparison, owner_id)
            final_comparison = limit_comparison(final_comparison)
            self.store.save_comparison(final_comparison, owner_id)
            response["comparison"] = final_comparison.model_dump(mode="json")
        if expected_requirement is not None and final_comparison is None:
            raise AppError(
                "DECISION_INCOMPLETE",
                "The agent did not complete the reviewed tour comparison.",
                502,
                retryable=True,
            )
        if (
            not response["assistant_text"]
            and response["tool_calls"]
            and not any((choices, final_requirement, final_comparison))
        ):
            response["assistant_text"] = "Mình chưa lấy được kết quả lần này. Bạn thử lại nhé."
        if not any((response["assistant_text"], response["tool_calls"], choices, final_requirement,
                    final_comparison)):
            raise AppError(
                self._response_empty_code,
                "The agent completed without returning a message or tool result.",
                502,
                retryable=True,
            )
        _log.info(
            "agent_turn_completed operation=%s decision_draft_attached=%s comparison_attached=%s tool_count=%d",
            operation,
            "decision_draft" in response,
            "comparison" in response,
            len(response["tool_calls"]),
        )
        yield {"type": "result", "response": response}

    @staticmethod
    def _validate_decision_result(
        comparison: Comparison,
        expected_requirement: Requirement,
        snapshot_comparison_id: str | None = None,
        expand_soft_review: bool = False,
    ) -> tuple[Requirement, Comparison]:
        if comparison.requirement != expected_requirement:
            raise AppError(
                "DECISION_REQUIREMENT_MISMATCH",
                "The completed comparison does not match the reviewed criteria.",
                502,
            )
        snapshot_mismatch = (
            comparison.expanded_from_comparison_id != snapshot_comparison_id
            if expand_soft_review
            else comparison.scenario_source_comparison_id != snapshot_comparison_id
        )
        if snapshot_comparison_id is not None and snapshot_mismatch:
            raise AppError(
                "SCENARIO_SNAPSHOT_MISMATCH",
                "The completed comparison does not use the requested scan snapshot.",
                502,
            )
        return comparison.requirement, comparison

    @property
    def _response_empty_code(self) -> str:
        if self.settings.agent_provider == "opencode":
            return "OPENCODE_RESPONSE_EMPTY"
        return "AGENT_RESPONSE_EMPTY"


def _tool_name(value: str) -> str:
    normalized = value.rsplit(".", 1)[-1]
    for name in _MCP_TOOL_NAMES:
        if normalized == name or normalized.endswith(f"_{name}"):
            return name
    return normalized


def _usage_count(usage: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = usage.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
    return None


def _nested_tool_calls(metadata: Any) -> list[Any] | None:
    """Find logical MCP calls across OpenCode metadata wrapper versions."""
    for _ in range(16):
        if not isinstance(metadata, dict):
            return None
        calls = metadata.get("toolCalls")
        if isinstance(calls, list):
            return calls
        metadata = metadata.get("metadata")
    return None


def _tool_invocations(part: dict[str, Any], state: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize direct MCP events and OpenCode Code Mode's nested tool metadata."""
    outer_tool = part.get("tool") or part.get("name")
    outer_name = _tool_name(outer_tool) if isinstance(outer_tool, str) else ""
    outer_id = part.get("callID") or part.get("call_id") or part.get("id")

    metadata = state.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    nested_calls = _nested_tool_calls(metadata)
    if outer_name == "execute":
        if not isinstance(nested_calls, list):
            # `execute` is an OpenCode wrapper, not a user-facing business operation.
            # In particular, a malformed wrapper call must not count as a failed MCP call.
            return []
        invocations = []
        for index, call in enumerate(nested_calls):
            if not isinstance(call, dict):
                continue
            raw_name = call.get("tool") or call.get("name")
            if not isinstance(raw_name, str):
                continue
            name = _tool_name(raw_name)
            if name not in _MCP_TOOL_NAMES:
                continue
            tool_input = call.get("input") or call.get("arguments")
            if not isinstance(tool_input, dict):
                tool_input = {}
            call_id = call.get("callID") or call.get("id")
            if not isinstance(call_id, str) or not call_id:
                call_id = f"{outer_id}-{index}" if isinstance(outer_id, str) and outer_id else ""
            invocations.append({
                "id": call_id,
                "name": name,
                "status": str(call.get("status", state.get("status", "running"))),
                "input": tool_input,
            })
        return invocations

    if not outer_name or outer_name not in _MCP_TOOL_NAMES:
        return []
    tool_input = state.get("input")
    if not isinstance(tool_input, dict):
        tool_input = part.get("input") or part.get("arguments")
    if not isinstance(tool_input, dict):
        tool_input = {}
    return [{
        "id": outer_id if isinstance(outer_id, str) else "",
        "name": outer_name,
        "status": str(state.get("status", "running")),
        "input": tool_input,
    }]


def _tool_progress_message(name: str, value: dict[str, Any]) -> str:
    """Build a user-safe activity summary from the tool operation and structured inputs."""
    if name == "ask_choice":
        question = _summary_text(value.get("question"), 120)
        return f"Chuẩn bị lựa chọn: {question}" if question else "Chuẩn bị câu hỏi lựa chọn"
    if name == "catalog_facets":
        return "Kiểm tra điểm đến, giá và ngày khởi hành trong dữ liệu"
    if name == "discover_destinations":
        return "Lọc điểm đến theo các điều kiện đã biết"
    if name == "draft_requirement":
        return "Chuẩn bị bản điều kiện để bạn xem"
    if name == "query_tours":
        if value.get("expand_soft_review") is True:
            return "Đánh giá nhóm tour tiếp theo trên snapshot đã lưu"
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
        return f"Đánh giá ưu tiên và dữ kiện qua {count} lượt đối chiếu" if count else "Đánh giá dữ kiện tour"
    if name == "clarify_date":
        calendar = value.get("calendar")
        year, month, day = (value.get(field) for field in ("year", "month", "day"))
        if all(isinstance(item, int) and not isinstance(item, bool) for item in (year, month, day)):
            calendar_label = "ngày âm lịch" if calendar == "lunar" else "ngày dương lịch"
            return f"Đổi {calendar_label} {year:04d}-{month:02d}-{day:02d}"
        return "Kiểm tra và đổi ngày lịch"
    return "Đang xử lý yêu cầu"


def _condition_activity(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    field = value.get("field")
    labels = {
        "destination": "điểm đến",
        "departure_city": "nơi khởi hành",
        "date_from": "ngày đi",
        "date_to": "ngày khởi hành đến",
        "budget_max": "ngân sách tối đa",
        "duration_days": "thời lượng",
        "transport": "phương tiện",
        "accommodation": "lưu trú",
        "preference": "sở thích",
    }
    label = labels.get(field) if isinstance(field, str) else None
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
    max_snapshots = 50 if comparison.decision_views else 5
    if len({tour.id for tour in comparison.tour_snapshots}) > max_snapshots:
        return None
    if any(len(view.candidates) > 5 for view in comparison.decision_views):
        return None
    return requirement, comparison


def _requirement_draft(value: dict[str, Any]) -> Requirement | None:
    raw = value.get("requirement_draft")
    if not isinstance(raw, dict):
        return None
    try:
        requirement = Requirement.model_validate(raw)
    except (TypeError, ValueError):
        return None
    soft = requirement.soft()
    if soft and (
        any(condition.weight_percent is None for condition in soft)
        or sum(condition.weight_percent or 0 for condition in soft) != 100
    ):
        return None
    return requirement


def _deduplicate_calls(values: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    out = []
    for item in values:
        key = (item["name"], item["status"])
        if key not in seen:
            out.append(item)
            seen.add(key)
    return out
