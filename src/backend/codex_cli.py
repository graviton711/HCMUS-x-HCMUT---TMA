"""CLI for starting the separate Codex gateway service."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import dotenv_values

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_environment() -> None:
    for key, value in dotenv_values(_PROJECT_ROOT / ".env").items():
        if value is not None:
            os.environ.setdefault(key, value)


def main() -> None:
    parser = argparse.ArgumentParser(description="TourLens Codex CLI gateway")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="Run the Codex gateway")
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", type=int, default=None)
    args = parser.parse_args()
    _load_environment()

    if args.command == "serve":
        import uvicorn

        host = args.host or os.environ.get("CODEX_SERVER_HOST", "127.0.0.1")
        port = args.port or int(os.environ.get("CODEX_SERVER_PORT", "4099"))
        uvicorn.run("backend.codex_gateway:create_app", factory=True, host=host, port=port, workers=1)


if __name__ == "__main__":
    main()
