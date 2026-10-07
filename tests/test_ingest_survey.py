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
    assert dest.read_text(encoding="utf-8") == "origin: example.test\n"
    with pytest.raises(ValueError, match="no profile.yaml"):
        promote_profile(tmp_path / "empty", "example", tmp_path / "profiles")
    assert _parse_args(["--source", "example", "--promote"]).promote is True
    assert _parse_args(["--source", "example"]).promote is False
