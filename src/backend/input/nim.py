"""Single NIM JSON gateway. All backend LLM calls go through complete_json."""

from __future__ import annotations

import json

import httpx

from backend.errors import AppError
from backend.settings import PromptCfg
from shared import get_logger

log = get_logger("nim")


class NimClient:
    def __init__(self, api_key: str, model: str, timeout: float,
                 prompt: PromptCfg | None = None,
                 transport: httpx.BaseTransport | None = None):
        self._key = api_key
        self._model = model
        self._timeout = timeout
        self._prompt = prompt
        self._transport = transport

    def configured(self) -> bool:
        return bool(self._key)

    @property
    def api_key(self) -> str:
        return self._key

    @property
    def model(self) -> str:
        return self._model

    @property
    def timeout(self) -> float:
        return self._timeout

    @property
    def prompt(self) -> PromptCfg | None:
        return self._prompt

    def complete_json(self, *, system: str, user: str,
                      max_tokens: int, temperature: float) -> dict:
        """Single NIM JSON gateway. All LLM calls go through here."""
        body = {
            "model": self._model,
            "stream": False,
            "temperature": temperature,
            "max_tokens": max_tokens,
            # Mechanical JSON tasks: no chain-of-thought, deterministic output.
            "reasoning_effort": "none",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
        }
        for attempt in (1, 2):
            try:
                with httpx.Client(timeout=self._timeout, transport=self._transport) as client:
                    response = client.post(
                        "https://integrate.api.nvidia.com/v1/chat/completions",
                        json=body,
                        headers={"Authorization": f"Bearer {self._key}"},
                    )
                if response.status_code != 200:
                    log.warning("nim upstream %s", response.status_code)
                    raise AppError("LLM_UPSTREAM_ERROR", "NIM không trả lời được.",
                                   502, retryable=True)
                parsed = json.loads(response.json()["choices"][0]["message"]["content"])
                if not isinstance(parsed, dict):
                    raise AppError("LLM_INVALID_OUTPUT", "NIM trả sai định dạng.", 502)
                return parsed
            except AppError:
                raise
            except httpx.TimeoutException as exc:
                log.warning("nim timeout after %ss", self._timeout)
                raise AppError("LLM_TIMEOUT", "NIM vượt thời hạn.", 504, retryable=True) from exc
            except httpx.HTTPError as exc:
                log.warning("nim connection failed: %s", type(exc).__name__)
                raise AppError("LLM_UPSTREAM_ERROR", "Không kết nối được NIM.", 502,
                               retryable=True) from exc
            except (ValueError, KeyError, TypeError, IndexError) as exc:
                # Malformed JSON despite json_object mode is transient: retry once.
                log.warning("nim invalid output (attempt %s): %s", attempt, type(exc).__name__)
                if attempt == 2:
                    raise AppError("LLM_INVALID_OUTPUT", "NIM trả sai định dạng.", 502) from exc
        raise AppError("LLM_INVALID_OUTPUT", "NIM trả sai định dạng.", 502)

    def extract(self, text: str, ref_date: str = "") -> dict:
        if not self._key:
            raise AppError("LLM_NOT_CONFIGURED", "Chưa cấu hình NVIDIA NIM.", 503)
        if self._prompt is None or not self._prompt.system.strip():
            raise AppError("PROMPT_NOT_CONFIGURED", "Thiếu prompt extract.", 500)
        from backend.input.lunar import tet_frame

        user = text
        if ref_date:
            user += f"\nNgày tham chiếu (dương lịch): {ref_date}"
            frame = tet_frame(ref_date)
            if frame:
                user += f"\n{frame}"
        return self.complete_json(system=self._prompt.system, user=user,
                                   max_tokens=self._prompt.max_tokens,
                                   temperature=self._prompt.temperature)
