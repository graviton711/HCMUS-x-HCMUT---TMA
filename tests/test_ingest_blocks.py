"""Offline tests for ingest blocks/clean/validate. No network, no browser."""

import re

from ingest import extract
from ingest.fetch import UnsafeURLError, validate_public_url

FIXTURE_HTML = """<!DOCTYPE html><html><head>
<title>Tour Example 7N6Đ</title>
<script type="application/ld+json">{"@type": "Product", "sku": "ABC",
"offers": {"price": 100, "priceCurrency": "VND"}}</script>
<script>window.__DATA__ = {"tourInfoData": {"dayStayText": "7N6Đ",
"departureName": "TP. Ho Chi Minh"}};</script>
<style>.hidden { display: none; }</style>
</head><body><h1>Tour Example 7N6Đ</h1>
<h2 id="sec-schedule">Lịch khởi hành</h2>
<p>Departs from TP. Ho Chi Minh.</p></body></html>"""


def test_validate_rejects_private_and_cross_origin_urls():
    for bad in ["http://127.0.0.1/x", "http://10.0.0.1/x", "ftp://example.test/x",
                "http://169.254.169.254/"]:
        try:
            validate_public_url(bad)
        except UnsafeURLError:
            continue
        raise AssertionError(f"accepted {bad}")
    try:
        validate_public_url("https://other.test/x", "example.test")
    except UnsafeURLError:
        return
    raise AssertionError("accepted cross-origin")


def test_blocks_parse_json_ld_nodes_in_order():
    nodes = extract.parse_json_ld(FIXTURE_HTML)
    assert nodes[0]["sku"] == "ABC"
    assert nodes[0]["offers"]["priceCurrency"] == "VND"


def test_blocks_iso_to_dmy():
    assert extract.iso_to_dmy("2026-10-25T08:00:00") == "25/10/2026"
    assert extract.iso_to_dmy(None) == ""
    assert extract.iso_to_dmy("not-a-date") == ""


def test_blocks_walk_departures_keeps_containers():
    found = []
    extract.walk_departures({"a": {"departureDate": "2026-10-04", "flights": ["VN1"]}}, found)
    assert found == [{"departureDate": "2026-10-04", "flights": ["VN1"]}]


def test_clean_drops_technical_fields_keeps_decision_fields():
    keep = re.compile(r"(code|date|price|name)$", re.I)
    dep = {"tourCode": "X1", "price": 100, "thumbnail": "u", "guid": "8e9fa47a-caa2-efce-3456-3a21bc4f10dd",
           "nothing": None, "note": "short"}
    from ingest.quality import filter_dep
    out = filter_dep(dep, {"thumbnail"}, keep)
    assert out == {"tourCode": "X1", "price": 100}


def test_clean_dedupes_identical_values_to_shared():
    from ingest.quality import dedupe_departures
    deps = [{"date": "d1", "hotel": "H", "price": 1}, {"date": "d2", "hotel": "H", "price": 2}]
    trimmed, shared = dedupe_departures(deps)
    assert shared == {"hotel": "H"}
    assert all("hotel" not in dep for dep in trimmed)


def test_clean_extract_notes_by_semantic_keys():
    from ingest.quality import extract_notes
    payloads = [{"infoInclude": "Visa fee and airport tax included here for real Dao",
                 "groupItems": [{"description": "x" * 600}]}]
    notes = extract_notes(payloads, "includ|exclud|condition")
    assert "infoInclude" in notes and "groupItems" not in notes


def test_profiles_load_and_reject_bad(tmp_path):
    from ingest.extract import load_profile, load_settings

    settings = load_settings()
    assert settings["batch"]["max_consecutive_failures"] == 10
    vietravel = load_profile("vietravel")
    assert vietravel["origin"] == "travel.com.vn"
    assert "combo" in " ".join(vietravel["flows"])
    bad = tmp_path / "bad.yaml"
    bad.write_text("just: [a, list]\n", encoding="utf-8")
    try:
        load_profile("bad", profiles_dir=tmp_path)
    except ValueError:
        return
    raise AssertionError("accepted bad profile")


def test_logging_redacts_secrets(caplog):
    from shared import get_logger, redact

    masked = redact({"api_key": "abcdefghij", "url": "https://example.test/x"})
    assert masked["api_key"] != "abcdefghij" and masked["url"].endswith("/x")
    with caplog.at_level("INFO", logger="mlai.test"):
        get_logger("test").info("hello")
    assert "hello" in caplog.text


