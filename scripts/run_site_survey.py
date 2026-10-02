"""Run a site-survey agent and save its output under artifacts/.

The operator runs this manually (it invokes the agent, takes minutes).
Nothing is executed at import time.

The agent must hand over a self-tested, generic crawl profile:
profile.yaml declares, per canonical field, WHERE the value lives
(source/path/context), how to normalize it and how to gate noise, so the
generic crawler needs no per-site code. selftest.md records the dev-set
PASS/FAIL the agent used before handover.

Usage:
    uv run --no-project python scripts/run_site_survey.py --source pys --origin https://pystravel.vn/
    uv run --no-project python scripts/run_site_survey.py --source xyz --origin https://example.test/ --timeout-min 30
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

MODEL = "opencode/muse-spark-1.3-contributor-free"
VARIANT = "xhigh"

AGENT_SPEC = """---
description: Bounded tour-source surveyor producing a self-tested crawl profile
mode: primary
permission:
  "*": allow
  "question": deny
---

You survey ONE public tour website and hand over a profile that a fixed,
generic crawler (< 100 lines) can run on ANY tour of that site to produce
the canonical field set with NO further coding and NO per-field guessing.

TARGET ORIGIN is given in the task message (not in this file).

HARD RULES (violating any fails the task):
- Public HTTP GET only, same origin. Respect robots.txt; never fetch a
  disallowed path. No login, no CAPTCHA/paywall bypass, no POST/PUT/DELETE,
  no credentials or cookies. Max 60 requests total, >=1s apart, <=2MB each.
- Never invent facts. Every claim needs a verbatim quote from a fetched page.
- Write all output files inside the working directory only.
- You may ONLY edit profile.yaml. You must never write or edit crawler code.
- NO NATURAL LANGUAGE OR CONDITIONAL PROSE IN profile.yaml. Every field rule
  must be a strictly machine-readable dictionary specifying exact coordinates.
  Writing prose instructions like "ends at next heading" or "if X then Y"
  will cause the runner to fail and is a hard rejection.

SPEED PRIORITY & RENDERING DECISION:
1. Static HTML + embedded JSON (JSON-LD, hydration blobs, sitemaps):
   Always start by inspecting static HTML. If static HTML contains sufficient data
   for canonical fields (like SSR sites), set `render: false` and `flows: [static]`.
2. Browser rendering (Playwright Chromium):
   If static HTML lacks critical decision fields (e.g. itinerary, inclusions,
   exclusions, departure_pattern) or contains empty placeholder shells due to
   client-side JavaScript / Next.js hydration:
   - YOU DECIDE to activate browser rendering: set `render: true` and `flows: [browser]`.
   - Use the provided `render_url.py` in your working directory to capture hydrated DOM:
       python render_url.py <tour_url> raw/tour-1.html
   - Inspect the hydrated HTML to locate the exact CSS / section / label coordinates.

CANONICAL FIELDS (the fixed target set; every field must be addressed):
hard  (compared by code): tour_name, departure_city, destinations, route,
                          transport, accommodation,
                          duration_days, duration_nights, price, currency,
                          price_type, departure_pattern
soft  (compared by LLM) : itinerary, inclusions, exclusions,
                          cancellation_policy
- destinations is a LIST of real destinations (from the site's own taxonomy,
  breadcrumb or structured-data location); Title Case (e.g. ["Mộc Châu", "Sơn La"]).
- route is the ordered list of all stops including transit, stripped of slogans.
- transport is one of: flight | bus | train | cruise | mixed.
- accommodation is standard category: 3_star | 4_star | 5_star | homestay | mixed.
- duration_days/duration_nights are integers parsed from text like
  "3 ngay 4 dem" or ISO-8601 "P3D".
- price_type is one of: fixed | from | contact.
- departure_dates belong to Offer, not Tour; when the site publishes no fixed
  dates, set departure_pattern (e.g. "hang tuan") and leave dates empty.
- A field the site genuinely does not publish is written with
  status: not_observed. Missing data is a valid result; guessing is failure.

MACHINE-READABLE PROFILE SCHEMA:
Each rule in `fields` MUST use one of these 4 source types:
1. json_ld:
     source: json_ld
     path: <dotted_path>          # e.g. "offers.price", "startLocation.name"
     entity: <entity_type>        # optional, e.g. "TouristTrip"
2. css:
     source: css
     selector: <css_selector>     # e.g. "h1.tour-title", "span.price"
     attr: <attr_name>            # optional, default "text", or "content", "href"
3. label_sibling:
     source: label_sibling
     label: <text_anchor>         # e.g. "Thời gian:", "Khởi hành từ:"
4. section:
     source: section
     start_label: <heading_text>  # e.g. "Lịch trình", "Giá tour bao gồm"
     stop_labels: [<heading_1>, <heading_2>] # headings where section terminates

