"""Deterministic profile audit: score a profile on holdout URLs.

No LLM, no guessing, no network beyond the crawls themselves. The agent
claims genericity; this tool measures it: every holdout tour is crawled,
every extracted field is evidence-checked verbatim, and the profile passes
only if all gates hold. Exit 0 pass, 1 fail, 2 usage/config error.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from shared.runtime import run_cli

from .extract import load_profile, load_settings
from .pipeline import run_tour


@dataclass
class AuditResult:
    tours: int
    failed_tours: list[str]
    fields: dict[str, dict[str, int]]
    unobserved: list[str]
    evidence_rate: float
    failures: list[str]
    passed: bool = False


def _declared_absent(profile: dict) -> set[str]:
    """Fields whose top-level rule says the site never publishes them."""
    out = set()
    for name, rule in (profile.get("fields") or {}).items():
        if isinstance(rule, dict) and rule.get("status") == "not_observed":
            out.add(str(name))
    return out


def audit_urls(urls: list[str], profile: dict, settings: dict,
               out_dir: Path | None = None, min_evidence: float = 0.9) -> AuditResult:
    """Crawl each URL once (static only) and score field fill + evidence."""
    fields = profile.get("fields") or {}
    if not fields:
        return AuditResult(0, [], {}, [], 0.0,
                           ["profile has no fields: nothing to score"], False)
    work = Path(out_dir) if out_dir else Path(tempfile.mkdtemp(prefix="ingest-audit-"))
    work.mkdir(parents=True, exist_ok=True)
    static_profile = {**profile, "flows": ["static"]}
    # Evidence verdicts come from the crawl itself (computed against full
    # page context including script blobs); recomputing here against prose
    # alone would false-fail script-sourced fields. Audit independence is
    # from the agent's claims, and fill/thresholds are still checked here.
    filled: dict[str, int] = {name: 0 for name in fields}
    evidence_ok = 0
    evidence_total = 0
    failed_tours: list[str] = []
    for url in urls:
        try:
            row = run_tour(url, static_profile, settings, work)
        except Exception as exc:
            failed_tours.append(f"{url} ({type(exc).__name__})")
            continue
        detail_file = row.get("detail_file", "")
        try:
            detail = json.loads(Path(detail_file).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            failed_tours.append(f"{url} (unreadable detail file)")
            continue
        record = detail.get("record") or {}
        if detail.get("record_evidence") == "verified":
            evidence_ok += 1
        evidence_total += 1
        for name in fields:
            value = record.get(name)
            if value not in (None, "", [], {}):
                filled[name] += 1
    declared = _declared_absent(profile)
    unobserved = sorted(name for name in fields
                        if filled.get(name, 0) == 0 and name not in declared)
    per_field = {name: {"filled": filled.get(name, 0), "tours": len(urls)} for name in fields}
    failures: list[str] = []
    failures.extend(f"unreachable tour: {item}" for item in failed_tours)
    failures.extend(f"field never filled (broken selector or undeclared absence): {name}"
                    for name in unobserved)
    evidence_rate = (evidence_ok / evidence_total) if evidence_total else 0.0
    if evidence_total and evidence_rate < min_evidence:
        failures.append(f"evidence verified {evidence_ok}/{evidence_total} "
                        f"({evidence_rate:.2f}) below {min_evidence:.2f}")
    if not urls:
        failures.append("no holdout urls given")
    return AuditResult(len(urls), failed_tours, per_field, unobserved,
                       evidence_rate, failures, not failures)


def main(argv: list[str] | None = None) -> int:
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(prog="ingest-audit",
                                     description="Score a profile on holdout tour URLs.")
    parser.add_argument("--profile", "-p", required=True, help="profile name or YAML path")
    parser.add_argument("--urls", type=Path, required=True, help="file with one tour URL per line")
    parser.add_argument("--min-evidence", type=float, default=0.9,
                        help="minimum verified fraction (default 0.9)")
    parser.add_argument("--out-dir", type=Path, default=None, help="detail JSON directory")
    args = parser.parse_args(argv)
    try:
        settings = load_settings()
        candidate = Path(args.profile)
        if candidate.exists():
            import yaml

            data = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
            if not isinstance(data, dict) or not data.get("origin"):
                raise ValueError(f"not a profile YAML: {candidate}")
            profile = data
        else:
            profile = load_profile(args.profile)
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"Invalid config: {exc}", file=sys.stderr)
        return 2
    urls = [line.strip() for line in Path(args.urls).read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")]
    result = audit_urls(urls, profile, settings, args.out_dir, args.min_evidence)
    print(f"tours={result.tours} failed_tours={len(result.failed_tours)} "
          f"evidence_rate={result.evidence_rate:.2f}")
    for name in sorted(result.fields):
        stat = result.fields[name]
        print(f"  {name}: filled {stat['filled']}/{stat['tours']}")
    if result.unobserved:
        print("unobserved fields: " + ", ".join(result.unobserved))
    for failure in result.failures:
        print(f"FAIL: {failure}")
    if result.passed:
        print("AUDIT PASS")
        return 0
    print("AUDIT FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(run_cli(main))
