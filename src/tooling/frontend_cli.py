"""Project command adapter for the frontend package scripts."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _corepack_executable() -> str:
    candidates = (
        (shutil.which("corepack.cmd"), shutil.which("corepack"))
        if os.name == "nt"
        else (shutil.which("corepack"),)
    )
    for candidate in candidates:
        if candidate is not None:
            return candidate
    raise FileNotFoundError("Corepack was not found. Install Node.js with Corepack enabled.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Tour frontend commands")
    parser.add_argument("command", choices=["dev"], help="Frontend package script to run")
    args = parser.parse_args()
    frontend_root = PROJECT_ROOT / "src" / "frontend"
    if not (frontend_root / "package.json").is_file():
        parser.error("Frontend package was not found under src/frontend.")

    try:
        return_code = subprocess.call(
            [
                _corepack_executable(),
                "pnpm",
                "--dir",
                str(frontend_root),
                args.command,
            ],
            cwd=PROJECT_ROOT,
        )
    except FileNotFoundError as exc:
        parser.error(str(exc))
    raise SystemExit(return_code)


if __name__ == "__main__":
    main()
