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


def test_validate_public_url_can_enforce_full_origin_scope(monkeypatch):
    import ipaddress

    import ingest.fetch as fetch_mod
    from ingest.fetch import UnsafeURLError, validate_public_url

    monkeypatch.setattr(fetch_mod, "_cached_ips",
                        lambda host, ttl: [ipaddress.ip_address("8.8.8.8")])

    assert validate_public_url("https://example.test/a", "https://example.test")
    for url in ("http://example.test/a", "https://example.test:8443/a",
                "https://other.test/a"):
        try:
            validate_public_url(url, "https://example.test")
        except UnsafeURLError:
            pass
        else:
            raise AssertionError(f"accepted out-of-origin URL {url}")


def test_fetcher_bounds_gzip_expansion(monkeypatch):
    import gzip
    import ipaddress

    import ingest.fetch as fetch_mod
    from ingest.fetch import RateLimiter, SafeFetcher

    class Response:
        status = 200

        def __init__(self, body):
            self.body = body

        def read(self, _limit):
            return self.body

        def getheaders(self):
            return [("content-encoding", "gzip"), ("content-type", "text/html")]

    class Connection:
        def request(self, *_args, **_kwargs):
            pass

        def getresponse(self):
            return Response(gzip.compress(b"x" * 10_000))

    pool = {}
    monkeypatch.setattr(fetch_mod, "validate_public_url", lambda url, *_args: url)
    monkeypatch.setattr(fetch_mod, "_cached_ips",
                        lambda *_args: [ipaddress.ip_address("8.8.8.8")])
    monkeypatch.setattr(fetch_mod, "_pool", lambda: pool)
    monkeypatch.setattr(fetch_mod, "_dial", lambda *_args: Connection())
    fetcher = SafeFetcher(max_bytes=100, limiter=RateLimiter(0))

    result = fetcher._get("https://example.test/tour", {}, "https://example.test")

    assert result.error == "Response exceeds byte limit"


def test_fetch_robots_distinguishes_absent_policy_from_fetch_failure():
    from ingest.fetch import FetchResult, SafeFetcher, fetch_robots

    class FakeFetcher(SafeFetcher):
        def __init__(self, result):
            super().__init__()
            self.result = result

        def fetch(self, url, origin_host="", extra_headers=None):
            return self.result

    missing = fetch_robots(FakeFetcher(FetchResult("https://example.test/robots.txt", 404, "",
                                                   error="HTTP 404")),
                           "https://example.test", "example.test")
    assert missing is not None and missing.can_fetch("test-agent", "https://example.test/tour")
    failed = fetch_robots(FakeFetcher(FetchResult("https://example.test/robots.txt", 503, "",
                                                  error="HTTP 503")),
                           "https://example.test", "example.test")
    assert failed is None


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


def test_crawl_fields_isolates_a_raising_clean():
    from ingest.extract import apply_clean, crawl_fields, refindall, research

    assert research(r"(a)(b)", "xab", 2) == "b"
    assert research(r"zzz", "xab") == ""
    assert research(r"(a", "xab") == ""
    assert refindall(r"\d+", "a1b22") == ["1", "22"]
    assert refindall(r"zzz", "abc") == []
    assert apply_clean({"clean": "research(r'Price\\s*([\\d,]+)', str(val))"},
                       "Price 1,200 VND") == "1,200"

    html = "<html><body><h1>Tour A</h1></body></html>"
    profile = {"fields": {
        "good": {"source": "css", "selector": "h1"},
        "bad": {"source": "css", "selector": "h1", "clean": "1/0"},
        "ugly": {"source": "css", "selector": "h1",
                 "clean": "re.search(r'zzz', str(val)).group(1)"},
    }}
    row = crawl_fields(html, profile)
    assert row["good"] == "Tour A"
    assert row["bad"] == "" and row["ugly"] == ""


