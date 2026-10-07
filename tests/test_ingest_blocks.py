"""Offline tests for ingest blocks/clean/validate. No network, no browser."""

import re

from ingest import extract
from ingest.fetch import SafeFetcher, UnsafeURLError, validate_public_url

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
    profile = load_profile("dulichviet")
    assert profile["origin"] == "dulichviet.com.vn"
    assert "static" in " ".join(profile["flows"])
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


def test_verify_record_checks_raw_not_cleaned():
    from ingest.quality import verify_record

    record = {"tour_name": "Tour Ha Giang", "transport": "mixed",
              "price": 8590000, "url": "https://example.test/t"}
    raw = {"tour_name": "Tour Ha Giang", "transport": "Xe du lich, May bay",
           "price": "8,590,000 VND"}
    html = "<h1>Tour Ha Giang</h1><p>Xe du lich, May bay</p><p>8,590,000 VND</p>"
    assert verify_record(record, raw, html) == ("verified", [])
    verdict, missing = verify_record(record, raw, "<h1>Tour Ha Giang</h1><p>1,000 VND</p>")
    assert verdict == "partial" and sorted(missing) == ["price", "transport"]
    assert verify_record({"url": "https://example.test/t"}, {}, html) == ("unverified", [])
    assert verify_record({}, {}, html) == ("unverified", [])


def test_verify_record_flags_value_synthesized_without_source():
    from ingest.quality import verify_record

    record = {"currency": "VND"}
    assert verify_record(record, {"currency": ""}, "<p>anything</p>") == ("unverified", ["currency"])


def test_timestamps_use_vietnam_time():
    from shared import now_vn_iso

    assert now_vn_iso().endswith("+07:00")


def test_cli_parses_args():
    from ingest.pipeline import _parse_args

    args = _parse_args(["https://example.test/t", "--profile", "dulichviet", "--limit", "5"])
    assert args.url.endswith("/t") and args.profile == "dulichviet" and args.limit == 5
    assert _parse_args(["--publish"]).publish == ""
    assert _parse_args(["--publish", "out"]).publish == "out"


def test_save_discovered_roundtrip(tmp_path):
    from ingest.pipeline import _read_done, _save_discovered

    path = _save_discovered(["https://example.test/du-lich-a",
                             "https://example.test/du-lich-b"], tmp_path / "d.csv")
    assert _read_done(path) == {"https://example.test/du-lich-a",
                                "https://example.test/du-lich-b"}


def test_default_paths_namespace_per_source(tmp_path, monkeypatch):
    import ingest.pipeline as pipeline_mod
    from ingest.pipeline import _source_dir, run_batch

    settings = {"output": {"dir": str(tmp_path)}}
    assert _source_dir(settings, "a") != _source_dir(settings, "b")
    assert _source_dir(settings, "a").name == "a"

    def fake_run_tour(url, profile, settings, out_dir, robots_cache=None,
                      conditional=None):
        out_dir.mkdir(parents=True, exist_ok=True)
        return {"url": url, "status": "ok", "title": "T", "departures": 0,
                "verified": 0, "notes_keys": "", "error": ""}

    monkeypatch.setattr(pipeline_mod, "run_tour", fake_run_tour)
    out_csv = tmp_path / "out.csv"
    assert run_batch(["https://example.test/1"], {"name": "s"}, settings,
                     out_csv, None) == 0
    assert (tmp_path / "s" / "tours").is_dir()


def test_audit_urls_from_csv_and_missing_default(tmp_path, monkeypatch):
    import csv as _csv

    import ingest.audit as audit_mod

    csv_path = tmp_path / "tours.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = _csv.DictWriter(handle, fieldnames=["url"])
        writer.writeheader()
        writer.writerow({"url": "https://example.test/du-lich-a"})
    assert audit_mod._urls_from_csv(csv_path) == ["https://example.test/du-lich-a"]
    monkeypatch.setattr(audit_mod, "load_settings",
                        lambda path=None: {"output": {"dir": str(tmp_path / "empty")}})
    assert audit_mod.main(["--profile", "dulichviet"]) == 2


def test_logging_level_from_env(monkeypatch):
    import logging

    from shared import get_logger

    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    logger = get_logger("envtest")
    assert logger.getEffectiveLevel() == logging.WARNING
    monkeypatch.delenv("LOG_LEVEL")
    assert get_logger("envtest2").getEffectiveLevel() == logging.INFO


