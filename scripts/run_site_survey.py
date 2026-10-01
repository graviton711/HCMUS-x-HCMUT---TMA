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
generic crawler can run on ANY tour of that site to produce the canonical
field set with NO further coding and NO per-field guessing.

TARGET ORIGIN is given in the task message (not in this file).

HARD RULES (violating any fails the task):
- Public HTTP GET only, same origin. Respect robots.txt; never fetch a
  disallowed path. No login, no CAPTCHA/paywall bypass, no POST/PUT/DELETE,
  no credentials or cookies. Max 60 requests total, >=1s apart, <=2MB each.
- Never invent facts. Every claim needs a verbatim quote from a fetched page.
- Write all output files inside the working directory only.
- You may ONLY edit profile.yaml. You must never write or edit crawler code,
  and you must never add site-specific logic outside the profile's declared
  rule types (JSON path, heading-adjacent text, label:value, date-window).

SPEED PRIORITY (in order, stop at the first sufficient layer):
1. Static HTML + embedded JSON (JSON-LD, hydration blobs, sitemaps).
2. Public JSON endpoints the site's own pages call (same rules as above).
3. Browser rendering ONLY if you prove layers 1-2 lack decision fields,
   with the missing field names listed as proof.

CANONICAL FIELDS (the fixed target set; every field must be addressed):
hard  (compared by code): tour_name, departure_city, destinations, route,
                          duration_days, duration_nights, price, currency,
                          price_type, departure_pattern
soft  (compared by LLM) : itinerary, inclusions, exclusions,
                          cancellation_policy
- destinations is a LIST of real destinations (from the site's own taxonomy,
  breadcrumb or structured-data location); never inferred from the tour name.
- route is the ordered list of all stops including transit.
- duration_days/duration_nights are integers parsed from text like
  "3 ngay 4 dem" or ISO-8601 "P3D".
- price_type is one of: fixed | from | contact.
- departure_dates belong to Offer, not Tour; when the site publishes no fixed
  dates, set departure_pattern (e.g. "hang tuan") and leave dates empty.
- A field the site genuinely does not publish is written with
  status "not_observed" and value null. Missing data is a valid result;
  guessing is failure. Never drop a canonical field.

MINIMUM EVIDENCE (thin output is rejected):
- Fetch: robots.txt, sitemap(s), homepage, and >=3 real tour-detail pages
  (not listings). Save raw bodies under ./raw/ (names: robots.txt,
  sitemap-*.xml, tour-1.html, ...).
- For EACH canonical field, record 2 INDEPENDENT evidences (different URLs or
  different source layers) OR mark it not_observed with the reason. Format:
  `field | value | evidence_url_1 + verbatim quote | evidence_url_2 +
  verbatim quote | layer (static-json/static-text/api/browser)`.

SELF-TEST LOOP (required before handover):
- STEP 0 — PROFILE MUST PARSE. Before any crawl test, load profile.yaml with a
  YAML parser (e.g. `python -c "import yaml; yaml.safe_load(open('profile.yaml'))"`).
  If it raises, the profile is broken; fix the syntax first. An unparseable
  profile is a hard FAIL no matter how good the rules look.
  Common YAML trap you MUST avoid: a plain scalar containing ": " (colon +
  space) anywhere, e.g. `normalize: split NGAY XX: A - B - C`. The parser reads
  that inner colon as a new mapping key. Wrap such values in quotes, or use a
  block scalar (|). The same applies to any value ending in ":" such as
  `label: Thoi gian:`. Quote anything containing ": ".
- STEP 1 — WRITE A VERIFIER. You MUST write your own throwaway script that
  loads profile.yaml, parses raw/tour-*.html, executes every json_ld rule
  (resolve the path) and every text rule (extract the section), and prints
  produced values per field per tour. Keep it inside the working directory.
  Text-rule execution counts: extract the label section and show what came out.
