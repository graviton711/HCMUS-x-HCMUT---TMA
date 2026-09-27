from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .engine import Crawler, CrawlOptions
from .models import CrawlIssue, CrawlReport
from .safety import UnsafeURLError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="supplier-crawler", description="Audit public data exposed by a tour supplier website."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    inspect = subparsers.add_parser("inspect", help="inspect one supplier website")
    inspect.add_argument("url", help="public HTTP(S) seed URL")
    inspect.add_argument(
        "--output", "-o", type=Path, help="write the selected report format to this path"
    )
    inspect.add_argument(
        "--max-pages", type=int, default=12, help="maximum HTML pages (1-50; default: 12)"
    )
    inspect.add_argument(
        "--max-requests",
        type=int,
        default=20,
        help="maximum total HTTP requests (including robots/sitemap)",
    )
    inspect.add_argument(
        "--max-bytes", type=int, default=1_000_000, help="maximum bytes per response"
    )
    inspect.add_argument(
        "--timeout", type=float, default=12.0, help="per-request timeout in seconds"
    )
    inspect.add_argument(
        "--delay", type=float, default=1.0, help="minimum delay between requests in seconds"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        options = CrawlOptions(
            max_pages=args.max_pages,
            max_requests=args.max_requests,
            max_response_bytes=args.max_bytes,
            timeout=args.timeout,
            delay=args.delay,
        )
        report = Crawler(options).crawl(args.url)
        exit_code = 1 if report.status in {"error", "blocked"} else 0
    except (UnsafeURLError, ValueError) as exc:
        report = CrawlReport(source_url=args.url, status="error")
        report.issues.append(CrawlIssue("invalid_input", str(exc)))
        exit_code = 2

    rendered = json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
    if args.output:
        try:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered + "\n", encoding="utf-8")
        except OSError as exc:
            print(f"Could not write report: {exc}", file=sys.stderr)
            return 2
    else:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        print(rendered)
    return exit_code
