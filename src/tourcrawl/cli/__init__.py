"""Single entry point for the team. No business logic beyond argv."""

from __future__ import annotations

import argparse
import io
import os
import sys
from pathlib import Path

from shared import get_logger

from ..fetch import RateLimiter, SafeFetcher
from ..pipeline import run_batch, run_tour, sitemap_urls
from ..profiles import load_profile, load_settings

log = get_logger("cli")


def _load_dotenv() -> None:
    try:
        text = Path(".env").read_text(encoding="utf-8")
    except OSError:
        return
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip("'\"")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="tour-crawl", description="Crawl tour data by source profile.")
    parser.add_argument("url", nargs="?", help="single tour URL")
    parser.add_argument("--profile", "-p", default="vietravel", help="source profile name")
    parser.add_argument("--batch", type=Path, help="CSV file with a url column")
    parser.add_argument("--sitemap", action="store_true", help="enumerate profile sitemaps instead")
    parser.add_argument("--limit", type=int, default=0, help="max tours (0 = all)")
    parser.add_argument("--output", "-o", type=Path, default=None, help="CSV output path")
    parser.add_argument("--out-dir", type=Path, default=None, help="JSON detail directory")
    parser.add_argument("--no-browser", action="store_true", help="skip browser flow")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = _parse_args(argv)
    _load_dotenv()
    os.environ.setdefault("LOG_LEVEL", "INFO")

    try:
        settings = load_settings()
        profile = load_profile(args.profile)
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"Invalid config: {exc}", file=sys.stderr)
        return 2
    if args.no_browser:
        profile = {**profile, "flows": [flow for flow in profile.get("flows", []) if "browser" not in flow]}

    import csv

    if args.batch:
        with args.batch.open(encoding="utf-8-sig") as handle:
            urls = [row["url"] for row in csv.DictReader(handle) if row.get("url")]
    elif args.sitemap:
        fetch_cfg = settings.get("fetch", {})
        fetcher = SafeFetcher(
            timeout=float(fetch_cfg.get("timeout_s", 20)),
            max_bytes=int(fetch_cfg.get("max_bytes", 2_000_000)),
            user_agent=str(fetch_cfg.get("user_agent", "MLAITourSourceAuditor/0.1")),
            limiter=RateLimiter(float(fetch_cfg.get("delay_s", 1.0))),
        )
        urls = sitemap_urls(fetcher, profile.get("sitemaps", []), profile.get("tour_url_patterns", []))
        print(f"sitemap urls: {len(urls)}")
    elif args.url:
        urls = [args.url]
    else:
        print("Provide a URL, --batch, or --sitemap.", file=sys.stderr)
        return 2
    if args.limit > 0:
        urls = urls[: args.limit]

    out_dir = args.out_dir or (Path(settings.get("output", {}).get("dir", ".local")) / "tours")
    if len(urls) == 1 and not args.batch and not args.sitemap:
        from ..validate import BLOCKED, FETCH_FAIL

        try:
            row = run_tour(urls[0], profile, settings, out_dir)
        except Exception as exc:
            print(f"Tour failed: {type(exc).__name__}", file=sys.stderr)
            return 1
        print(f"status={row['status']} title={row.get('title', '')[:80]} "
              f"departures={row.get('departures', 0)} error={row.get('error', '')}")
        return 0 if row["status"] not in (BLOCKED, FETCH_FAIL) else 1

    output = args.output or (Path(settings.get("output", {}).get("dir", ".local")) / "tours.csv")
    out_dir = args.out_dir or (Path(settings.get("output", {}).get("dir", ".local")) / "tours")
    return run_batch(urls, profile, settings, output, out_dir)


if __name__ == "__main__":
    raise SystemExit(main())
