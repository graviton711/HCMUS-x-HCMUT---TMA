"""Safe, transport-boundary logging policy for backend errors."""

from __future__ import annotations

import logging
import traceback
from pathlib import Path

from backend.errors import AppError
from shared import get_logger

_log = get_logger("backend.errors")


def log_app_error(error: AppError, *, transport: str, operation: str) -> None:
    """Log only server-side or retryable application errors, without messages."""
    if error.status < 500 and not error.retryable:
        return
    level = logging.ERROR if error.status >= 500 else logging.WARNING
    _log.log(
        level,
        "application_error transport=%s operation=%s code=%s status=%d retryable=%s",
        transport,
        operation,
        error.code,
        error.status,
        error.retryable,
    )


def log_unexpected_error(error: Exception, *, transport: str, operation: str) -> None:
    """Log exception type and source frames, never exception text or payloads."""
    frames = traceback.extract_tb(error.__traceback__)
    stack = " <- ".join(
        f"{Path(frame.filename).name}:{frame.lineno}:{frame.name}" for frame in frames[-8:]
    )
    _log.error(
        "unexpected_error transport=%s operation=%s exception_type=%s stack=%s",
        transport,
        operation,
        type(error).__name__,
        stack,
    )
