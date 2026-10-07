"""Shared cross-cutting helpers for crawl, backend and frontend.

Nothing domain-specific lives here: only infrastructure every layer needs
(logging and CLI runtime today, maybe retry/time/ids later). Backend and
frontend import from this package directly; they must never depend on
crawler internals.
"""

from .logging import get_logger, redact
from .runtime import FastExit, run_cli

__all__ = ["FastExit", "get_logger", "redact", "run_cli"]
