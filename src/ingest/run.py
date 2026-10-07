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
import io
import sys
from collections.abc import Sequence

from shared.runtime import run_cli

from . import pipeline as pipeline_mod
from . import survey as survey_mod


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the full ingest chain for one source.")
    parser.add_argument("--source", required=True, help="short name in configs/sources-mvp.csv")
    parser.add_argument("--limit", type=int, default=0,
                        help="max tours through discover+batch (0 = all)")
    parser.add_argument("--skip-survey", action="store_true",
                        help="reuse the promoted profile instead of re-surveying")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = _parse_args(argv)
    limit = ["--limit", str(args.limit)] if args.limit > 0 else []
    steps: list[tuple[str, list[str]]] = []
    if not args.skip_survey:
        steps.append(("survey", ["--source", args.source, "--promote"]))
    steps.extend([
        ("discover", ["--discover", "--profile", args.source, *limit]),
        ("batch", ["--batch", "--profile", args.source, *limit]),
        ("migrate", ["--migrate"]),
        ("publish", ["--publish", "--profile", args.source]),
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
