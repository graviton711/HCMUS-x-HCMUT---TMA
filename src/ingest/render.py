"""Render CLI: thin entry over fetch.render_url (needs the `browser` extra)."""
from __future__ import annotations

import argparse
from pathlib import Path

from shared.runtime import run_cli

from .fetch import render_url


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a webpage via Playwright Chromium.")
    parser.add_argument("url", help="Target webpage URL")
    parser.add_argument("output", help="Output file path (e.g. raw/tour-1.html)")
    parser.add_argument("--timeout", type=int, default=30000, help="Navigation timeout in ms")
    parser.add_argument("--capture-net", type=Path, default=None,
                        help="Directory to save JSON XHR responses + network.json (endpoint discovery)")
    args = parser.parse_args(argv)
    render_url(args.url, args.output, timeout=args.timeout, capture_net=args.capture_net)
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli(main))
