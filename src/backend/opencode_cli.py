"""Project CLI for running a local OpenCode server with project configuration."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import dotenv_values

from backend.opencode_binary import resolve_opencode_binary

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", "0.0.0.0"}


def _load_environment() -> dict[str, str]:
    """Load the project .env without exposing its values in output."""
    environment = os.environ.copy()
    for key, value in dotenv_values(PROJECT_ROOT / ".env").items():
        if value is not None and key not in environment:
            environment[key] = value
    return environment


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Tour project OpenCode commands")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="Start the configured local OpenCode server")
    serve.add_argument("--hostname", default=None, help="Bind address (default: 127.0.0.1)")
    return parser


def _server_port(server_url: str) -> int:
    url = server_url.strip() or "http://127.0.0.1:4098"
    try:
        parsed = urlsplit(url)
        configured_host = parsed.hostname
        configured_port = parsed.port
    except ValueError as exc:
        raise ValueError("OPENCODE_SERVER_URL must be a valid local HTTP URL.") from exc

    if parsed.scheme != "http" or configured_host is None:
        raise ValueError("OPENCODE_SERVER_URL must be a local http:// URL to start OpenCode here.")
    if configured_host.lower() not in LOCAL_HOSTS:
        raise ValueError(
            "OPENCODE_SERVER_URL points to a remote host; start remote OpenCode from its deploy service."
        )

    port = configured_port if configured_port is not None else 4098
    if not 1 <= port <= 65535:
        raise ValueError("OpenCode port must be between 1 and 65535.")
    return port


def main() -> None:
    from shared import ensure_utf8_stdout

    ensure_utf8_stdout()
    parser = _parser()
    args = parser.parse_args()
    environment = _load_environment()

    try:
        configured_port = _server_port(environment.get("OPENCODE_SERVER_URL", ""))
        binary = environment.get("OPENCODE_BINARY", "opencode").strip() or "opencode"
        executable = resolve_opencode_binary(binary)
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))

    hostname = args.hostname or "127.0.0.1"
    command = [
        executable,
        "serve",
        "--hostname",
        hostname,
        "--port",
        str(configured_port),
    ]
    try:
        return_code = subprocess.call(command, cwd=PROJECT_ROOT, env=environment)
    except KeyboardInterrupt:
        return_code = 130
    raise SystemExit(return_code)


if __name__ == "__main__":
    main()
