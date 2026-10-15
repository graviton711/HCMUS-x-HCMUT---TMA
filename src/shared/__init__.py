"""Shared cross-cutting helpers for crawl and backend.

Nothing domain-specific lives here: only infrastructure every layer needs
(logging and CLI runtime today, maybe retry/time/ids later). Backend imports
from this package directly; it must never depend on crawler internals.
"""

from .logging import RequestContextMiddleware, get_logger, redact
from .runtime import FastExit, ensure_utf8_stdout, run_cli
from .time import VN_TZ, now_vn_iso

__all__ = [
    "FastExit",
    "RequestContextMiddleware",
    "VN_TZ",
    "ensure_utf8_stdout",
    "get_logger",
    "now_vn_iso",
    "redact",
    "run_cli",
]
