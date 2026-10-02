"""Render a dynamic URL via Playwright Chromium and save the DOM to file."""
from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright


def render_url(url: str, output_path: str | Path, timeout: int = 30000) -> None:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=timeout)
        page.wait_for_timeout(1000)
        html = page.content()
        browser.close()
    out.write_text(html, encoding="utf-8")
    print(f"Rendered {url} -> {out} ({len(html)} bytes)")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Render a webpage via Playwright Chromium.")
    parser.add_argument("url", help="Target webpage URL")
    parser.add_argument("output", help="Output file path (e.g. raw/tour-1.html)")
    parser.add_argument("--timeout", type=int, default=30000, help="Navigation timeout in ms")
    args = parser.parse_args(argv)
    render_url(args.url, args.output, timeout=args.timeout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