def test_read_done_retries_failures(tmp_path):
    import csv as _csv

    from ingest.pipeline import _read_done

    path = tmp_path / "t.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = _csv.DictWriter(handle, fieldnames=["url", "status"])
        writer.writeheader()
        writer.writerow({"url": "https://example.test/ok", "status": "ok"})
        writer.writerow({"url": "https://example.test/fail", "status": "fetch_fail"})
        writer.writerow({"url": "https://example.test/blocked", "status": "blocked"})
        writer.writerow({"url": "https://example.test/plain"})
    assert _read_done(path) == {"https://example.test/ok", "https://example.test/plain"}


def test_batch_resume_retries_failed_urls(tmp_path, monkeypatch):
    import csv as _csv

    import ingest.pipeline as pipeline_mod
    from ingest.pipeline import run_batch

    out_csv = tmp_path / "out.csv"
    with out_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = _csv.DictWriter(handle, fieldnames=["url", "status"])
        writer.writeheader()
        writer.writerow({"url": "https://example.test/done", "status": "ok"})
        writer.writerow({"url": "https://example.test/retry", "status": "fetch_fail"})

    calls: list[str] = []

    def fake_run_tour(url, profile, settings, out_dir, robots_cache=None,
                      conditional=None):
        calls.append(url)
        return {"url": url, "status": "ok", "title": "T", "departures": 0,
                "verified": 0, "notes_keys": "", "error": ""}

    monkeypatch.setattr(pipeline_mod, "run_tour", fake_run_tour)
    settings = {"output": {"dir": str(tmp_path)},
                "batch": {"workers": 1, "delay_s": 0, "max_consecutive_failures": 10}}
    assert run_batch(["https://example.test/done", "https://example.test/retry"],
                     {}, settings, out_csv, tmp_path / "json") == 0
    assert calls == ["https://example.test/retry"]


def test_cli_parses_args():
    from ingest.pipeline import _parse_args

    args = _parse_args(["https://example.test/t", "--profile", "dulichviet", "--limit", "5"])
    assert args.url.endswith("/t") and args.profile == "dulichviet" and args.limit == 5
    assert _parse_args(["--publish"]).publish == ""
    assert _parse_args(["--publish", "out"]).publish == "out"
    assert _parse_args(["--batch"]).batch == ""
    assert _parse_args(["--batch", "in.csv"]).batch == "in.csv"


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


def test_sitemap_reads_gzip_urlsets_with_output_size_cap():
    import gzip

    from ingest.fetch import FetchResult
    from ingest.pipeline import sitemap_urls

    xml = (b"<urlset><url><loc>https://example.test/du-lich-a</loc></url></urlset>")
    compressed = gzip.compress(xml)

    class FakeFetcher(SafeFetcher):
        def fetch(self, url, origin_host="", extra_headers=None):
            return FetchResult(url, 200, "application/gzip", compressed)

    assert sitemap_urls(FakeFetcher(), ["https://example.test/tours.xml.gz"],
                        ["/du-lich-"]) == ["https://example.test/du-lich-a"]


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


def test_batch_without_fresh_tours_does_not_burn_quality_baseline(tmp_path, monkeypatch):
    import json

    import ingest.pipeline as pipeline_mod
    from ingest.pipeline import run_batch

    settings = {"output": {"dir": str(tmp_path)}, "batch": {"workers": 1, "delay_s": 0}}
    out_csv = tmp_path / "out.csv"
    # utf-8-sig prepends the BOM; a literal \ufeff prefix would double it and
    # corrupt the header key for _read_done.
    out_csv.write_text("url\nhttps://example.test/1\n", encoding="utf-8-sig", newline="")
    source_dir = tmp_path / "s"
    quality_path = source_dir / "quality.json"
    baseline = json.dumps({
        "observed_at": "2026-10-17T10:21:04+07:00",
        "summary": {"tours": 37, "price_mean": 1.0, "fills": {}, "fallback_count": 0},
        "warnings": [],
    }, ensure_ascii=False)
    source_dir.mkdir(parents=True)
    quality_path.write_text(baseline, encoding="utf-8")

    calls: list[str] = []

    def boom(url, profile, settings, out_dir, robots_cache=None, state_entry=None):
        calls.append(url)
        return {"url": url, "status": "ok", "detail_file": ""}

    monkeypatch.setattr(pipeline_mod, "run_tour", boom)
    assert run_batch(["https://example.test/1"], {"name": "s"}, settings,
                     out_csv, tmp_path / "json") == 0
    assert calls == []  # resume skipped the done URL; nothing crawled
    assert quality_path.read_text(encoding="utf-8") == baseline  # baseline preserved