- STEP 2 — EXECUTE, DO NOT EYEBALL. Run the verifier and read its real output.
  Reading a value on the page with your eyes is NOT verification; a field
  passes only if executing the rule returns the value. If the verifier raises
  or returns null where the page clearly has the value, the rule is wrong:
  fix it and re-run. Maximum 5 iterations.
- Pick 3 tour URLs from DIFFERENT tours as your dev set, and also include one
  variant if the site has one (e.g. a 1-day tour, a contact-only price).
- A json_ld path resolves from the page's OWNING entity (the
  Product/TouristTrip root), not from a nested node named in the gate — the
  gate describes a confirmation condition, not the node to resolve from.
- Never fix a failure by hardcoding a value for a specific tour. The profile
  must be generic to the whole site.
- If a field still fails after 5 iterations, list it in unknowns.md as a
  profile-schema limitation instead of padding a guess.
- selftest.md MUST contain the ACTUAL verifier stdout pasted in (per tour,
  per field, produced values and PASS/FAIL), not a retold table. It must also
  state that `yaml.safe_load` succeeded on the final profile.yaml. A selftest
  with no pasted program output is treated as not run.

OUTPUT FILES (all five required, nothing else counts as done):
1. `profile.yaml` with EXACTLY these keys:
   origin, flows (subset of [static, browser, api]), sitemaps (list),
   tour_url_patterns (list of path substrings identifying tour-detail URLs),
   fields (map canonical field -> rule object, see below),
   schedule (how departure dates/prices are obtained + evidence),
   notes_keys (observed keys holding inclusions/exclusions/policy or empty),
   junk (selectors/patterns to drop).
   Each rule object in `fields` MUST declare WHERE the value lives so the
   generic crawler never has to guess:
     source: json_ld | hydration | text
     path:   dotted JSON path or source key when source is json_ld/hydration
     context: for text, the label/heading the value sits under, and whether
              the value extends to the next heading
     normalize: declared transform (e.g. currency, thousand-sep, duration)
     gate: any condition that filters noise (e.g. date-only-near-schedule)
   Example:
     fields:
       price:
         source: hydration
         path: offers.price
         normalize: integer
       inclusions:
         source: text
         context: {label: "Gia tour bao gom", extent: next_heading}
   A field the site lacks is declared as: {status: not_observed}.
2. `evidence.md` -- the per-field evidence table above.
3. `selftest.md` -- the per-field dev-set PASS/FAIL with change log.
4. `raw/` -- saved raw bodies.
5. `unknowns.md` -- fields/pages that could not be verified + why.

QUALITY BAR: another engineer must crawl any tour on this site using only
profile.yaml, without re-researching and without writing code. The profile
must be complete enough that no field rule is guessed at crawl time. If you
cannot reach that bar, say so in unknowns.md instead of padding guesses.
"""

EXPECTED = ["profile.yaml", "evidence.md", "selftest.md", "unknowns.md", "raw"]


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run a site-survey agent.")
    parser.add_argument("--source", required=True, help="short name, e.g. pys")
    parser.add_argument("--origin", required=True, help="https://example.test/")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--variant", default=VARIANT)
    parser.add_argument("--timeout-min", type=int, default=20)
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

    task = (
        "Execute your agent instructions now: survey the tour website at "
        f"{args.origin} and produce profile.yaml, evidence.md, selftest.md, "
        "raw/, unknowns.md in the working directory. Start with robots.txt "
        "and sitemaps. Before handover you MUST run the self-test loop over 3 "
        "different tours, fix profile.yaml on any failure, and record the "
        "final result in selftest.md."
    )
    print(f"workdir={workdir}")
    print(f"target={args.origin} model={args.model} variant={args.variant}")
    started = time.perf_counter()
    exe = shutil.which("opencode") or shutil.which("opencode.cmd") or "opencode"
    try:
        subprocess.run(
            [exe, "run", "--model", args.model, "--variant", args.variant,
             "--agent", "site-surveyor", "--dir", str(workdir),
             "--format", "json", task],
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
