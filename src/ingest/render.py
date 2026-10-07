"""Render CLI: thin entry over fetch.render_url (needs the `browser` extra)."""
from __future__ import annotations

import argparse
from pathlib import Path

from shared.runtime import run_cli

from .extract import load_settings
from .fetch import render_url


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a webpage via Playwright Chromium.")
    parser.add_argument("url", help="Target webpage URL")
    parser.add_argument("output", help="Output file path (e.g. raw/tour-1.html)")
    parser.add_argument("--timeout", type=int, default=None,
                        help="Navigation timeout in ms (default: browser.timeout_ms in settings)")
    parser.add_argument("--capture-net", type=Path, default=None,
                        help="Directory to save JSON XHR responses + network.json (endpoint discovery)")
    args = parser.parse_args(argv)
    try:
        settings = load_settings()
    except (ValueError, RuntimeError, OSError):
        settings = {}
    timeout = (args.timeout if args.timeout is not None
               else int(settings.get("browser", {}).get("timeout_ms", 30000)))
    render_url(args.url, args.output, timeout=timeout, capture_net=args.capture_net)
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli(main))
