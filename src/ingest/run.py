"""Full source chain in one command: survey -> discover -> batch -> migrate -> publish.

Steps compose through the per-source defaults (no paths passed): discover
writes `<output.dir>/<source>/discovered.csv`, batch reads it, publish ships
`<source>/tours/`. No separate audit pass: batch already scores per-tour
evidence while crawling, so a second full crawl adds cost without new
information. Run `python -m ingest.audit` by hand when the profile changes
or for a new source.

Usage:
    uv run python -m ingest.run --source dulichviet
    uv run python -m ingest.run --source dulichviet --limit 5 --skip-survey
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from shared.runtime import ensure_utf8_stdout, run_cli

from . import pipeline as pipeline_mod
from . import survey as survey_mod


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the full ingest chain for one source.")
    parser.add_argument("--source", default=None,
                        help="short name in configs/sources-mvp.csv (default: all sources)")
    parser.add_argument("--limit", type=int, default=0,
                        help="max tours through discover+batch (0 = all)")
    parser.add_argument("--skip-survey", action="store_true",
                        help="reuse the promoted profile instead of re-surveying")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    ensure_utf8_stdout()
    args = _parse_args(argv)
    if args.source:
        sources = [args.source]
    else:
        try:
            sources = survey_mod.list_sources()
        except ValueError as exc:
            print(f"Invalid source: {exc}", file=sys.stderr)
            return 2
        if not sources:
            print("No sources in configs/sources-mvp.csv.", file=sys.stderr)
            return 2
    worst = 0
    for source in sources:
        if len(sources) > 1:
            print(f"=== run: {source} ===", flush=True)
        code = _run_source(source, args.limit, args.skip_survey)
        if code != 0:
            print(f"run {source} stopped (exit {code})", file=sys.stderr)
            worst = worst or code
    if worst == 0:
        print("run COMPLETE", flush=True)
    return worst


def _run_source(source: str, limit: int, skip_survey: bool) -> int:
    limited = ["--limit", str(limit)] if limit > 0 else []
    steps: list[tuple[str, list[str]]] = []
    if not skip_survey:
        steps.append(("survey", ["--source", source, "--promote"]))
    steps.extend([
        ("discover", ["--discover", "--profile", source, *limited]),
        ("batch", ["--batch", "--profile", source, *limited]),
        ("migrate", ["--migrate"]),
        ("publish", ["--publish", "--profile", source]),
    ])
    runners = {"survey": survey_mod.main, "discover": pipeline_mod.main,
               "batch": pipeline_mod.main,
               "migrate": pipeline_mod.main, "publish": pipeline_mod.main}
    for name, step_argv in steps:
        print(f"=== run: {name} ===", flush=True)
        code = runners[name](step_argv)
        if code != 0:
            print(f"run stopped at {name} (exit {code})", file=sys.stderr)
            return code
    print("run COMPLETE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli(main))
