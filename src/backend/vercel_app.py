"""Vercel serverless entrypoint. Imported only by the Vercel Python runtime.

Nothing else in the repo imports this module, so local dev, the CLI and the
test suite never execute it. It exists solely to hand Vercel a top-level
``app`` object without adding import-time side effects to ``backend.api``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = str(_REPO_ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from backend.api import create_app  # noqa: E402 — sys.path bootstrap above is load-bearing

if os.getenv("VERCEL") and os.getenv("DATABASE_URL", "").startswith("sqlite"):
    raise RuntimeError(
        "DATABASE_URL must be postgres:// on Vercel: SQLite files are ephemeral "
        "between serverless invocations and sessions would vanish randomly."
    )

app = create_app()
