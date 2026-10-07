"""Offline tests for tourcrawl blocks/clean/validate. No network, no browser."""

import re

from tourcrawl import blocks, clean, validate
from tourcrawl.fetch import UnsafeURLError, validate_public_url

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


def test_blocks_parse_json_ld_and_embedded_object():
    nodes = blocks.parse_json_ld(FIXTURE_HTML)
    assert nodes[0]["sku"] == "ABC"
    assert nodes[0]["offers"]["priceCurrency"] == "VND"
    assert blocks.parse_embedded_object(FIXTURE_HTML, "tourInfoData") == {
        "dayStayText": "7N6Đ", "departureName": "TP. Ho Chi Minh"}


def test_blocks_balanced_slice_respects_escapes():
    text = '{"a": "x\\"y { not a brace}", "b": {"c": 1}} trailing'
    assert blocks.balanced_slice(text, 0) == text[: text.rindex("}") + 1]


def test_blocks_sections_by_id_with_heading_fallback():
    anchors = {"schedule": ["sec-schedule"], "missing": ["sec-nope"]}
    out = blocks.parse_sections(FIXTURE_HTML, anchors)
    assert "Lịch khởi hành" in out["schedule"]
    assert out["missing"] == ""


def test_blocks_itinerary_prefers_details_element():
    html = ('<h3>Ngày 1: Go</h3>'
            '<details><summary><h3>Ngày 1: Go</h3></summary><p>Do things</p></details>')
    days = blocks.parse_itinerary_days(html)
    assert days and days[0]["day"].startswith("Ngày 1")
    assert "Do things" in days[0]["detail"]


def test_blocks_walk_departures_keeps_containers():
    found = []
    blocks.walk_departures({"a": {"departureDate": "2026-10-04", "flights": ["VN1"]}}, found)
    assert found == [{"departureDate": "2026-10-04", "flights": ["VN1"]}]


def test_clean_drops_technical_fields_keeps_decision_fields():
    keep = re.compile(r"(code|date|price|name)$", re.I)
    dep = {"tourCode": "X1", "price": 100, "thumbnail": "u", "guid": "8e9fa47a-caa2-efce-3456-3a21bc4f10dd",
           "nothing": None, "note": "short"}
    from tourcrawl.clean import filter_dep
    out = filter_dep(dep, {"thumbnail"}, keep)
    assert out == {"tourCode": "X1", "price": 100}


def test_clean_dedupes_identical_values_to_shared():
    from tourcrawl.clean import dedupe_departures
    deps = [{"date": "d1", "hotel": "H", "price": 1}, {"date": "d2", "hotel": "H", "price": 2}]
    trimmed, shared = dedupe_departures(deps)
    assert shared == {"hotel": "H"}
    assert all("hotel" not in dep for dep in trimmed)


def test_clean_prose_keeps_headings_drops_code_and_cloud():
    cloud = ",".join(f'"Tag {i}"' for i in range(30))
    sample = ('self.__next_f.push([1,"Giá tour bao gồm","Giá tour","' + cloud + '",'
              '"Hộ chiếu của quý khách phải còn thời hạn trên 6 tháng quy định"]])')
    out = clean.clean_prose(sample)
    assert "Giá tour bao gồm" in out and "Hộ chiếu" in out
    assert "Tag 29" not in out and "__next_f" not in out


def test_clean_extract_notes_by_semantic_keys():
    from tourcrawl.clean import extract_notes
    payloads = [{"infoInclude": "Visa fee and airport tax included here for real Dao",
                 "groupItems": [{"description": "x" * 600}]}]
    notes = extract_notes(payloads, "includ|exclud|condition")
    assert "infoInclude" in notes and "groupItems" not in notes


def test_validate_strict_accepts_verbatim_rejects_slug_guess():
    context = "Tour 7N6Đ price 168000000 VND"
    payload = {
        "duration": {"value": "7 ngày 6 đêm", "evidence_quote": "7N6Đ"},
        "price": {"value": "168000000", "evidence_quote": "168000000"},
        "tour_code": {"value": "14112", "evidence_quote": "pid-14112"},
    }
    report = validate.validate_fields(payload, ["duration", "price", "tour_code"], context,
                                      strict={"duration", "price", "tour_code"})
    assert report.fields["duration"]["value"] == "7 ngày 6 đêm"
    assert report.fields["tour_code"] == {"value": None, "evidence_quote": None}
    assert report.dropped == ["tour_code"]
    assert report.populated == "2/3"


def test_validate_fuzzy_accepts_descriptive_and_truncates():
    payload = {"itinerary": {"value": "x" * 500, "evidence_quote": "beaches Da Nang ancient town"}}
    report = validate.validate_fields(payload, ["itinerary"],
                                      "beautiful beaches of Da Nang and ancient town",
                                      strict=set())
    assert report.fields["itinerary"]["value"] == "x" * 400
    assert report.evidence_match == "1/1"