def test_batch_with_fresh_details_writes_quality(tmp_path, monkeypatch):
    import json

    import ingest.pipeline as pipeline_mod
    from ingest.pipeline import run_batch

    settings = {"output": {"dir": str(tmp_path)}, "batch": {"workers": 2, "delay_s": 0}}
    out_csv = tmp_path / "out.csv"
    detail_path = tmp_path / "json" / "d.json"
    detail_path.parent.mkdir(parents=True)
    detail_path.write_text(json.dumps({
        "record": {"tour_name": "Tour A", "price": 1500000, "currency": "VND",
                   "departure_city": "Sài Gòn"},
    }, ensure_ascii=False), encoding="utf-8")

    def fake_run_tour(url, profile, settings_, out_dir, robots_cache=None, state_entry=None):
        return {"url": url, "status": "ok", "detail_file": str(detail_path)}

    monkeypatch.setattr(pipeline_mod, "run_tour", fake_run_tour)
    monkeypatch.setattr(pipeline_mod, "fetch_robots", lambda *a: None)
    monkeypatch.setattr(pipeline_mod, "make_fetcher", lambda settings_: type(
        "F", (), {"fetch": staticmethod(lambda url, origin_host="", extra_headers=None: url)})())
    assert run_batch([f"https://example.test/{index}" for index in range(1, 3)],
                     {"name": "s", "flows": ["static"]}, settings, out_csv, tmp_path / "json") == 0
    snapshot = json.loads((tmp_path / "s" / "quality.json").read_text(encoding="utf-8"))
    assert snapshot["summary"]["tours"] == 2


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


def test_map_ordered_keeps_order_and_stops_early():
    import threading

    from ingest.pipeline import _map_ordered

    stop = threading.Event()
    assert list(_map_ordered(lambda u: str(u).upper(), ["b", "a"], 2, stop)) == [
        (0, "B"), (1, "A")]

    stopped = threading.Event()
    stopped.set()
    assert list(_map_ordered(lambda u: u, ["x"], 2, stopped)) == []

    assert list(_map_ordered(lambda u: 1 / 0, ["x"], 1, threading.Event())) == [
        (0, ZeroDivisionError)] or True
    outcomes = list(_map_ordered(lambda u: 1 / 0, ["x"], 1, threading.Event()))
    assert len(outcomes) == 1 and isinstance(outcomes[0][1], ZeroDivisionError)


def test_run_batch_saves_state_on_interrupt(tmp_path, monkeypatch):
    import pytest

    import ingest.pipeline as pipeline_mod
    from ingest.pipeline import _load_state, run_batch

    def fake_run_tour(url, profile, settings, out_dir, robots_cache=None,
                      conditional=None):
        if "boom" in url:
            raise KeyboardInterrupt()
        return {"url": url, "status": "ok", "title": "T", "departures": 0,
                "verified": 0, "notes_keys": "", "error": "",
                "_state_entry": {"hash": "h", "observed_at": "t",
                                 "etag": "", "last_modified": ""}}

    monkeypatch.setattr(pipeline_mod, "run_tour", fake_run_tour)
    out_csv = tmp_path / "out.csv"
    settings = {"output": {"dir": str(tmp_path / "home")},
                "batch": {"workers": 2, "delay_s": 0, "max_consecutive_failures": 10}}
    with pytest.raises(KeyboardInterrupt):
        run_batch(["https://example.test/1", "https://example.test/boom",
                   "https://example.test/3"], {}, settings, out_csv, tmp_path / "json")
    assert "https://example.test/1" in _load_state(tmp_path / "home" / "_state.json")





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


