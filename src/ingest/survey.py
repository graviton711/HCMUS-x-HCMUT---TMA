"""Run a site-survey agent and save its output under artifacts/.

The operator runs this manually (it invokes the agent, takes minutes).
Nothing is executed at import time.

The agent must hand over a self-tested, generic crawl profile:
profile.yaml declares, per canonical field, WHERE the value lives
(source/path/context), how to normalize it and how to gate noise, so the
generic crawler needs no per-site code. selftest.md records the dev-set
PASS/FAIL the agent used before handover.

Usage:
    uv run python -m ingest.survey --source pys --origin https://pystravel.vn/
    uv run python -m ingest.survey --source xyz --origin https://example.test/ --timeout-min 30
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

MODEL = "opencode/muse-spark-1.3-contributor-free"
VARIANT = "xhigh"

DEFAULT_AGENT_SPEC = Path(__file__).resolve().parents[2] / "configs" / "agents" / "site-surveyor.yaml"
DEFAULT_CRITIC_SPEC = Path(__file__).resolve().parents[2] / "configs" / "agents" / "profile-critic.yaml"


def load_agent_spec(path: str | Path | None = None) -> str:
    """Agent prompt + frontmatter, rebuilt byte-identical from YAML."""
    import yaml

    data = yaml.safe_load(Path(path or DEFAULT_AGENT_SPEC).read_text(encoding="utf-8"))
    head = ["---", f"description: {data['description']}", f"mode: {data['mode']}", "permission:"]
    for key, val in data["permission"].items():
        head.append(f'  "{key}": {val}')
    return "\n".join(head) + "\n---\n" + data["prompt"]


AGENT_SPEC = load_agent_spec()


def load_agent_task(origin: str, path: str | Path | None = None) -> str:
    """Handover task rendered from YAML with the target origin filled in."""
    import yaml

    data = yaml.safe_load(Path(path or DEFAULT_AGENT_SPEC).read_text(encoding="utf-8"))
    return data["handover_task"].format(origin=origin)


def load_task(path: str | Path, **kwargs: object) -> str:
    """Render any agent task template (handover/fix/critic) with named fields."""
    import yaml

    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return data["handover_task"].format(**kwargs)


def load_critic_task(origin: str, profile_file: Path, holdout_file: Path,
                     holdout_dir: Path, round_no: int, budget: int,
                     path: str | Path | None = None) -> str:
    """Critic handover with profile + blind holdout locations filled in."""
    return load_task(path or DEFAULT_CRITIC_SPEC, origin=origin,
                     profile_file=str(profile_file), holdout_file=str(holdout_file),
                     holdout_dir=str(holdout_dir), round=round_no, budget=budget)


def load_fix_task(round_no: int, path: str | Path | None = None) -> str:
    """Surveyor fix-round task pointing at critic_report.md in its workdir."""
    import yaml

    data = yaml.safe_load(Path(path or DEFAULT_AGENT_SPEC).read_text(encoding="utf-8"))
    return data["fix_task"].format(round=round_no)


EXPECTED = ["profile.yaml", "evidence.md", "selftest.md", "unknowns.md", "raw",
            "dev_urls.txt", "candidate_pool.json", "verify.json"]

USER_AGENT = "MLAITourSourceAuditor/0.1"
PREFETCH_TIMEOUT_S = 15
MAX_BODY_BYTES = 2_000_000


def _robots_sitemaps(text: str) -> list[str]:
    return [line.split(":", 1)[1].strip() for line in text.splitlines()
            if line.lower().startswith("sitemap:")]


def _save_url(url: str, raw_dir: Path, user_agent: str = USER_AGENT,
              timeout_s: float = PREFETCH_TIMEOUT_S,
              max_bytes: int = MAX_BODY_BYTES) -> str | None:
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", urlsplit(url).path.strip("/")) or "robots.txt"
    dest = raw_dir / name
    if dest.exists():
        return None
    try:
        req = Request(url, headers={"User-Agent": user_agent})
        with urlopen(req, timeout=timeout_s) as resp:
            body = resp.read(max_bytes)
        dest.write_bytes(body)
        return name
    except Exception:
        return None


def _agent_env() -> dict[str, str] | None:
    """PATH with the project .venv first, so the agent's `python` is the venv
    (bs4/yaml/playwright ready) and it never pip-installs into system Python."""
    root = Path(__file__).resolve().parents[1]
    for bin_dir, exe in ((".venv/Scripts", "python.exe"), (".venv/bin", "python")):
        if (root / bin_dir / exe).exists():
            env = dict(os.environ)
            env["PATH"] = str(root / bin_dir) + os.pathsep + env.get("PATH", "")
            env.setdefault("VIRTUAL_ENV", str(root / ".venv"))
            src = str(root / "src")
            env["PYTHONPATH"] = src + os.pathsep + env.get("PYTHONPATH", "") if env.get("PYTHONPATH") else src
            return env
    return None


def prefetch(origin: str, raw_dir: Path, settings: dict | None = None) -> list[str]:
    """Best-effort: save robots.txt and its declared sitemaps into raw/.

    Mechanical work the agent would otherwise burn HTTP requests and LLM
    turns on; any failure is ignored (the agent still handles the source).
    """
    survey_cfg = (settings or {}).get("survey", {})
    fetch_cfg = (settings or {}).get("fetch", {})
    user_agent = str(fetch_cfg.get("user_agent", USER_AGENT))
    timeout_s = float(survey_cfg.get("prefetch_timeout_s", PREFETCH_TIMEOUT_S))
    max_bytes = int(survey_cfg.get("max_body_bytes", MAX_BODY_BYTES))
    def save(url: str) -> str | None:
        return _save_url(url, raw_dir, user_agent, timeout_s, max_bytes)

    base = origin.rstrip("/")
    robots = save(f"{base}/robots.txt")
    if robots:
        sitemaps = _robots_sitemaps(
            (raw_dir / robots).read_text(encoding="utf-8", errors="replace"))
    else:
        sitemaps = []
    sitemaps.append(f"{base}/sitemap.xml")
    with ThreadPoolExecutor(max_workers=4) as pool:
        names = pool.map(save, dict.fromkeys(sitemaps))
        saved = [robots] if robots else []
        saved.extend(name for name in names if name)
    return saved


SOURCES_CSV = Path(__file__).resolve().parents[2] / "configs" / "sources-mvp.csv"


def resolve_origin(source: str, csv_path: str | Path | None = None) -> str:
    """Look up the origin URL for a source in the frozen MVP scope list."""
    import csv

    target = Path(csv_path or SOURCES_CSV)
    if not target.exists():
        raise ValueError(f"sources list not found: {target}")
    with target.open(encoding="utf-8") as handle:
        hits = [row["url"].strip() for row in csv.DictReader(handle) if row.get("source") == source]
    if len(hits) != 1:
        raise ValueError(f"source {source!r} must match exactly one row in {target} (found {len(hits)})")
    return hits[0]


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a site-survey agent.")
    parser.add_argument("--source", required=True, help="short name, e.g. pys")
    parser.add_argument("--origin", default=None,
                        help="https://example.test/ (default: looked up from configs/sources-mvp.csv)")
    parser.add_argument("--model", default=None,
                        help="default: survey.model in settings")
    parser.add_argument("--variant", default=None,
                        help="default: survey.variant in settings")
    parser.add_argument("--timeout-min", type=int, default=None,
                        help="default: survey.timeout_min in settings")
    parser.add_argument("--format", choices=["default", "json"], default="default",
                        help="opencode output format (default: formatted readable output)")
    parser.add_argument("--output", type=Path, default=None,
                        help="default: artifacts/agent_surveys/<source>")
    parser.add_argument("--promote", action="store_true",
                        help="on COMPLETE, copy profile.yaml to configs/profiles/<source>.yaml")
    parser.add_argument("--critic-rounds", default="auto",
                        help="'auto' (coverage clean -> 1 confirmation round, "
                             "gaps -> 2 rounds), a number, or 0 to skip")
    parser.add_argument("--fix-timeout-min", type=int, default=None,
                        help="fix-round budget in minutes (default: min(8, timeout))")
    parser.add_argument("--holdout-n", type=int, default=3,
                        help="blind holdout tours for gates and critic")
    parser.add_argument("--seed", type=int, default=7,
                        help="deterministic seed for the holdout split")
    return parser.parse_args(argv)


DEFAULT_PROFILES_DIR = Path(__file__).resolve().parents[2] / "configs" / "profiles"


def promote_profile(out_dir: Path, source: str,
                    profiles_dir: Path | None = None) -> Path:
    """Copy a completed survey profile into the versioned configs tree."""
    src = Path(out_dir) / "profile.yaml"
    if not src.exists():
        raise ValueError(f"no profile.yaml in {out_dir}")
    dest_dir = Path(profiles_dir) if profiles_dir is not None else DEFAULT_PROFILES_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{source}.yaml"
    text = src.read_text(encoding="utf-8")
    header = "# yaml-language-server: $schema=../profile.schema.json\n"
    if not text.startswith("# yaml-language-server:"):
        text = header + text
    dest.write_text(text, encoding="utf-8")
    return dest


REQUIRED_PROFILE_KEYS = ["origin", "render", "flows", "sitemaps",
                         "tour_url_patterns", "discovery", "fields"]

PASS_FLOOR = 0.9


def check_profile_keys(data: dict) -> list[str]:
    """Missing top-level profile keys (empty means machine-readable enough to gate)."""
    return [key for key in REQUIRED_PROFILE_KEYS if key not in data]


def split_holdout(pool: list[dict], holdout_n: int, seed: int,
                  dev_urls: Sequence[str] = ()) -> tuple[list[str], list[str]]:
    """Stratified blind split: cover every cluster, deterministic per seed.

    Returns (holdout_urls, dev_pool_urls). Dev tours are never in holdout.
    """
    import random

    dev = {u.strip() for u in dev_urls if u.strip()}
    candidates: dict[str, list[str]] = {}
    for entry in pool:
        url = str(entry.get("url", "")).strip()
        if not url or url in dev:
            continue
        bucket = candidates.setdefault(str(entry.get("cluster", "?")), [])
        if url not in bucket:
            bucket.append(url)
    rng = random.Random(seed)
    holdout: list[str] = []
    clusters = sorted(candidates)
    rng.shuffle(clusters)
    for cluster in clusters:
        if len(holdout) >= holdout_n:
            break
        urls = [u for u in candidates[cluster] if u not in holdout]
        if urls:
            holdout.append(rng.choice(urls))
    rest = [u for urls in candidates.values() for u in urls if u not in holdout]
    rng.shuffle(rest)
    holdout.extend(rest[:max(0, holdout_n - len(holdout))])
    return holdout, [u for urls in candidates.values() for u in urls]


def coverage_gaps(pool: list[dict], holdout: Sequence[str]) -> list[str]:
    """Clusters with >=2 pool members but zero holdout coverage."""
    from collections import Counter

    counts: Counter = Counter()
    covered: set[str] = set()
    held = set(holdout)
    for entry in pool:
        cluster = str(entry.get("cluster", "?"))
        counts[cluster] += 1
        if str(entry.get("url", "")).strip() in held:
            covered.add(cluster)
    return sorted(c for c, n in counts.items() if n >= 2 and c not in covered)


def pass_threshold(dev_rate: float, margin: float, floor: float = PASS_FLOOR) -> float:
    """Holdout bar from the dev-set rate minus the agent-proposed margin."""
    return max(dev_rate - max(0.0, margin), floor)


def hash_file(path: Path) -> str:
    import hashlib

    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]


SECTION_FIELDS = ["offers", "cancellation_policy", "surcharges", "child_policy"]

ADVERSARIAL_INPUTS = ["", "   ", "<div><p></p></div>", "Liên hệ", "0",
                      "N/A", "\\u0000test"]


def property_test_cleans(profile: dict) -> list[str]:
    """Every clean must be total: run each against hostile inputs, fail on raise."""
    from .extract import apply_clean

    failures = []
    for field, rule in (profile.get("fields") or {}).items():
        code = rule.get("clean") if isinstance(rule, dict) else None
        if not code:
            continue
        for bad in ADVERSARIAL_INPUTS:
            try:
                apply_clean({"clean": code}, bad)
            except Exception as exc:
                failures.append(f"{field} raises on {bad!r} ({type(exc).__name__})")
                break
    return failures


def coverage_check(dev_rows: list[dict], dev_count: int, verify: dict) -> list[str]:
    """Machine-check the agent-reported coverage matrix against dev output.

    Clusters come from the agent (spot-checked by the critic); section
    presence is recomputed here from dev rows, so a one-sided section
    without a declared-unfillable note fails without any agent input.
    """
    gaps = []
    if not 10 <= dev_count <= 15:
        gaps.append(f"dev set has {dev_count} tours, need 10-15")
    coverage = verify.get("coverage", {}) if isinstance(verify, dict) else {}
    clusters = coverage.get("clusters", {}) if isinstance(coverage, dict) else {}
    if not clusters:
        gaps.append("verify.json declares no cluster coverage")
    elif sum(int(v or 0) for v in clusters.values()) != dev_count:
        gaps.append("cluster counts do not add up to dev tour count")
    else:
        gaps.extend(f"cluster {name} has no dev tour"
                    for name, count in clusters.items() if not int(count or 0))
    matrix = coverage.get("section_matrix", {}) if isinstance(coverage, dict) else {}
    for field in SECTION_FIELDS:
        present = sum(1 for row in dev_rows
                      if row.get(field) not in (None, "", [], {}))
        absent = len(dev_rows) - present
        claimed = matrix.get(field, {}) if isinstance(matrix, dict) else {}
        if present and not absent and not claimed.get("unfillable"):
            gaps.append(f"{field} present in all dev tours (no absent case)")
        if absent and not present and not claimed.get("unfillable"):
            gaps.append(f"{field} absent in all dev tours (no present case)")
    return gaps


def stamp_metadata(path: Path, sample_tours: Sequence[str]) -> dict:
    """Add version/surveyed_at/sample_tours provenance to a profile file."""
    import yaml

    from shared import now_vn_iso

    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    data["version"] = int(data.get("version", 0)) + 1
    data["surveyed_at"] = now_vn_iso()
    data["sample_tours"] = [str(u) for u in sample_tours]
    with Path(path).open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False, width=4096)
    return {"version": data["version"], "surveyed_at": data["surveyed_at"],
            "sample_tours": len(data["sample_tours"])}


def run_agent(agent: str, workdir: Path, task: str, model: str, variant: str,
              timeout_min: int, fmt: str = "default") -> int | None:
    """One opencode agent invocation; None on timeout."""
    exe = shutil.which("opencode") or shutil.which("opencode.cmd") or "opencode"
    try:
        completed = subprocess.run(
            [exe, "run", "--model", model, "--variant", variant,
             "--agent", agent, "--dir", str(workdir),
             "--format", fmt, task],
            timeout=timeout_min * 60, check=False, env=_agent_env(),
        )
        return completed.returncode
    except subprocess.TimeoutExpired:
        print(f"agent {agent} timed out after {timeout_min} min; collecting partial output",
              file=sys.stderr)
        return None


def collect_outputs(workdir: Path, out_dir: Path,
                    expected: Sequence[str] = EXPECTED) -> list[str]:
    """Copy agent handover files to the evidence dir; returns missing names."""
    missing = []
    for name in expected:
        src = workdir / name
        if not src.exists():
            missing.append(name)
            continue
        dst = out_dir / name
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
    return missing


def read_url_list(path: Path) -> list[str]:
    """One URL per line, ignoring blanks and # comments."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return []
    return [line.strip() for line in text.splitlines()
            if line.strip() and not line.strip().startswith("#")]


