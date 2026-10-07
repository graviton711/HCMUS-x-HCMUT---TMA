import pytest

from ingest.survey import _robots_sitemaps


def test_robots_sitemaps_extracts_all_declared():
    text = "\n".join([
        "User-agent: *",
        "Disallow: /admin",
        "Sitemap: https://example.test/sitemap.xml",
        "",
        "Sitemap: https://example.test/du-lich/sitemap_index.xml",
    ])
    assert _robots_sitemaps(text) == [
        "https://example.test/sitemap.xml",
        "https://example.test/du-lich/sitemap_index.xml",
    ]


def test_robots_sitemaps_case_insensitive_and_empty():
    assert _robots_sitemaps("SITEMAP: https://example.test/s.xml") == [
        "https://example.test/s.xml",
    ]
    assert _robots_sitemaps("User-agent: *\nDisallow: /") == []


def test_agent_task_renders_origin_without_placeholders():
    from ingest.survey import load_agent_task

    task = load_agent_task('https://example.test/')
    assert 'https://example.test/' in task
    assert '{' not in task and '}' not in task
    assert 'ingest.extract' in task


def test_mvp_sources_csv_matches_profiles():
    import csv
    from pathlib import Path
    from urllib.parse import urlsplit

    import yaml

    root = Path('configs')
    with (root / 'sources-mvp.csv').open(encoding='utf-8') as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) >= 1
    assert list(rows[0].keys()) == ['source', 'url']
    yaml_names = {p.stem for p in (root / 'profiles').glob('*.yaml')}
    for r in rows:
        host = (urlsplit(r['url']).hostname or '').lower()
        matched = [n for n in yaml_names
                   if yaml.safe_load(((root / 'profiles') / (n + '.yaml')).read_text(encoding='utf-8'))['origin'] == host]
        assert len(matched) == 1, f"no unique profile for {r['url']}: {matched}"


def test_resolve_origin_reads_mvp_scope_list():
    from ingest.survey import resolve_origin

    assert resolve_origin('dulichviet') == 'https://dulichviet.com.vn'
    with pytest.raises(ValueError, match='exactly one row'):
        resolve_origin('khong-ton-tai')


def test_promote_copies_profile_into_configs(tmp_path):
    from ingest.survey import _parse_args, promote_profile

    out_dir = tmp_path / "survey"
    out_dir.mkdir()
    (out_dir / "profile.yaml").write_text("origin: example.test\n", encoding="utf-8")
    dest = promote_profile(out_dir, "example", tmp_path / "profiles")
    assert dest.read_text(encoding="utf-8").startswith(
        "# yaml-language-server: $schema=../profile.schema.json\norigin: example.test\n")
    with pytest.raises(ValueError, match="no profile.yaml"):
        promote_profile(tmp_path / "empty", "example", tmp_path / "profiles")
    assert _parse_args(["--source", "example", "--promote"]).promote is True
    assert _parse_args(["--source", "example"]).promote is False
    defaults = _parse_args(["--source", "example"])
    assert defaults.model is None and defaults.variant is None and defaults.timeout_min is None


def test_settings_has_tunable_sections():
    from ingest.extract import load_settings

    settings = load_settings()
    assert settings["sitemap"]["attempts"] == 2
    assert settings["batch"]["workers"] == 8
    assert settings["audit"]["min_evidence"] == 0.9
    assert settings["survey"]["timeout_min"] == 20
    assert settings["survey"]["prefetch_timeout_s"] == 15


def _pool():
    return [
        {"url": "https://example.test/a1", "cluster": "a"},
        {"url": "https://example.test/a2", "cluster": "a"},
        {"url": "https://example.test/a3", "cluster": "a"},
        {"url": "https://example.test/b1", "cluster": "b"},
        {"url": "https://example.test/b2", "cluster": "b"},
        {"url": "https://example.test/c1", "cluster": "c"},
    ]


def test_split_holdout_stratified_deterministic_and_blind_to_dev():
    from ingest.survey import split_holdout

    dev = ["https://example.test/a1"]
    first, _ = split_holdout(_pool()[1:], 3, seed=7, dev_urls=dev)
    second, _ = split_holdout(_pool()[1:], 3, seed=7, dev_urls=dev)
    assert first == second and len(first) == 3
    assert "https://example.test/a1" not in first
    clusters = set()
    pool = _pool()[1:]
    for url in first:
        clusters.add(next(e["cluster"] for e in pool if e["url"] == url))
    assert {"a", "b", "c"} <= clusters


def test_coverage_gaps_and_threshold_and_keys(tmp_path):
    from ingest.survey import check_profile_keys, coverage_gaps, pass_threshold, stamp_metadata

    assert check_profile_keys({"origin": "x"}) != []
    assert check_profile_keys({"origin": "x", "render": False, "flows": [],
                               "sitemaps": [], "tour_url_patterns": [],
                               "discovery": {}, "fields": {}}) == []
    assert coverage_gaps(_pool(), ["https://example.test/a2",
                                   "https://example.test/b1",
                                   "https://example.test/c1"]) == []
    assert coverage_gaps(_pool(), ["https://example.test/c1"]) == ["a", "b"]
    assert pass_threshold(1.0, 0.05, 0.9) == 0.95
    assert pass_threshold(0.91, 0.05, 0.9) == 0.9
    profile = tmp_path / "p.yaml"
    profile.write_text("origin: example.test\n", encoding="utf-8")
    stamp = stamp_metadata(profile, ["https://example.test/a1"])
    assert stamp["version"] == 1 and stamp["sample_tours"] == 1
    assert stamp_metadata(profile, [])["version"] == 2
    import yaml

    data = yaml.safe_load(profile.read_text(encoding="utf-8"))
    assert data["surveyed_at"].endswith("+07:00") and data["sample_tours"] == []


def test_check_critic_report_completeness(tmp_path):
    from ingest.survey import check_critic_report

    holdout = ["https://example.test/a", "https://example.test/b"]
    report = tmp_path / "r.md"
    report.write_text("https://example.test/a\nFAIL: price\nhttps://example.test/b\nPASS\n",
                      encoding="utf-8")
    check = check_critic_report(report, holdout)
    assert check == {"complete": True, "has_findings": True, "missing": []}
    report.write_text("https://example.test/a\nZERO failures attempted all attacks\n",
                      encoding="utf-8")
    check = check_critic_report(report, holdout)
    assert check["complete"] is False and check["missing"] == ["https://example.test/b"]


def test_survey_args_cover_critic_and_holdout():
    from ingest.survey import _parse_args

    args = _parse_args(["--source", "example"])
    assert (args.critic_rounds, args.holdout_n, args.seed) == (2, 3, 7)
    args = _parse_args(["--source", "example", "--critic-rounds", "0"])
    assert args.critic_rounds == 0


def test_critic_prompt_loads_and_renders():
    from ingest.survey import load_agent_spec, load_critic_task

    spec = load_agent_spec("configs/agents/profile-critic.yaml")
    assert "profile-critic" in spec or "adversary" in spec
    task = load_critic_task("https://example.test/", "p.yaml", "h.txt", "hdir",
                            1, 20, path="configs/agents/profile-critic.yaml")
    assert all(s in task for s in ("https://example.test/", "p.yaml", "h.txt",
                                   "hdir", "1", "20"))
    assert "{" not in task and "}" not in task
