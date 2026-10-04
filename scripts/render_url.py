"""Render a dynamic URL via Playwright Chromium and save the DOM to file.

Optionally capture JSON XHR/fetch responses (--capture-net) so an agent can
discover a site's internal API endpoints.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

MAX_BODY_BYTES = 2_000_000


def render_url(url: str, output_path: str | Path, timeout: int = 30000,
               capture_net: Path | None = None) -> list[dict[str, object]]:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    if capture_net is not None:
        capture_net.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, object]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        def on_response(response) -> None:
            ctype = response.headers.get("content-type", "")
            if "json" not in ctype.lower():
                return
            try:
                body = response.body()
                if len(body) > MAX_BODY_BYTES:
                    return
                json.loads(body.decode("utf-8", errors="strict"))
            except Exception:
                return
            base = re.sub(r"[^A-Za-z0-9._-]+", "_", urlsplit(response.url).path.strip("/"))[-60:] or "api"
            name = f"{hashlib.md5(response.url.encode()).hexdigest()[:8]}_{base}.json"
            if capture_net is not None:
                (capture_net / name).write_bytes(body)
            entries.append({"url": response.url, "status": response.status,
                            "content_type": ctype, "file": name, "bytes": len(body)})

        page.on("response", on_response)
        page.goto(url, wait_until="networkidle", timeout=timeout)
        page.wait_for_timeout(1000)
        html = page.content()
        browser.close()

    out.write_text(html, encoding="utf-8")
    if capture_net is not None:
        (capture_net / "network.json").write_text(
            json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Captured {len(entries)} JSON responses -> {capture_net / 'network.json'}")
    print(f"Rendered {url} -> {out} ({len(html)} bytes)")
    return entries


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
    raise SystemExit(main())
