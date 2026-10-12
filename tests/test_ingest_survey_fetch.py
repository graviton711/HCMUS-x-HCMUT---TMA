"""Offline coverage and cache tests for complete survey discovery."""

from __future__ import annotations

import csv

import yaml

import ingest.survey_fetch as survey_fetch
from ingest.fetch import FetchResult


class FakeFetcher:
    calls: list[str] = []

    def __init__(self, **_kwargs):
        self.user_agent = "test-agent"
        self.calls = []
        type(self).calls = self.calls

    def fetch(self, url, origin_host="", extra_headers=None):
        self.calls.append(url)
        bodies = {
            "https://example.test/robots.txt": (
                b"User-agent: *\nAllow: /\nSitemap: https://example.test/sitemap.xml\n"),
            "https://example.test/sitemap.xml": (
                b"<sitemapindex><sitemap><loc>https://example.test/tours.xml</loc></sitemap></sitemapindex>"),
            "https://example.test/tours.xml": (
                b"<urlset><url><loc>https://example.test/tour-a</loc></url></urlset>"),
            "https://example.test/list?page=1": (
                b'<a href="/tour-a">A</a><a href="/tour-b">B</a>'
                b'<a href="/list?page=2">2</a>'),
            "https://example.test/list?page=2": b'<a href="/tour-b">B</a>',
            "https://example.test/tour-a": b"<html>A</html>",
            "https://example.test/tour-b": b"<html>B</html>",
        }
        body = bodies.get(url)
        if body is None:
            return FetchResult(url, 404, "", error="HTTP 404")
        ctype = "text/html" if b"<html>" in body or b"<a " in body else "application/xml"
        return FetchResult(url, 200, ctype, body)


def _profile(path):
    path.write_text(yaml.safe_dump({
        "origin": "example.test",
        "sitemaps": ["https://example.test/sitemap.xml"],
        "tour_url_patterns": ["/tour-"],
        "discovery": {"method": "search_pages", "entry": "https://example.test/list?page=1",
                      "page_param": "page", "max_pages": 5},
        "fields": {},
    }), encoding="utf-8")
    return path


def test_discovery_unions_dedupes_listing_and_sitemap_then_caches_tour_pages(tmp_path, monkeypatch):
    FakeFetcher.calls = []
    monkeypatch.setattr(survey_fetch, "SafeFetcher", FakeFetcher)
    profile = _profile(tmp_path / "profile.yaml")
    raw = tmp_path / "raw"

    first = survey_fetch.fetch_all(profile, raw, delay_s=1)
    with (raw / "tour_pages.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    detail_calls = [url for url in FakeFetcher.calls if "/tour-" in url]

    assert first["discovered_sitemap"] == 1
    assert first["discovered_listing"] == 2
    assert first["discovered_unique"] == 2
    assert [row["status"] for row in rows] == ["ok", "ok"]
    assert len(detail_calls) == 2

    FakeFetcher.calls = []
    second = survey_fetch.fetch_all(profile, raw, delay_s=1)
    assert second["fetched_or_cached"] == 2
    assert second["cache_mode"] == "reuse"
    assert FakeFetcher.calls == ["https://example.test/robots.txt"]


def test_refresh_refetches_discovery_and_tour_pages(tmp_path, monkeypatch):
    FakeFetcher.calls = []
    monkeypatch.setattr(survey_fetch, "SafeFetcher", FakeFetcher)
    profile = _profile(tmp_path / "profile.yaml")
    raw = tmp_path / "raw"

    survey_fetch.fetch_all(profile, raw, delay_s=1)
    FakeFetcher.calls = []
    refreshed = survey_fetch.fetch_all(profile, raw, delay_s=1, refresh=True)

    assert refreshed["cache_mode"] == "refresh"
    assert "https://example.test/sitemap.xml" in FakeFetcher.calls
    assert "https://example.test/list?page=1" in FakeFetcher.calls
    assert "https://example.test/tour-a" in FakeFetcher.calls


def test_discovery_reports_listing_page_cap_as_coverage_gap(tmp_path, monkeypatch):
    FakeFetcher.calls = []
    monkeypatch.setattr(survey_fetch, "SafeFetcher", FakeFetcher)
    profile = _profile(tmp_path / "profile.yaml")
    data = yaml.safe_load(profile.read_text(encoding="utf-8"))
    data["discovery"]["max_pages"] = 1
    profile.write_text(yaml.safe_dump(data), encoding="utf-8")

    result = survey_fetch.fetch_all(profile, tmp_path / "raw", delay_s=1)

    assert any(gap.startswith("listing_page_cap:2>1") for gap in result["gaps"])
