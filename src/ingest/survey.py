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


EXPECTED = ["profile.yaml", "evidence.md", "selftest.md", "unknowns.md", "raw"]

USER_AGENT = "MLAITourSourceAuditor/0.1"
PREFETCH_TIMEOUT_S = 15
MAX_BODY_BYTES = 2_000_000


def _robots_sitemaps(text: str) -> list[str]:
    return [line.split(":", 1)[1].strip() for line in text.splitlines()
            if line.lower().startswith("sitemap:")]


def _save_url(url: str, raw_dir: Path) -> str | None:
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", urlsplit(url).path.strip("/")) or "robots.txt"
    dest = raw_dir / name
    if dest.exists():
        return None
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=PREFETCH_TIMEOUT_S) as resp:
            body = resp.read(MAX_BODY_BYTES)
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


def prefetch(origin: str, raw_dir: Path) -> list[str]:
    """Best-effort: save robots.txt and its declared sitemaps into raw/.

    Mechanical work the agent would otherwise burn HTTP requests and LLM
    turns on; any failure is ignored (the agent still handles the source).
    """
    base = origin.rstrip("/")
    robots = _save_url(f"{base}/robots.txt", raw_dir)
    if robots:
        sitemaps = _robots_sitemaps(
            (raw_dir / robots).read_text(encoding="utf-8", errors="replace"))
    else:
        sitemaps = []
    sitemaps.append(f"{base}/sitemap.xml")
    with ThreadPoolExecutor(max_workers=4) as pool:
        names = pool.map(lambda url: _save_url(url, raw_dir), dict.fromkeys(sitemaps))
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
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--variant", default=VARIANT)
    parser.add_argument("--timeout-min", type=int, default=20)
    parser.add_argument("--format", choices=["default", "json"], default="default",
                        help="opencode output format (default: formatted readable output)")
    parser.add_argument("--output", type=Path, default=None,
                        help="default: artifacts/agent_surveys/<source>")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = _parse_args(argv)
    try:
        origin = args.origin or resolve_origin(args.source)
    except ValueError as exc:
        print(f"Invalid source: {exc}", file=sys.stderr)
        return 2
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

    # raw/ các lần chạy trước nằm ở out_dir/raw (chuẩn cũ) — đưa vào workdir
    # để agent dùng lại thay vì tải lại từ đầu.
    legacy_raw = out_dir / "raw"
    if legacy_raw.exists():
        shutil.copytree(legacy_raw, raw_dir, dirs_exist_ok=True)

    started = time.perf_counter()
    prefetched = prefetch(origin, raw_dir)
    print(f"prefetch={prefetched or 'nothing'} elapsed={time.perf_counter() - started:.1f}s",
          flush=True)

    task = load_agent_task(origin)
    print(f"workdir={workdir}", flush=True)
    print(f"target={origin} model={args.model} variant={args.variant}", flush=True)
    exe = shutil.which("opencode") or shutil.which("opencode.cmd") or "opencode"
    returncode: int | None = None
    try:
        completed = subprocess.run(
            [exe, "run", "--model", args.model, "--variant", args.variant,
             "--agent", "site-surveyor", "--dir", str(workdir),
             "--format", args.format, task],
            timeout=args.timeout_min * 60, check=False, env=_agent_env(),
        )
        returncode = completed.returncode
    except subprocess.TimeoutExpired:
        print(f"agent timed out after {args.timeout_min} min; collecting partial output",
              file=sys.stderr)
    agent_elapsed = time.perf_counter() - started

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
    print(f"agent_elapsed={agent_elapsed:.0f}s total={time.perf_counter() - started:.0f}s "
          f"opencode_exit={returncode} saved={out_dir}", flush=True)
    if missing:
        print(f"MISSING (incomplete run): {missing}", file=sys.stderr)
        return 1
    print("COMPLETE: profile.yaml, evidence.md, unknowns.md, raw/ all present")
    return 0


if __name__ == "__main__":
    from shared.runtime import run_cli

    raise SystemExit(run_cli(main))
