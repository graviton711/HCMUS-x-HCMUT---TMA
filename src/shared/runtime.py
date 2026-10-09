"""Small runtime utilities for command-line entrypoints."""
from __future__ import annotations

import signal
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from types import FrameType

INTERRUPTED_EXIT_CODE = 130


class FastExit(BaseException):
    """Internal cancellation signal that must bypass ordinary error handling."""


def _interrupt(_signum: int, _frame: FrameType | None) -> None:
    raise FastExit()


@contextmanager
def fast_safe_exit() -> Iterator[None]:
    """Turn Ctrl+C into a quiet cancellation while restoring the prior handler."""
    previous_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, _interrupt)
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, previous_handler)


def run_cli(action: Callable[[], int]) -> int:
    """Run a CLI action and return 130 for Ctrl+C without a traceback."""
    try:
        with fast_safe_exit():
            return action()
    except (FastExit, KeyboardInterrupt):
        return INTERRUPTED_EXIT_CODE


def ensure_utf8_stdout() -> None:
    """Best-effort UTF-8 stdout for Windows consoles. Never raises."""
    with suppress(Exception):
        reconfigure = getattr(sys.stdout, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")