def test_profiles_load_and_reject_bad(tmp_path):
    from tourcrawl.profiles import load_profile, load_settings

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
    from tourcrawl.fetch import RateLimiter, SafeFetcher

    fetcher = SafeFetcher(limiter=RateLimiter(delay=0))
    result = fetcher.fetch("http://127.0.0.1/x")
    assert result.status_code == 0 and result.error
    assert fetcher.requests_made == 0


def test_departure_evidence_grades():
    from tourcrawl.validate import departure_evidence

    dep = {"tourCode": "X1", "salePrice": 100, "departureDate": "2026-10-04"}
    assert departure_evidence(dep, "X1 100 2026-10-04 here") == "verified"
    assert departure_evidence(dep, "only X1 here") == "partial"
    assert departure_evidence(dep, "nothing relevant") == "unverified"
    assert departure_evidence({}, "anything") == "unverified"


def test_cli_parses_args():
    from tourcrawl.cli import _parse_args

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


def test_sections_fall_back_to_heading_keywords():
    html = "<h2>Ngày khởi hành X</h2><p>01/01/2027</p><h2>Mục khác</h2><p>zzz</p>"
    out = blocks.parse_sections(html, {"schedule": ["sec-nope"]},
                                {"schedule": ["ngày khởi hành"]})
    assert "01/01/2027" in out["schedule"]


def test_run_batch_respects_out_dir(tmp_path, monkeypatch):
    import tourcrawl.pipeline as pipeline_mod
    from tourcrawl.pipeline import run_batch

    calls = []

    def fake_run_tour(url, profile, settings, out_dir):
        calls.append(out_dir)
        return {"url": url, "status": "ok", "title": "T", "departures": 0,
                "verified": 0, "notes_keys": "", "error": ""}

    monkeypatch.setattr(pipeline_mod, "run_tour", fake_run_tour)
    out_csv = tmp_path / "out.csv"
    out_json = tmp_path / "json"
    assert run_batch(["https://example.test/1"], {}, {}, out_csv, out_json) == 0
    assert calls == [out_json]
    assert out_csv.exists()


def test_compile_keep_is_case_insensitive_regression():
    from tourcrawl.clean import compile_keep, filter_dep

    keep = compile_keep(["(code|date|price)$"])
    out = filter_dep({"tourCode": "X1", "departureDate": "2026-10-04", "salePrice": 100,
                      "priority": 1}, set(), keep)
    assert out == {"tourCode": "X1", "departureDate": "2026-10-04", "salePrice": 100}


def test_blocks_panel_detail_parses_flights_tiers_meeting():
    segment = "\n".join([
        "Thông tin tour:", "Ngày đi:", "25/10/2026", "VN112", "08:00", "09:20",
        "Người lớn", "(Từ 12 tuổi trở lên)", "3,890,000₫",
        "Phụ thu phòng đơn", "1,100,000₫",
        "Địa điểm tập trung:", "06:00 Sáng tại nhà ga T3",
    ])
    detail = blocks.parse_panel_detail(segment)
    assert detail["flights"] == ["VN112"]
    assert "08:00" in detail["flight_times"] and "09:20" in detail["flight_times"]
    assert {"label": "Người lớn (Từ 12 tuổi trở lên)", "price": 3890000} in detail["tiered_prices"]
    assert detail["meeting_point"].startswith("06:00 Sáng")


def test_blocks_panel_tier_ignores_bare_vietnamese_d():
    detail = blocks.parse_panel_detail("Ghi chú\n(Từ 5 đến 11 tuổi)\nKhông có giá ở đây")
    assert "tiered_prices" not in detail


def test_blocks_snapshots_attribute_by_click_not_dates():
    snapshots = [("25/10/2026", "<html><body><p>Thông tin tour:</p><p>VN112</p></body></html>"),
                 ("01/11/2026", "<html><body><p>Nothing relevant here</p></body></html>")]
    panels = blocks.parse_snapshots(snapshots)
    assert set(panels) == {"25/10/2026"}
    assert panels["25/10/2026"]["flights"] == ["VN112"]
    assert blocks.iso_to_dmy("2026-10-25T08:00:00") == "25/10/2026"
    assert blocks.iso_to_dmy(None) == ""


def test_blocks_fallback_segments_joined_text_by_date():
    text = ("04/10/2026\nMã tour:\nAAA\n3,990,000₫\nChọn\n"
            "25/10/2026\nThông tin tour:\nVN112\n3,890,000₫\nNhững thông tin cần lưu ý")
    detail = blocks.parse_fallback(text, "25/10/2026", "FESGN302-008-251026VN-V-7")
    assert detail["flights"] == ["VN112"]
    assert {"label": "VN112", "price": 3890000} in [
        {"label": t["label"], "price": t["price"]} for t in detail["tiered_prices"]]
    assert blocks.parse_fallback("no dates here", "25/10/2026", "X") == {}