def test_sitemap_follows_index_and_retries_once():
    from ingest.fetch import FetchResult
    from ingest.pipeline import sitemap_urls

    index = (b'<?xml version="1.0"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
             b'<sitemap><loc>https://example.test/sitemap/tour_1.xml</loc></sitemap></sitemapindex>')
    child = (b'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
             b'<url><loc>https://example.test/du-lich-ha-long</loc></url>'
             b'<url><loc>https://example.test/tin-tuc</loc></url></urlset>')
    calls: list[str] = []

    class FakeFetcher(SafeFetcher):
        def fetch(self, url, origin_host="", extra_headers=None):
            calls.append(url)
            if url.endswith("tour_1.xml"):
                return FetchResult(url, 200, "text/xml", child, None)
            return FetchResult(url, 200, "text/xml", index, None)

    urls = sitemap_urls(FakeFetcher(), ["https://example.test/sitemap_tour_index.xml"], ["/du-lich-"])
    assert urls == ["https://example.test/du-lich-ha-long"]
    assert calls.count("https://example.test/sitemap_tour_index.xml") == 1


def test_sitemap_orders_fresh_first_and_filters_since():
    from ingest.fetch import FetchResult
    from ingest.pipeline import sitemap_urls

    def urlset(*pairs):
        body = ['<?xml version="1.0"?><urlset>']
        for loc, lastmod in pairs:
            body.append(f"<url><loc>{loc}</loc>")
            if lastmod:
                body.append(f"<lastmod>{lastmod}</lastmod>")
            body.append("</url>")
        body.append("</urlset>")
        return "".join(body).encode()

    pages = {
        "https://example.test/s.xml": urlset(
            ("https://example.test/du-lich-old", "2020-01-01T00:00:00+07:00"),
            ("https://example.test/du-lich-new", "2026-09-01T00:00:00+07:00"),
            ("https://example.test/du-lich-nostamp", ""),
        ),
    }

    class FakeFetcher(SafeFetcher):
        def fetch(self, url, origin_host="", extra_headers=None):
            return FetchResult(url, 200, "text/xml", pages[url], None)

    urls = sitemap_urls(FakeFetcher(), ["https://example.test/s.xml"], ["/du-lich-"])
    assert urls == ["https://example.test/du-lich-new",
                    "https://example.test/du-lich-old",
                    "https://example.test/du-lich-nostamp"]
    assert sitemap_urls(FakeFetcher(), ["https://example.test/s.xml"], ["/du-lich-"],
                        min_lastmod="2026-01-01") == ["https://example.test/du-lich-new"]


def test_sitemap_gives_up_after_two_failures(caplog):
    from ingest.fetch import FetchResult
    from ingest.pipeline import sitemap_urls

    calls: list[str] = []

    class FakeFetcher(SafeFetcher):
        def fetch(self, url, origin_host="", extra_headers=None):
            calls.append(url)
            return FetchResult(url, 0, "", b"", "TimeoutError")

    assert sitemap_urls(FakeFetcher(), ["https://example.test/s.xml"], ["/du-lich-"]) == []
    assert calls == ["https://example.test/s.xml"] * 2


def test_sitemap_attempts_come_from_settings():
    from ingest.fetch import FetchResult
    from ingest.pipeline import sitemap_urls

    calls: list[str] = []

    class FakeFetcher(SafeFetcher):
        def fetch(self, url, origin_host="", extra_headers=None):
            calls.append(url)
            return FetchResult(url, 0, "", b"", "TimeoutError")

    assert sitemap_urls(FakeFetcher(), ["https://example.test/s.xml"], ["/du-lich-"],
                        attempts=1) == []
    assert calls == ["https://example.test/s.xml"]
    assert sitemap_urls(FakeFetcher(), ["https://example.test/s.xml"], ["/du-lich-"],
                        attempts=3) == []
    assert calls == ["https://example.test/s.xml"] * 4


def test_make_fetcher_reads_settings():
    from ingest.fetch import make_fetcher

    fetcher = make_fetcher({"fetch": {"timeout_s": 5, "max_bytes": 1000,
                                      "delay_s": 0.1, "user_agent": "TestAgent/1.0"}})
    assert (fetcher.timeout, fetcher.max_bytes, fetcher.user_agent,
            fetcher.limiter.delay) == (5.0, 1000, "TestAgent/1.0", 0.1)
    fallback = make_fetcher({})
    assert (fallback.timeout, fallback.max_bytes) == (20.0, 2000000)


