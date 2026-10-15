"""Shared logging with optional rotating file output and request correlation."""

from __future__ import annotations

import logging
import os
import sys
import time
import traceback
import uuid
from contextvars import ContextVar, Token
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

_CONFIGURED_SIGNATURE: tuple[str, str | None] | None = None
_REQUEST_ID: ContextVar[str] = ContextVar("mlai_request_id", default="-")
_SECRET_HINTS = ("key", "token", "secret", "password", "cookie", "auth", "jwt")


class _RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _REQUEST_ID.get()
        return True


class _DynamicStderrHandler(logging.StreamHandler):
    """Resolve stderr at emit time so redirected/test streams are not retained."""

    def __init__(self):
        super().__init__(sys.stderr)

    def emit(self, record: logging.LogRecord) -> None:
        self.stream = sys.stderr
        super().emit(record)


def _redact_value(value: object) -> object:
    if isinstance(value, str) and len(value) > 8:
        return value[:2] + "***" + value[-2:]
    return "***"


def redact(mapping: dict) -> dict:
    """Return a copy with secret-looking values masked."""
    cleaned = {}
    for key, value in mapping.items():
        if any(hint in str(key).casefold() for hint in _SECRET_HINTS):
            cleaned[key] = _redact_value(value)
        else:
            cleaned[key] = value
    return cleaned


def set_request_id(value: str) -> Token[str]:
    """Set the request ID for the current async context; return its reset token."""
    return _REQUEST_ID.set(value)


def reset_request_id(token: Token[str]) -> None:
    _REQUEST_ID.reset(token)


def _log_file_setting() -> str:
    if os.getenv("RENDER", "").casefold() == "true":
        return ""
    if "LOG_FILE" in os.environ:
        return os.environ["LOG_FILE"].strip()

    from dotenv import dotenv_values

    local_value = dotenv_values(".env").get("LOG_FILE")
    return local_value.strip() if isinstance(local_value, str) else ".local/logs/backend.log"


class RequestContextMiddleware:
    """Add a server-generated correlation ID across the full ASGI response stream."""

    def __init__(self, app: Any):
        self.app = app
        self.logger = get_logger("backend.request")

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        request_id = uuid.uuid4().hex
        token = set_request_id(request_id)
        scope.setdefault("state", {})["request_id"] = request_id
        started = time.monotonic()
        status_code = 500
        response_started = False

        async def send_with_request_id(message: dict[str, Any]) -> None:
            nonlocal status_code, response_started
            if message.get("type") == "http.response.start":
                status_code = int(message.get("status", 500))
                response_started = True
                headers = [
                    (key, value)
                    for key, value in message.get("headers", [])
                    if key.lower() != b"x-request-id"
                ]
                headers.append((b"x-request-id", request_id.encode("ascii")))
                message = {**message, "headers": headers}
            await send(message)

        self.logger.info("request_started method=%s path=%s", scope.get("method", ""), scope.get("path", ""))
        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception as error:
            frames = traceback.extract_tb(error.__traceback__)
            frame_text = " <- ".join(
                f"{Path(frame.filename).name}:{frame.lineno}:{frame.name}" for frame in frames[-8:]
            )
            self.logger.error(
                "request_failed method=%s path=%s exception_type=%s stack=%s",
                scope.get("method", ""),
                scope.get("path", ""),
                type(error).__name__,
                frame_text,
            )
            if not response_started:
                body = b'{"error":{"code":"INTERNAL_ERROR","message":"An internal error occurred."}}'
                try:
                    await send_with_request_id({
                        "type": "http.response.start",
                        "status": 500,
                        "headers": [(b"content-type", b"application/json")],
                    })
                    await send_with_request_id({"type": "http.response.body", "body": body})
                except Exception:
                    pass
        finally:
            self.logger.info(
                "request_finished method=%s path=%s status=%d duration_ms=%d",
                scope.get("method", ""),
                scope.get("path", ""),
                status_code,
                round((time.monotonic() - started) * 1000),
            )
            reset_request_id(token)


def get_logger(name: str, level: str | None = None) -> logging.Logger:
    """Return a child logger configured for stderr and optional rotating file.

    Level priority: explicit arg > LOG_LEVEL env > INFO. `LOG_FILE` enables a
    second sink with 10 MiB files and five backups. Configuration is reapplied
    when either setting changes, which also keeps CLI and tests predictable.
    """
    global _CONFIGURED_SIGNATURE
    resolved_level = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    file_value = _log_file_setting()
    resolved_file = str(Path(file_value).expanduser()) if file_value else None
    signature = (resolved_level, resolved_file)
    logger = logging.getLogger(f"mlai.{name}")
    if _CONFIGURED_SIGNATURE != signature:
        root = logging.getLogger("mlai")
        for old_handler in root.handlers[:]:
            root.removeHandler(old_handler)
            old_handler.close()

        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s %(message)s"
        )
        console = _DynamicStderrHandler()
        console.setFormatter(formatter)
        console.addFilter(_RequestContextFilter())
        root.addHandler(console)

        if resolved_file:
            log_path = Path(resolved_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                log_path,
                maxBytes=10 * 1024 * 1024,
                backupCount=5,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            file_handler.addFilter(_RequestContextFilter())
            root.addHandler(file_handler)

        root.setLevel(getattr(logging, resolved_level, logging.INFO))
        _CONFIGURED_SIGNATURE = signature
    return logger
