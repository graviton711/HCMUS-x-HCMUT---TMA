"""Vercel serverless entrypoint. Imported only by the Vercel Python runtime.

Lives at the repo root (not under src/) because Vercel resolves the
``tool.vercel.entrypoint`` module to a file path relative to the service root
— dotted paths under ``src/`` do not resolve. Nothing else in the repo imports
this module, so local dev, the CLI and the test suite never execute it.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent
_SRC = str(_REPO_ROOT / "src")
if _SRC not in sys.path:
    # Covers runtimes that do not pip-install the project (src/ layout).
    # Harmless when the package is already installed.
    sys.path.insert(0, _SRC)

from backend.api import create_app  # noqa: E402 — sys.path bootstrap above is load-bearing

if os.getenv("VERCEL"):
    database_url = os.getenv("SUPABASE_TOUR_DB_URL", "")
    if not database_url.startswith(("postgres://", "postgresql://")):
        raise RuntimeError(
            "SUPABASE_TOUR_DB_URL must use a postgres:// or postgresql:// URL on Vercel; "
            "SQLite files are ephemeral between serverless invocations."
        )

app = create_app()