def test_quality_fallback_compare_and_batch_snapshot(tmp_path, monkeypatch):
    import json as _json

    import ingest.pipeline as pipeline_mod
    from ingest.pipeline import run_batch
    from ingest.quality import compare_quality, fallback_fields, summarize_details

    record = {'tour_name': 'T', 'price': 100, 'destinations': [], 'route': ''}
    assert fallback_fields(record) == ['destinations', 'route']
    summary = summarize_details([{'record': record}, {'record': {}}], ['tour_name', 'price'])
    assert summary['tours'] == 2 and summary['price_mean'] == 100
    assert summary['fill'] == {'tour_name': 0.5, 'price': 0.5}
    assert summary['fallback_total'] == 2
    cfg = {'min_tours_ratio': 0.8, 'max_price_shift': 0.3, 'min_fill_rate': 0.85}
    first = compare_quality(summary, {}, cfg)
    assert len(first) == 2 and all('fill' in w for w in first)
    prev = {'tours': 10, 'price_mean': 100.0, 'fill': {'tour_name': 1.0, 'price': 1.0}}
    warnings = compare_quality(summary, prev, cfg)
    assert any('tours 2 below' in w for w in warnings)
    assert any('fill tour_name 0.50 below' in w for w in warnings)
    assert compare_quality({'tours': 9, 'price_mean': 115.0, 'fill': {'tour_name': 1.0, 'price': 1.0}}, prev, cfg) == []

    detail = tmp_path / 'd.json'
    detail.write_text(_json.dumps({'record': {'tour_name': 'T', 'price': 100}}), encoding='utf-8')

    def fake_run_tour(url, profile, settings, out_dir, robots_cache=None, conditional=None):
        return {'url': url, 'status': 'ok', 'title': 'T', 'departures': 0,
                'verified': 0, 'notes_keys': '', 'error': '', 'detail_file': str(detail)}

    monkeypatch.setattr(pipeline_mod, 'run_tour', fake_run_tour)
    settings = {'output': {'dir': str(tmp_path / 'home')},
                'batch': {'workers': 1, 'delay_s': 0, 'max_consecutive_failures': 10}}
    assert run_batch(['https://example.test/1'], {'name': 's'}, settings,
                     tmp_path / 'out.csv', tmp_path / 'json') == 0
    snapshot = _json.loads((tmp_path / 'home' / 's' / 'quality.json').read_text(encoding='utf-8'))
    assert snapshot['summary']['tours'] == 1 and snapshot['warnings'] == []
    assert snapshot['observed_at'].endswith('+07:00')


def test_list_and_infer_profiles():
    from ingest.pipeline import infer_profile_for_url, list_profiles

    names = list_profiles()
    assert {"dulichviet", "vietravel", "saigontourist"} <= set(names)
    assert infer_profile_for_url("https://travel.com.vn/chuong-trinh/x-pid-1") == "vietravel"
    assert infer_profile_for_url("https://www.dulichviet.com.vn/du-lich-x") == "dulichviet"


def test_infer_profile_rejects_unknown_url():
    import pytest

    from ingest.pipeline import infer_profile_for_url

    with pytest.raises(ValueError, match="exactly one profile"):
        infer_profile_for_url("https://unknown.test/tour-1")


def test_all_mode_guards_need_single_profile():
    from ingest import pipeline as pipeline_mod

    assert pipeline_mod.main(["--discover", "--output", "x.csv"]) == 2
    assert pipeline_mod.main(["--batch", "some.csv"]) == 2
    assert pipeline_mod.main(["--publish", "some/dir"]) == 2
    assert pipeline_mod.main(["https://unknown.test/tour-1"]) == 2


def test_bare_publish_runs_all_profiles(monkeypatch, tmp_path):
    import ingest.pipeline as pipeline_mod

    published: list = []
    monkeypatch.setattr(pipeline_mod, "publish_snapshot",
                        lambda out_dir, profile: published.append(profile) or {"tours": 0})
    assert pipeline_mod.main(["--publish"]) == 0
    assert sorted(published) == ["dulichviet", "saigontourist", "vietravel", "viettourist"]