def test_search_pages_workers_match_sequential_and_limit_stops_early():
    from ingest.fetch import FetchResult
    from ingest.pipeline import search_page_urls

    def page(cards, last):
        links = "".join(f'<a href="{c}">tour</a>' for c in cards)
        paging = "".join(
            f'<a href="/tim-kiem?q=&type=tour&perPage=50&page={n}">{n}</a>'
            for n in range(2, last + 1))
        return f"<html><body>{links}{paging}</body></html>".encode()

    bodies = {
        1: page(["https://example.test/du-lich-a"], 4),
        2: page(["https://example.test/du-lich-b"], 4),
        3: page(["https://example.test/du-lich-c"], 4),
        4: page(["https://example.test/du-lich-d"], 4),
    }
    fetched: list[int] = []

    class FakeFetcher(SafeFetcher):
        def fetch(self, url, origin_host="", extra_headers=None):
            import re as _re
            match = _re.search(r"[?&]page=(\d+)", url)
            num = int(match.group(1)) if match else 1
            fetched.append(num)
            return FetchResult(url, 200, "text/html", bodies[num], None)

    discovery = {"method": "search_pages",
                 "entry": "https://example.test/tim-kiem?q=&type=tour",
                 "page_param": "page", "per_page_param": "perPage",
                 "per_page": 50, "max_pages": 200, "strip_query": True}
    seq = search_page_urls(FakeFetcher(), discovery, ["/du-lich-"])
    assert seq == ["https://example.test/du-lich-a", "https://example.test/du-lich-b",
                   "https://example.test/du-lich-c", "https://example.test/du-lich-d"]
    assert search_page_urls(FakeFetcher(), discovery, ["/du-lich-"], workers=4) == seq
    fetched.clear()
    limited = search_page_urls(FakeFetcher(), discovery, ["/du-lich-"], workers=1, limit=2)
    assert limited == seq[:2]
    assert fetched == [1, 2]
    seen_pages: list[tuple[int, list[str]]] = []
    limited = search_page_urls(FakeFetcher(), discovery, ["/du-lich-"], workers=4, limit=2,
                               on_page=lambda p, fresh: seen_pages.append((p, fresh)))
    assert limited == seq[:2]
    assert [p for p, _ in seen_pages] == [1, 2]
    assert seen_pages[0][1] == ["https://example.test/du-lich-a"]


def test_search_pages_dedupes_startday_links_and_caps_pages():
    from ingest.fetch import FetchResult
    from ingest.pipeline import discover_urls, search_page_urls

    def page(cards, last):
        links = "".join(f'<a href="{c}">tour</a>' for c in cards)
        paging = "".join(
            f'<a href="/tim-kiem?q=&type=tour&perPage=50&page={n}">{n}</a>'
            for n in range(2, last + 1))
        return f"<html><body>{links}{paging}</body></html>".encode()

    tour_a = "https://example.test/du-lich-trong-nuoc/tour-a"
    tour_b = "https://example.test/du-lich-trong-nuoc/tour-b"
    bodies = {
        1: page([f"{tour_a}?startday=2026-10-16", f"{tour_a}?startday=2026-10-23",
                 f"{tour_b}?startday=2026-10-16", "https://other.test/du-lich-x"], 3),
        2: page([f"{tour_b}?startday=2026-11-01"], 3),
        3: page([], 3),
    }

    class FakeFetcher(SafeFetcher):
        def fetch(self, url, origin_host="", extra_headers=None):
            import re as _re
            match = _re.search(r"[?&]page=(\d+)", url)
            num = int(match.group(1)) if match else 1
            return FetchResult(url, 200, "text/html", bodies[num], None)

    discovery = {"method": "search_pages",
                 "entry": "https://example.test/tim-kiem?q=&type=tour",
                 "page_param": "page", "per_page_param": "perPage",
                 "per_page": 50, "max_pages": 200, "strip_query": True}
    assert search_page_urls(FakeFetcher(), discovery, ["/du-lich-"]) == [tour_a, tour_b]
    profile = {"discovery": discovery}
    assert discover_urls(FakeFetcher(), profile, ["/du-lich-"]) == [tour_a, tour_b]
    assert discover_urls(FakeFetcher(), {}, ["/du-lich-"]) == []
    capped = dict(discovery, max_pages=1)
    seen: list[str] = []

    class CountingFetcher(FakeFetcher):
        def fetch(self, url, origin_host="", extra_headers=None):
            seen.append(url)
            return super().fetch(url, origin_host, extra_headers)

    assert search_page_urls(CountingFetcher(), capped, ["/du-lich-"]) == [tour_a, tour_b]
    assert all("page=2" not in u and "page=3" not in u for u in seen)


