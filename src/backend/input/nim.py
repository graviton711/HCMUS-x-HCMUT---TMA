"""One NIM call: Vietnamese text → structured conditions. No other prompts."""

from __future__ import annotations

import json

import httpx

from backend.errors import AppError
from backend.settings import ExtractPromptCfg


class NimClient:
    def __init__(self, api_key: str, model: str, timeout: float = 45.0,
                 prompt: ExtractPromptCfg | None = None,
                 transport: httpx.BaseTransport | None = None):
        self._key = api_key
        self._model = model
        self._timeout = timeout
        self._prompt = prompt or ExtractPromptCfg()
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

    def extract(self, text: str) -> dict:
        if not self._key:
            raise AppError("LLM_NOT_CONFIGURED", "Chưa cấu hình NVIDIA NIM.", 503)
        body = {
            "model": self._model,
            "stream": False,
            "temperature": self._prompt.temperature,
            "max_tokens": self._prompt.max_tokens,
            "messages": [
                {"role": "system", "content": self._prompt.system},
                {"role": "user", "content": text},
            ],
            "response_format": {"type": "json_object"},
        }
        try:
            with httpx.Client(timeout=self._timeout, transport=self._transport) as client:
                response = client.post(
                    "https://integrate.api.nvidia.com/v1/chat/completions",
                    json=body,
                    headers={"Authorization": f"Bearer {self._key}"},
                )
            if response.status_code != 200:
                raise AppError("LLM_UPSTREAM_ERROR", "NIM không trích được yêu cầu.",
                               502, retryable=True)
            content = response.json()["choices"][0]["message"]["content"]
            parsed = json.loads(content)
        except AppError:
            raise
        except httpx.TimeoutException as exc:
            raise AppError("LLM_TIMEOUT", "NIM vượt thời hạn.", 504, retryable=True) from exc
        except httpx.HTTPError as exc:
            raise AppError("LLM_UPSTREAM_ERROR", "Không kết nối được NIM.", 502,
                           retryable=True) from exc
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            raise AppError("LLM_INVALID_OUTPUT", "NIM trả sai định dạng.", 502) from exc
        if not isinstance(parsed, dict):
            raise AppError("LLM_INVALID_OUTPUT", "NIM trả sai định dạng.", 502)
        return parsed
