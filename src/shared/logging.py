"""One logger for the whole system. No secrets in logs, ever."""

from __future__ import annotations

import logging
import os
import sys

_CONFIGURED_LEVEL: str | None = None
_SECRET_HINTS = ("key", "token", "secret", "password", "cookie", "auth", "jwt")


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


def get_logger(name: str, level: str | None = None) -> logging.Logger:
    """One configured root handler (stderr); children per module.

    Level priority: explicit arg > LOG_LEVEL env > INFO. Re-applies when the
    resolved level changes so tests and CLI flags take effect.
    """
    global _CONFIGURED_LEVEL
    resolved = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    logger = logging.getLogger(f"mlai.{name}")
    if _CONFIGURED_LEVEL != resolved:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        root = logging.getLogger("mlai")
        root.handlers.clear()
        root.addHandler(handler)
        root.setLevel(getattr(logging, resolved, logging.INFO))
        _CONFIGURED_LEVEL = resolved
    return logger