def test_run_batch_respects_out_dir(tmp_path, monkeypatch):
    import ingest.pipeline as pipeline_mod
    from ingest.pipeline import run_batch

    calls = []

    def fake_run_tour(url, profile, settings, out_dir, robots_cache=None,
                      conditional=None):
        calls.append(out_dir)
        return {"url": url, "status": "ok", "title": "T", "departures": 0,
                "verified": 0, "notes_keys": "", "error": ""}

    monkeypatch.setattr(pipeline_mod, "run_tour", fake_run_tour)
    out_csv = tmp_path / "out.csv"
    out_json = tmp_path / "json"
    assert run_batch(["https://example.test/1"], {},
                     {"output": {"dir": str(tmp_path)}}, out_csv, out_json) == 0
    assert calls == [out_json]
    assert out_csv.exists()


def test_batch_fetches_robots_once_per_origin(tmp_path, monkeypatch):
    import ingest.pipeline as pipeline_mod
    from ingest.fetch import FetchResult
    from ingest.pipeline import run_batch

    robots_calls: list[str] = []

    class FakeFetcher(SafeFetcher):
        def __init__(self, *args, **kwargs):
            self.user_agent = "test"

        def fetch(self, url, origin_host="", extra_headers=None):
            if url.endswith("/robots.txt"):
                robots_calls.append(url)
                return FetchResult(url, 404, "", b"", "HTTP 404")
            return FetchResult(url, 200, "text/html",
                               b"<html><head><title>T</title></head><body></body></html>", None)

    monkeypatch.setattr(pipeline_mod, "make_fetcher", lambda settings: FakeFetcher())
    out_csv = tmp_path / "out.csv"
    out_json = tmp_path / "json"
    urls = ["https://a.test/1", "https://a.test/2", "https://b.test/1"]
    assert run_batch(urls, {}, {"output": {"dir": str(tmp_path)}}, out_csv, out_json) == 0
    assert sorted(robots_calls) == ["https://a.test/robots.txt", "https://b.test/robots.txt"]


def test_concurrent_batch_keeps_input_order(tmp_path, monkeypatch):
    import csv as _csv
    import threading

    import ingest.pipeline as pipeline_mod
    from ingest.pipeline import run_batch

    gate = threading.Event()

    def fake_run_tour(url, profile, settings, out_dir, robots_cache=None):
        if "slow.test" in url:
            assert gate.wait(timeout=30)
        else:
            gate.set()
        return {"url": url, "status": "ok", "title": "T", "departures": 0,
                "verified": 0, "notes_keys": "", "error": ""}

    monkeypatch.setattr(pipeline_mod, "run_tour", fake_run_tour)
    monkeypatch.setattr(pipeline_mod, "fetch_robots", lambda *a: None)
    out_csv = tmp_path / "out.csv"
    out_json = tmp_path / "json"
    settings = {"output": {"dir": str(tmp_path)},
                "batch": {"workers": 2, "delay_s": 0, "max_consecutive_failures": 10}}
    urls = ["https://slow.test/1", "https://fast.test/2"]
    assert run_batch(urls, {"flows": ["static"]}, settings, out_csv, out_json) == 0
    with out_csv.open(encoding="utf-8-sig") as handle:
        rows = list(_csv.DictReader(handle))
    assert [r["url"] for r in rows] == urls


def test_conditional_fetch_skips_unchanged_pages(tmp_path, monkeypatch):
    import hashlib as _hashlib

    import ingest.pipeline as pipeline_mod
    from ingest.fetch import FetchResult
    from ingest.pipeline import run_tour

    body = b"<html><head><title>T</title></head><body>hi</body></html>"
    digest = _hashlib.sha256(body).hexdigest()
    seen_headers: list = []

    class FakeFetcher(SafeFetcher):
        def __init__(self, *args, **kwargs):
            self.user_agent = "test"

        def fetch(self, url, origin_host="", extra_headers=None):
            if url.endswith("/robots.txt"):
                return FetchResult(url, 404, "", b"", "HTTP 404")
            seen_headers.append(extra_headers or {})
            if (extra_headers or {}).get("If-None-Match") == '"abc"':
                return FetchResult(url, 304, "", b"", None, {"ETag": '"abc"'})
            return FetchResult(url, 200, "text/html", body, None, {"ETag": '"abc"'})

    monkeypatch.setattr(pipeline_mod, "make_fetcher", lambda settings: FakeFetcher())
    monkeypatch.setattr(pipeline_mod, "fetch_robots", lambda *a: None)
    out_json = tmp_path / "json"

    row = run_tour("https://example.test/1", {}, {}, out_json,
                   None, {"etag": '"abc"', "last_modified": "", "hash": "old"})
    assert row["status"] == "not_modified"
    assert seen_headers[-1].get("If-None-Match") == '"abc"'
    assert row["_state_entry"]["hash"] == "old"

    row = run_tour("https://example.test/2", {}, {}, out_json,
                   None, {"etag": "", "last_modified": "", "hash": digest})
    assert row["status"] == "not_modified"

    row = run_tour("https://example.test/3", {}, {}, out_json,
                   None, {"etag": "", "last_modified": "", "hash": "stale"})
    assert row["status"] == "ok"
    assert row["_state_entry"]["hash"] == digest

    row = run_tour("https://example.test/4", {}, {}, out_json)
    assert row["status"] == "ok"
    assert row["_state_entry"]["hash"] == digest