def test_fetcher_refuses_unsafe_without_network():
    from ingest.fetch import RateLimiter, SafeFetcher

    fetcher = SafeFetcher(limiter=RateLimiter(delay=0))
    result = fetcher.fetch("http://127.0.0.1/x")
    assert result.status_code == 0 and result.error
    assert fetcher.requests_made == 0


def test_departure_evidence_grades():
    from ingest.quality import departure_evidence

    dep = {"tourCode": "X1", "salePrice": 100, "departureDate": "2026-10-04"}
    assert departure_evidence(dep, "X1 100 2026-10-04 here") == "verified"
    assert departure_evidence(dep, "only X1 here") == "partial"
    assert departure_evidence(dep, "nothing relevant") == "unverified"
    assert departure_evidence({}, "anything") == "unverified"


def test_cli_parses_args():
    from ingest.pipeline import _parse_args

    args = _parse_args(["https://example.test/t", "--profile", "dulichviet", "--limit", "5"])
    assert args.url.endswith("/t") and args.profile == "dulichviet" and args.limit == 5


def test_logging_level_from_env(monkeypatch):
    import logging

    from shared import get_logger

    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    logger = get_logger("envtest")
    assert logger.getEffectiveLevel() == logging.WARNING
    monkeypatch.delenv("LOG_LEVEL")
    assert get_logger("envtest2").getEffectiveLevel() == logging.INFO


def test_run_batch_respects_out_dir(tmp_path, monkeypatch):
    import ingest.pipeline as pipeline_mod
    from ingest.pipeline import run_batch

    calls = []

    def fake_run_tour(url, profile, settings, out_dir, robots_cache=None):
        calls.append(out_dir)
        return {"url": url, "status": "ok", "title": "T", "departures": 0,
                "verified": 0, "notes_keys": "", "error": ""}

    monkeypatch.setattr(pipeline_mod, "run_tour", fake_run_tour)
    out_csv = tmp_path / "out.csv"
    out_json = tmp_path / "json"
    assert run_batch(["https://example.test/1"], {}, {}, out_csv, out_json) == 0
    assert calls == [out_json]
    assert out_csv.exists()


def test_batch_fetches_robots_once_per_origin(tmp_path, monkeypatch):
    import ingest.pipeline as pipeline_mod
    from ingest.fetch import FetchResult
    from ingest.pipeline import run_batch

    robots_calls: list[str] = []

    class FakeFetcher:
        def __init__(self, *args, **kwargs):
            self.user_agent = "test"

        def fetch(self, url, origin_host=""):
            if url.endswith("/robots.txt"):
                robots_calls.append(url)
                return FetchResult(url, 404, "", b"", "HTTP 404")
            return FetchResult(url, 200, "text/html",
                               b"<html><head><title>T</title></head><body></body></html>", None)

    monkeypatch.setattr(pipeline_mod, "SafeFetcher", FakeFetcher)
    out_csv = tmp_path / "out.csv"
    out_json = tmp_path / "json"
    urls = ["https://a.test/1", "https://a.test/2", "https://b.test/1"]
    assert run_batch(urls, {}, {}, out_csv, out_json) == 0
    assert sorted(robots_calls) == ["https://a.test/robots.txt", "https://b.test/robots.txt"]


def test_compile_keep_is_case_insensitive_regression():
    from ingest.quality import compile_keep, filter_dep

    keep = compile_keep(["(code|date|price)$"])
    out = filter_dep({"tourCode": "X1", "departureDate": "2026-10-04", "salePrice": 100,
                      "priority": 1}, set(), keep)
    assert out == {"tourCode": "X1", "departureDate": "2026-10-04", "salePrice": 100}





def test_migrate_db_applies_each_sql_once(monkeypatch, tmp_path):
    import sys
    import types

    import ingest.pipeline as pipeline_mod
    from ingest.pipeline import migrate_db

    (tmp_path / '001_a.sql').write_text('CREATE TABLE t1 (id INT);', encoding='utf-8')
    monkeypatch.setattr(pipeline_mod, '_migrations_dir', lambda: tmp_path)
    seen = []

    class FakeCursor:
        def __enter__(self): return self
        def __exit__(self, *a): return None
        def execute(self, q, p=()): seen.append(q)
        def fetchone(self): return None

    class FakeConn:
        def __enter__(self): return self
        def __exit__(self, *a): return None
        def cursor(self): return FakeCursor()
        def commit(self): pass

    fake_psycopg = types.SimpleNamespace(connect=lambda _url: FakeConn())
    monkeypatch.setitem(sys.modules, 'psycopg', fake_psycopg)
    assert migrate_db('postgresql://unused') == 1
    assert any('CREATE TABLE t1' in q for q in seen)
    assert any('schema_migrations' in q for q in seen)
