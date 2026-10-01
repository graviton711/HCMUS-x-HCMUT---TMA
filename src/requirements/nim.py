import json
import time

import httpx
from pydantic import ValidationError

from domain.common import AppError
from domain.requirements import Message, Requirement
from requirements.extraction import PROMPT_VERSION, SYSTEM_PROMPT, Extraction


class NimGateway:
    def __init__(self, settings, transport=None):
        self.settings = settings
        self.transport = transport

    async def extract(self, message: Message, previous: Requirement | None = None, *, feedback: str | None = None) -> tuple[Extraction, dict]:
        s = self.settings
        if not s.nvidia_nim_api.get_secret_value() or not s.nvidia_nim_model:
            raise AppError("LLM_NOT_CONFIGURED", "Chưa cấu hình NVIDIA NIM ở backend.", 503)
        context = None
        if previous:
            context = {"conditions": [c.model_dump(exclude={"sources"}) for c in previous.conditions],
                       "party": previous.party.model_dump(exclude={"sources"}),
                       "hard_tree": previous.hard_tree.model_dump(),
                       "preference_tree": previous.preference_tree.model_dump()}
        body = {"model": s.nvidia_nim_model, "stream": False, "temperature": 1.0, "top_p": 0.95,
                "max_tokens": s.nim_max_tokens, "reasoning_effort": s.nim_reasoning,
                "messages": [{"role": "system", "content": SYSTEM_PROMPT + "\nJSON Schema bắt buộc:\n" + json.dumps(Extraction.model_json_schema(), ensure_ascii=False)},
                             {"role": "user", "content": json.dumps({"message": message.text,
                              "received_at": message.received_at, "previous": context, "validation_feedback": feedback}, ensure_ascii=False)}],
                "response_format": {"type": "json_schema", "json_schema": {
                    "name": "requirement_extraction", "strict": True, "schema": Extraction.model_json_schema()}}}
        if s.nim_reasoning != "none":
            body["reasoning_budget"] = s.nim_reasoning_budget
        started = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=s.nim_timeout_seconds, transport=self.transport,
                                         follow_redirects=False) as client:
                response = await client.post("https://integrate.api.nvidia.com/v1/chat/completions", json=body,
                                             headers={"Authorization": f"Bearer {s.nvidia_nim_api.get_secret_value()}"})
        except httpx.TimeoutException as exc:
            raise AppError("LLM_TIMEOUT", "NIM chưa trả kết quả trong thời hạn.", 504, retryable=True) from exc
        except httpx.HTTPError as exc:
            raise AppError("LLM_UPSTREAM_ERROR", "Không kết nối được NIM.", 502, retryable=True) from exc
        if response.status_code in {401, 403}:
            raise AppError("LLM_AUTH_FAILED", "NIM từ chối credential backend.", 502)
        if response.status_code == 429:
            raise AppError("LLM_RATE_LIMITED", "NIM đang giới hạn lượt gọi.", 503, retryable=True)
        if response.status_code == 202:
            raise AppError("LLM_PENDING", "NIM trả pending; hãy thử lại sau.", 503, retryable=True)
        if response.status_code != 200:
            raise AppError("LLM_UPSTREAM_ERROR", "NIM trả lỗi upstream.", 502, retryable=response.status_code >= 500)
        try:
            payload = response.json()
            choice = payload["choices"][0]
            if choice.get("finish_reason") != "stop":
                raise ValueError("Incomplete generation")
            content = choice["message"]["content"]
            if not isinstance(content, str) or len(content) > 100000:
                raise ValueError("Invalid response size")
            result = Extraction.model_validate_json(content)
        except ValidationError as exc:
            error = AppError("LLM_INVALID_OUTPUT", "Kết quả NIM không đúng schema.", 502)
            error.repair_hint = "; ".join(f"{e['loc']}: {e['msg']}" for e in exc.errors()[:5])[:1500]
            raise error from exc
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise AppError("LLM_INVALID_OUTPUT", "Kết quả NIM không đúng schema hoặc bị cắt ngắn.", 502) from exc
        usage = payload.get("usage", {})
        return result, {"model": s.nvidia_nim_model, "prompt_version": PROMPT_VERSION,
                        "reasoning": s.nim_reasoning, "latency_seconds": round(time.monotonic() - started, 3),
                        "tokens": {k: v for k, v in usage.items() if k in {
                            "prompt_tokens", "completion_tokens", "total_tokens"} and type(v) is int}}


async def parse_validated(nim, message, previous=None, **context):
    """At most one schema/grounding repair; caller owns the total deadline."""
    from requirements.service import from_extraction
    feedback, attempts = None, []
    for attempt in range(2):
        try:
            extraction, metrics = await nim.extract(message, previous, feedback=feedback)
            attempts.append(metrics)
            r = from_extraction(extraction=extraction, message=message, previous=previous, **context)
            return r, {"attempts": attempts, "repair_used": attempt > 0}
        except ValidationError as exc:
            feedback = "; ".join(f"{e['loc']}: {e['msg']}" for e in exc.errors()[:5])[:1500]
            if attempt:
                raise AppError("LLM_INVALID_OUTPUT", "Output vi phạm schema/ngữ nghĩa sau repair.", 502) from exc
        except AppError as exc:
            if exc.code != "LLM_INVALID_OUTPUT" or attempt:
                raise
            feedback = getattr(exc, "repair_hint", exc.message)
    raise AppError("LLM_INVALID_OUTPUT", "Không tạo được requirement hợp lệ.", 502)