FIELD CLEANING CODE (RECOMMENDED for exact target format & clean text):
  clean: "<python_expression>"   # e.g. "int(re.sub(r'\\D', '', str(val)))"
  Environment provides:
    - val: raw extracted value from source
    - modules: re, json, html
  Examples:
    - Clean Title Case list: "[s.strip().title() for s in re.split(r'[,;]', val) if s.strip()]"
    - Clean HTML tags/entities: "re.sub(r'<[^>]+>', '\\n', html.unescape(val)).strip()"
    - Normalize enum: "'flight' if 'bay' in str(val).lower() else ('bus' if 'xe' in str(val).lower() else 'mixed')"

Optional transform (legacy fallback):
  transform: int | regex | split | single_list

If a field is not present on the site, declare:
  status: not_observed

OUTPUT FILES (all five required, nothing else counts as done):
1. `profile.yaml` with EXACTLY these keys:
   origin, render (boolean: true if browser rendering is needed, false otherwise),
   flows (subset of [static, browser, api]), sitemaps (list),
   tour_url_patterns (list of path substrings identifying tour-detail URLs),
   fields (map canonical field -> rule object as specified above).
2. `evidence.md` -- the per-field evidence table.
3. `selftest.md` -- the per-field dev-set PASS/FAIL with the real JSONL output.
4. `raw/` -- saved raw bodies (robots.txt, sitemaps, tour-1.html, tour-2.html, tour-3.html).
5. `unknowns.md` -- fields/pages that could not be verified + why.

SELF-TEST LOOP (required before handover):
- You have `crawl_with_profile.py` provided in your working directory.
- Test your `profile.yaml` directly by running:
    python crawl_with_profile.py raw/tour-1.html raw/tour-2.html raw/tour-3.html --profile profile.yaml -o selftest.jsonl
- Inspect `selftest.jsonl` to ensure all 16 canonical fields match Target Canonical Formats in data-contract.md.
- If any field is empty, malformed, or has dirty HTML entities, adjust your clean expression or selectors in `profile.yaml` and re-run.
- Maximum 5 iterations.
- Paste the final `selftest.jsonl` content into `selftest.md`.
"""

EXPECTED = ["profile.yaml", "evidence.md", "selftest.md", "unknowns.md", "raw"]


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run a site-survey agent.")
    parser.add_argument("--source", required=True, help="short name, e.g. pys")
    parser.add_argument("--origin", required=True, help="https://example.test/")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--variant", default=VARIANT)
    parser.add_argument("--timeout-min", type=int, default=20)
    parser.add_argument("--format", choices=["default", "json"], default="default",
                        help="opencode output format (default: formatted readable output)")
    parser.add_argument("--output", type=Path, default=None,
                        help="default: artifacts/agent_surveys/<source>")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = _parse_args(argv)
    out_dir = args.output or Path("artifacts/agent_surveys") / args.source
    workdir = Path(tempfile.mkdtemp(prefix="site-survey-"))
    agent_dir = workdir / ".opencode" / "agents"
    agent_dir.mkdir(parents=True)
    (agent_dir / "site-surveyor.md").write_text(AGENT_SPEC, encoding="utf-8")

    runner_src = Path(__file__).parent / "crawl_with_profile.py"
    if runner_src.exists():
        shutil.copy2(runner_src, workdir / "crawl_with_profile.py")

    render_src = Path(__file__).parent / "render_url.py"
    if render_src.exists():
        shutil.copy2(render_src, workdir / "render_url.py")

    existing_raw = out_dir / "raw"
    if existing_raw.exists():
        shutil.copytree(existing_raw, workdir / "raw", dirs_exist_ok=True)

    task = (
        "Execute your agent instructions now: survey the tour website at "
        f"{args.origin} and produce profile.yaml, evidence.md, selftest.md, "
        "raw/, unknowns.md in the working directory. "
        "NOTE: If raw/ already contains robots.txt, sitemaps or tour-*.html, DO NOT re-fetch them; "
        "use the existing files in raw/ and only download what is missing. "
        "Before handover you MUST run the self-test loop over 3 "
        "different tours using crawl_with_profile.py, fix profile.yaml on any failure, "
        "and record the final result in selftest.md."
    )
    print(f"workdir={workdir}")
    print(f"target={args.origin} model={args.model} variant={args.variant}")
    started = time.perf_counter()
    exe = shutil.which("opencode") or shutil.which("opencode.cmd") or "opencode"
    try:
        subprocess.run(
            [exe, "run", "--model", args.model, "--variant", args.variant,
             "--agent", "site-surveyor", "--dir", str(workdir),
             "--format", args.format, task],
            timeout=args.timeout_min * 60, check=False,
        )
    except subprocess.TimeoutExpired:
        print(f"agent timed out after {args.timeout_min} min; collecting partial output",
              file=sys.stderr)
    elapsed = time.perf_counter() - started

    out_dir.mkdir(parents=True, exist_ok=True)
    missing = []
    for name in EXPECTED:
        src = workdir / name
        if not src.exists():
            missing.append(name)
            continue
        dst = out_dir / name
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
    print(f"elapsed={elapsed:.0f}s saved={out_dir}")
    if missing:
        print(f"MISSING (incomplete run): {missing}", file=sys.stderr)
        return 1
    print("COMPLETE: profile.yaml, evidence.md, unknowns.md, raw/ all present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
