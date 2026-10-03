"""Shared cross-cutting helpers for crawl, backend and frontend.

Nothing domain-specific lives here: only infrastructure every layer needs
(logging today, maybe retry/time/ids later). Backend and frontend import
from this package directly; they must never depend on crawler internals.
"""

from .logging import get_logger, redact

__all__ = ["get_logger", "redact"]