def sample_sitemap_holdout(profile: dict, dev_urls: Sequence[str], n: int,
                           settings: dict) -> list[str]:
    """Independent holdout sample from sitemaps (surveyor never sees the pick).

    Best-effort: any failure yields fewer (or zero) URLs and the caller falls
    back to the agent-proposed pool.
    """
    try:
        from .fetch import make_fetcher
        from .pipeline import sitemap_urls

        dev = set(dev_urls)
        urls = sitemap_urls(make_fetcher(settings), profile.get("sitemaps", []),
                            profile.get("tour_url_patterns", []))
        fresh = [u for u in urls if u not in dev]
        stride = max(1, len(fresh) // max(1, n))
        return fresh[::stride][:n]
    except Exception as exc:
        print(f"sitemap holdout sampling failed ({type(exc).__name__}); using pool only",
              file=sys.stderr)
        return []


def fetch_holdout(urls: Sequence[str], holdout_raw: Path, settings: dict) -> list[str]:
    """Wrapper-fetched holdout HTML (mechanical; keeps the surveyor blind)."""
    fetch_cfg = (settings or {}).get("fetch", {})
    survey_cfg = (settings or {}).get("survey", {})
    user_agent = str(fetch_cfg.get("user_agent", USER_AGENT))
    timeout_s = float(survey_cfg.get("prefetch_timeout_s", PREFETCH_TIMEOUT_S))
    max_bytes = int(survey_cfg.get("max_body_bytes", MAX_BODY_BYTES))
    holdout_raw.mkdir(parents=True, exist_ok=True)
    saved = []
    for index, url in enumerate(urls, 1):
        dest = holdout_raw / f"holdout-{index}.html"
        if dest.exists():
            dest.unlink()
        got = _save_url(url, holdout_raw, user_agent, timeout_s, max_bytes)
        if got is None:
            continue
        src = holdout_raw / got
        if src != dest:
            shutil.move(str(src), str(dest))
        saved.append(dest.name)
    return saved


def static_gates(profile_path: Path, dev_htmls: Sequence[Path],
                 holdout_htmls: Sequence[Path], dev_urls: Sequence[str],
                 verify: dict, gates_dir: Path) -> dict:
    """Cheap local gates: keys, extract, clean property tests, coverage matrix."""
    import yaml

    from .extract import main as extract_main

    report: dict = {"failures": []}
    try:
        data = yaml.safe_load(Path(profile_path).read_text(encoding="utf-8")) or {}
    except OSError as exc:
        return {"ok": False, "failures": [f"unreadable profile: {exc}"],
                "dev_rows": []}
    missing = check_profile_keys(data)
    if missing:
        return {"ok": False,
                "failures": [f"profile missing keys: {missing}"], "dev_rows": []}
    gates_dir.mkdir(parents=True, exist_ok=True)
    report["extract_dev"] = extract_main([*[str(p) for p in dev_htmls], "--profile",
                                          str(profile_path), "-o",
                                          str(gates_dir / "dev.jsonl")])
    report["extract_holdout"] = extract_main([*[str(p) for p in holdout_htmls],
                                              "--profile", str(profile_path), "-o",
                                              str(gates_dir / "holdout.jsonl")])
    if report["extract_dev"] != 0:
        report["failures"].append("extract failed on dev set")
    if report["extract_holdout"] != 0:
        report["failures"].append("extract failed on holdout set")
    dev_rows = []
    try:
        with (gates_dir / "dev.jsonl").open(encoding="utf-8") as handle:
            dev_rows = [json.loads(line) for line in handle if line.strip()]
    except (OSError, ValueError) as exc:
        report["failures"].append(f"unreadable dev.jsonl: {exc}")
    report["dev_rows"] = dev_rows
    prop = property_test_cleans(data)
    if prop:
        report["failures"].extend(f"clean not total: {item}" for item in prop)
    report["coverage_gaps"] = coverage_check(dev_rows, len(list(dev_urls)), verify)
    report["failures"].extend(f"coverage gap: {gap}" for gap in report["coverage_gaps"])
    report["ok"] = not report["failures"]
    return report


def audit_gates(profile_path: Path, dev_urls: Sequence[str],
                holdout_urls: Sequence[str], settings: dict,
                gates_dir: Path, margin: float, floor: float,
                dev_cache: dict | None = None) -> dict:
    """Network gates: dev audit (cached by profile hash) sets the holdout bar."""
    import yaml

    from .audit import audit_urls
    from .fetch import make_fetcher

    report: dict = {"failures": []}
    try:
        data = yaml.safe_load(Path(profile_path).read_text(encoding="utf-8")) or {}
    except OSError as exc:
        return {"ok": False, "failures": [f"unreadable profile: {exc}"]}
    key = {"profile": hash_file(profile_path), "dev": hash_file_content(dev_urls)}
    if dev_cache and dev_cache.get("key") == key:
        dev_rate = float(dev_cache.get("dev_rate", 0.0))
        report["dev_cached"] = True
    else:
        dev_result = audit_urls(list(dev_urls), data, settings,
                                gates_dir / "audit_dev", 0.0)
        dev_rate = dev_result.evidence_rate
        report["dev_cached"] = False
    report["dev_rate"] = dev_rate
    threshold = pass_threshold(dev_rate, margin, floor)
    report["threshold"] = threshold
    hold_result = audit_urls(list(holdout_urls), data, settings,
                             gates_dir / "audit_holdout", threshold)
    report["holdout_rate"] = hold_result.evidence_rate
    report["holdout_failures"] = hold_result.failures
    entry = (data.get("discovery") or {}).get("entry", "")
    if entry:
        fetched = make_fetcher(settings).fetch(entry)
        report["discovery_entry_ok"] = fetched.status_code == 200 and not fetched.error
        if not report["discovery_entry_ok"]:
            report["failures"].append(f"discovery entry unreachable: {entry}")
    else:
        report["discovery_entry_ok"] = True
    if not hold_result.passed:
        report["failures"].extend(hold_result.failures)
    report["dev_cache_key"] = key
    report["ok"] = not report["failures"]
    return report


def resolve_rounds(value: object, coverage_gaps: Sequence[str]) -> int:
    """Adaptive rigor: clean coverage earns one confirmation round, gaps earn two."""
    if isinstance(value, str) and value == "auto":
        return 1 if not coverage_gaps else 2
    try:
        return max(0, int(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 1


def hash_file_content(items: Sequence[str]) -> str:
    import hashlib

    return hashlib.sha256("\n".join(items).encode("utf-8")).hexdigest()[:16]


def check_critic_report(report_path: Path, holdout: Sequence[str]) -> dict:
    """Mechanical completeness: every holdout URL sectioned, verdict explicit."""
    try:
        text = Path(report_path).read_text(encoding="utf-8")
    except OSError:
        return {"complete": False, "has_findings": False, "missing": list(holdout)}
    missing = [u for u in holdout if u not in text]
    has_findings = "FAIL" in text
    zero_claim = any(s in text for s in ("ZERO", "zero failures", "no failures",
                                        "NO FAIL", "0 failures"))
    return {"complete": not missing and (has_findings or zero_claim),
            "has_findings": has_findings, "missing": missing}


def write_gates_md(out_dir: Path, report: dict) -> Path:
    """Human-readable gate record beside the machine artifacts."""
    lines = ["# Survey gates", "",
             f"- machine gates: {'PASS' if report.get('ok') else 'FAIL'}",
             f"- dev evidence rate: {report.get('dev_rate', 0.0):.2f}",
             f"- holdout evidence rate: {report.get('holdout_rate', 0.0):.2f} "
             f"(bar {report.get('threshold', 0.0):.2f})",
             f"- discovery entry reachable: {report.get('discovery_entry_ok')}",
             f"- critic rounds: {report.get('critic_rounds', 0)}, "
             f"findings: {report.get('critic_findings', 0)}"]
    for failure in report.get("failures", []):
        lines.append(f"- FAIL: {failure}")
    for note in report.get("notes", []):
        lines.append(f"- note: {note}")
    dest = out_dir / "gates.md"
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dest


def main(argv: Sequence[str] | None = None) -> int:
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = _parse_args(argv)
    try:
        origin = args.origin or resolve_origin(args.source)
    except ValueError as exc:
        print(f"Invalid source: {exc}", file=sys.stderr)
        return 2
    try:
        from .extract import load_settings

        settings = load_settings()
    except (ValueError, RuntimeError, OSError):
        settings = {}
    survey_cfg = settings.get("survey", {})
    model = args.model or str(survey_cfg.get("model", MODEL))
    variant = args.variant or str(survey_cfg.get("variant", VARIANT))
    timeout_min = (args.timeout_min if args.timeout_min is not None
                   else int(survey_cfg.get("timeout_min", 20)))
    out_dir = args.output or Path("artifacts/agent_surveys") / args.source
    out_dir.mkdir(parents=True, exist_ok=True)
    workdir = out_dir / "_work"
    agent_dir = workdir / ".opencode" / "agents"
    agent_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = workdir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "site-surveyor.md").write_text(AGENT_SPEC, encoding="utf-8")

    render_src = Path(__file__).parent / "render.py"
    if render_src.exists():
        shutil.copy2(render_src, workdir / "render_url.py")

    legacy_raw = out_dir / "raw"
    if legacy_raw.exists():
        shutil.copytree(legacy_raw, raw_dir, dirs_exist_ok=True)

    started = time.perf_counter()
    prefetched = prefetch(origin, raw_dir, settings)
    print(f"prefetch={prefetched or 'nothing'} elapsed={time.perf_counter() - started:.1f}s",
          flush=True)

    task = load_agent_task(origin)
    print(f"workdir={workdir}", flush=True)
    print(f"target={origin} model={model} variant={variant}", flush=True)
    returncode = run_agent("site-surveyor", workdir, task, model, variant,
                           timeout_min, args.format)
    agent_elapsed = time.perf_counter() - started

    missing = collect_outputs(workdir, out_dir)
    print(f"agent_elapsed={agent_elapsed:.0f}s total={time.perf_counter() - started:.0f}s "
          f"opencode_exit={returncode} saved={out_dir}", flush=True)
    if missing:
        print(f"MISSING (incomplete run): {missing}", file=sys.stderr)
        return 1

    gate_report: dict = {"critic_rounds": 0, "critic_findings": 0, "notes": []}
    try:
        verify = json.loads((out_dir / "verify.json").read_text(encoding="utf-8"))
        margin = float(verify.get("margin", 0.05))
        if not isinstance(verify, dict):
            verify = {}
    except (OSError, ValueError, TypeError, AttributeError):
        verify = {}
        margin = 0.05
        gate_report["notes"].append("verify.json unreadable; margin defaulted to 0.05")
    dev_urls = read_url_list(out_dir / "dev_urls.txt")
    try:
        pool = json.loads((out_dir / "candidate_pool.json").read_text(encoding="utf-8"))
        pool = pool if isinstance(pool, list) else []
    except (OSError, ValueError):
        pool = []
    holdout, _ = split_holdout(pool, args.holdout_n, args.seed, dev_urls)
    if len(holdout) < args.holdout_n:
        try:
            import yaml as _yaml

            profile_data = _yaml.safe_load((out_dir / "profile.yaml").read_text(encoding="utf-8")) or {}
        except OSError:
            profile_data = {}
        fill = sample_sitemap_holdout(profile_data, dev_urls,
                                      args.holdout_n - len(holdout), settings)
        holdout.extend(u for u in fill if u not in holdout)
    canary = dev_urls[0] if dev_urls and dev_urls[0] not in holdout else ""
    if canary:
        holdout.append(canary)
        gate_report["notes"].append("canary (seen dev tour) injected into holdout")
    gaps = coverage_gaps(pool, holdout)
    if gaps:
        gate_report["notes"].append(f"holdout misses clusters: {gaps}")
    holdout_raw = out_dir / "holdout_raw"
    fetched = fetch_holdout(holdout, holdout_raw, settings)
    if not fetched:
        print("GATES FAIL: no holdout page fetchable", file=sys.stderr)
        return 1
    dev_htmls = sorted(raw_dir.glob("tour-*.html"))
    holdout_htmls = [holdout_raw / name for name in fetched]
    profile_path = out_dir / "profile.yaml"
    floor = float(settings.get("audit", {}).get("min_evidence", PASS_FLOOR))
    fix_timeout = (args.fix_timeout_min if args.fix_timeout_min is not None
                   else min(8, timeout_min))
    gates_dir = out_dir / "gates_work"
    cache_file = gates_dir / ".dev_cache.json"

    def run_machine() -> dict:
        static = static_gates(profile_path, dev_htmls, holdout_htmls, dev_urls,
                              verify, gates_dir)
        merged: dict = {"failures": list(static.get("failures", [])),
                        "notes": [],
                        "extract_dev": static.get("extract_dev"),
                        "extract_holdout": static.get("extract_holdout"),
                        "coverage_gaps": static.get("coverage_gaps", [])}
        if not static.get("ok"):
            merged["ok"] = False
            return merged
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            cached = {}
        audit = audit_gates(profile_path, dev_urls, holdout, settings,
                            gates_dir, margin, floor,
                            cached if isinstance(cached, dict) else None)
        merged.update({k: v for k, v in audit.items() if k != "failures"})
        merged["failures"].extend(audit.get("failures", []))
        try:
            cache_file.write_text(json.dumps({"key": audit.get("dev_cache_key"),
                                              "dev_rate": audit.get("dev_rate", 0.0)}),
                                  encoding="utf-8")
        except OSError:
            pass
        merged["ok"] = not merged["failures"]
        return merged

    gates = run_machine()
    gate_report.update({k: v for k, v in gates.items() if k != "failures"})
    gate_report["failures"] = list(gates.get("failures", []))

    rounds = resolve_rounds(args.critic_rounds, gate_report.get("coverage_gaps", []))
    for round_no in range(1, rounds + 1):
        round_dir = out_dir / "_critic" / f"r{round_no}"
        round_dir.mkdir(parents=True, exist_ok=True)
        c_agent_dir = round_dir / ".opencode" / "agents"
        c_agent_dir.mkdir(parents=True, exist_ok=True)
        (c_agent_dir / "profile-critic.md").write_text(
            load_agent_spec(DEFAULT_CRITIC_SPEC), encoding="utf-8")
        shutil.copy2(profile_path, round_dir / "profile.yaml")
        (round_dir / "holdout.txt").write_text("\n".join(holdout) + "\n", encoding="utf-8")
        shutil.copytree(holdout_raw, round_dir / "holdout_raw", dirs_exist_ok=True)
        critic_task = load_critic_task(origin, round_dir / "profile.yaml",
                                       round_dir / "holdout.txt",
                                       round_dir / "holdout_raw", round_no, budget=20)
        run_agent("profile-critic", round_dir, critic_task, model, variant,
                  timeout_min, args.format)
        report_path = round_dir / "critic_report.md"
        check = check_critic_report(report_path, holdout)
        if report_path.exists():
            shutil.copy2(report_path, out_dir / f"critic_report_r{round_no}.md")
        gate_report["critic_rounds"] = round_no
        if not check["complete"]:
            gate_report["failures"].append(
                f"critic round {round_no} incomplete (missing {check['missing']})")
            break
        if not check["has_findings"]:
            gate_report["notes"].append(
                f"critic round {round_no}: zero findings on {len(holdout)} tours")
            if gate_report["failures"]:
                gate_report["notes"].append("CRITIC-USELESS: machine gates fail "
                                           "but critic found nothing")
            break
        gate_report["critic_findings"] += 1
        shutil.copy2(report_path, workdir / "critic_report.md")
        run_agent("site-surveyor", workdir, load_fix_task(round_no), model,
                  variant, fix_timeout, args.format)
        collect_outputs(workdir, out_dir)
        gates = run_machine()
        gate_report.update({k: v for k, v in gates.items() if k != "failures"})
        gate_report["failures"] = list(gates.get("failures", []))

    gate_report["ok"] = not gate_report["failures"]
    write_gates_md(out_dir, gate_report)
    if not gate_report["ok"]:
        print(f"GATES FAIL: {gate_report['failures']}", file=sys.stderr)
        return 1
    stamp = stamp_metadata(profile_path, dev_urls + holdout)
    gate_report["notes"].append(f"stamped {stamp}")
    write_gates_md(out_dir, gate_report)
    print("COMPLETE: profile gated on blind holdout; see gates.md", flush=True)
    if args.promote:
        dest = promote_profile(out_dir, args.source)
        print(f"promoted={dest}", flush=True)
    return 0


if __name__ == "__main__":
    from shared.runtime import run_cli

    raise SystemExit(run_cli(main))