def test_state_file_round_trip_and_corrupt_recovery(tmp_path, monkeypatch):
    import ingest.pipeline as pipeline_mod
    from ingest.fetch import FetchResult
    from ingest.pipeline import _load_state, _save_state, run_batch

    assert _load_state(tmp_path / "missing.json") == {}
    (tmp_path / "bad.json").write_text("not json{{", encoding="utf-8")
    assert _load_state(tmp_path / "bad.json") == {}
    _save_state(tmp_path / "s.json", {"u": {"hash": "h"}})
    assert _load_state(tmp_path / "s.json") == {"u": {"hash": "h"}}

    class FakeFetcher(SafeFetcher):
        def __init__(self, *args, **kwargs):
            self.user_agent = "test"

        def fetch(self, url, origin_host="", extra_headers=None):
            if url.endswith("/robots.txt"):
                return FetchResult(url, 404, "", b"", "HTTP 404")
            return FetchResult(url, 200, "text/html",
                               b"<html><head><title>T</title></head><body></body></html>",
                               None, {})

    monkeypatch.setattr(pipeline_mod, "make_fetcher", lambda settings: FakeFetcher())
    monkeypatch.setattr(pipeline_mod, "fetch_robots", lambda *a: None)
    out_csv = tmp_path / "out.csv"
    settings = {"output": {"dir": str(tmp_path / "state-home")},
                "batch": {"workers": 1, "delay_s": 0, "max_consecutive_failures": 10}}
    assert run_batch(["https://example.test/1"], {}, settings, out_csv, tmp_path / "json") == 0
    saved = _load_state(tmp_path / "state-home" / "_state.json")
    assert "https://example.test/1" in saved and saved["https://example.test/1"]["hash"]


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

    fake_sql = types.SimpleNamespace(SQL=lambda text: text)
    fake_psycopg = types.SimpleNamespace(connect=lambda _url: FakeConn(), sql=fake_sql)
    monkeypatch.setitem(sys.modules, 'psycopg', fake_psycopg)
    assert migrate_db('postgresql://unused') == 1
    assert any('CREATE TABLE t1' in q for q in seen)
    assert any('schema_migrations' in q for q in seen)


def test_publish_snapshot_upserts_tours_and_offers(monkeypatch, tmp_path):
    import json as _json
    import sys as _sys
    import types as _types

    from ingest.pipeline import publish_snapshot

    detail = {'url': 'https://example.test/t', 'fetched_at': '2026-10-07T00:00:00+07:00', 'record_evidence': 'verified', 'record_missing': [], 'record': {'tour_name': 'T', 'price': 100, 'currency': 'VND', 'duration_days': 3, 'offers': [{'departure_date': '2026-11-18', 'price': 100, 'availability': 'available'}]}}
    (tmp_path / 'tour_x.json').write_text(_json.dumps(detail), encoding='utf-8')
    (tmp_path / 'notes.txt').write_text('ignore me', encoding='utf-8')
    seen = []

    class FakeCursor:
        def __enter__(self): return self
        def __exit__(self, *a): return None
        def execute(self, q, p=()): seen.append(q)
        def fetchone(self): return (7,)

    class FakeConn:
        def __enter__(self): return self
        def __exit__(self, *a): return None
        def cursor(self): return FakeCursor()
        def commit(self): pass

    monkeypatch.setitem(_sys.modules, 'psycopg',
                        _types.SimpleNamespace(connect=lambda _url: FakeConn()))
    monkeypatch.setattr('ingest.pipeline.tour_db_url', lambda: 'postgresql://unused')
    counts = publish_snapshot(tmp_path, 'dulichviet')
    assert counts == {'tours': 1, 'offers': 1, 'skipped': 0}
    assert any('INSERT INTO tours' in q for q in seen)
    assert any('INSERT INTO offers' in q for q in seen)
    assert any('INSERT INTO providers' in q for q in seen)
