"""Per-field extraction and source-semantic verification regressions."""

from __future__ import annotations

from ingest.extract import crawl_fields_detailed
from ingest.quality import verify_record_fields


def test_crawl_distinguishes_empty_locator_from_missing_selector_and_clean_error():
    html = "<h1>Tour A</h1><div class='empty'></div>"
    profile = {"fields": {
        "name": {"source": "css", "selector": "h1"},
        "blank": {"source": "css", "selector": ".empty"},
        "missing": {"source": "css", "selector": ".does-not-exist"},
        "broken": {"source": "css", "selector": "h1", "clean": "1 / 0"},
        "unpublished": {"status": "not_observed"},
    }}

    row, raw, states = crawl_fields_detailed(html, profile)

    assert row["name"] == "Tour A" and raw["name"] == "Tour A"
    assert states == {"name": "extracted", "blank": "source_empty",
                      "missing": "selector_missing", "broken": "clean_error",
                      "unpublished": "declared_not_observed"}


def test_verifier_checks_shape_and_reports_missing_extractor_separately():
    profile = {"fields": {
        "tour_name": {"source": "css", "selector": "h1"},
        "departure_city": {"source": "css", "selector": ".origin"},
        "destinations": {"source": "css", "selector": ".dest"},
        "duration_days": {"source": "css", "selector": ".days"},
        "price": {"source": "css", "selector": ".price"},
        "currency": {"source": "css", "selector": ".currency"},
        "itinerary": {"source": "css", "selector": ".itinerary"},
        "inclusions": {"source": "css", "selector": ".included"},
        "exclusions": {"source": "css", "selector": ".excluded"},
        "insurance": {"source": "css", "selector": ".insurance"},
    }}
    record = {"tour_name": "Tour A", "departure_city": "Hà Nội",
              "destinations": ["Hạ Long"], "duration_days": "3",
              "price": 2_000_000, "currency": "VND", "itinerary": "Ngày 1",
              "inclusions": "Ăn sáng", "exclusions": "Vé tham quan", "insurance": ""}
    raw = {"tour_name": "Tour A", "departure_city": "Hà Nội",
           "destinations": ["Hạ Long"], "duration_days": "3",
           "price": "2.000.000 VND", "currency": "VND",
           "itinerary": "Ngày 1", "inclusions": "Ăn sáng",
           "exclusions": "Vé tham quan", "insurance": ""}
    states = {key: "extracted" for key in record}
    states["insurance"] = "selector_missing"
    html = "<h1>Tour A</h1><span>Tour A is mentioned somewhere else</span>"

    verdict, missing, checks = verify_record_fields(record, raw, html, profile, states)

    assert verdict == "partial"
    assert "duration_days" in missing and "insurance" in missing
    assert checks["duration_days"]["reason"] == "expected_integer"
    assert checks["insurance"]["reason"] == "selector_missing"


def test_destination_split_requires_independent_source_place_evidence():
    profile = {"fields": {"destinations": {"source": "css", "selector": ".crumb"},
                          "route": {"source": "css", "selector": ".route"}}}
    record = {"destinations": ["Singapore – Malaysia"],
              "route": ["TP.HCM", "Singapore", "Kuala Lumpur"]}
    raw = {"destinations": "Singapore – Malaysia", "route": "TP.HCM - Singapore - Kuala Lumpur"}
    states = {"destinations": "extracted", "route": "extracted"}
    structured = [
        {"@type": "Country", "name": "Singapore"},
        {"@type": "Country", "name": "Malaysia"},
    ]

    _, missing, checks = verify_record_fields(record, raw, "", profile, states, structured)

    assert "destinations" in missing
    assert checks["destinations"]["reason"] == "composite_destination_split_is_source_confirmed"
    assert checks["route"]["status"] == "verified"


def test_hyphenated_place_name_is_not_split_automatically():
    profile = {"fields": {"destinations": {"source": "json_ld", "entity": "Place",
                                             "path": "name"}}}
    record = {"destinations": ["Baden-Baden"]}
    raw = {"destinations": ["Baden-Baden"]}
    states = {"destinations": "extracted"}
    structured = [{"@type": "Place", "name": "Baden-Baden"}]

    _, missing, checks = verify_record_fields(record, raw, "", profile, states, structured)

    assert "destinations" not in missing
    assert checks["destinations"]["status"] == "verified"


def test_destination_components_are_verified_by_authoritative_taxonomy():
    profile = {"fields": {"destinations": {
        "source": "css", "selector": ".route-label", "taxonomy_selector": ".destination-taxonomy a"}}}
    record = {"destinations": ["Singapore", "Malaysia"]}
    raw = {"destinations": "Singapore – Malaysia"}
    html = '''<nav class="destination-taxonomy"><a>Singapore</a><a>Malaysia</a></nav>'''

    _, missing, checks = verify_record_fields(
        record, raw, html, profile, {"destinations": "extracted"})

    assert "destinations" not in missing
    assert checks["destinations"]["details"]["confirmed_taxonomy"] == ["Singapore", "Malaysia"]


def test_field_values_must_match_their_source_and_route_order():
    profile = {"fields": {
        "tour_name": {"source": "css", "selector": "h1"},
        "price": {"source": "css", "selector": ".price"},
        "route": {"source": "css", "selector": ".route"},
    }}
    record = {"tour_name": "Different Tour", "price": 2_000_000,
              "route": ["Kuala Lumpur", "Singapore"]}
    raw = {"tour_name": "Tour A", "price": "1.000.000 VND",
           "route": "Singapore → Kuala Lumpur"}
    states = {field: "extracted" for field in record}

    _, missing, checks = verify_record_fields(record, raw, "", profile, states)

    assert {"tour_name", "price", "route"}.issubset(missing)
    assert checks["tour_name"]["reason"] == "cleaned_value_not_grounded_in_field_source"
    assert checks["price"]["reason"] == "numeric_value_not_grounded_in_field_source"
    assert checks["route"]["reason"] == "route_stop_not_grounded_or_order_changed"


def test_required_not_observed_fails_but_optional_declaration_is_distinct():
    profile = {"fields": {"tour_name": {"status": "not_observed"},
                          "departure_pattern": {"status": "not_observed"}}}
    states = {"tour_name": "declared_not_observed",
              "departure_pattern": "declared_not_observed"}

    _, missing, checks = verify_record_fields({}, {}, "", profile, states)

    assert "tour_name" in missing
    assert "departure_pattern" not in missing
    assert checks["tour_name"]["status"] == "not_observed"
    assert checks["departure_pattern"]["status"] == "not_observed"


def test_extract_all_cannot_pass_when_discovery_report_has_a_gap(tmp_path):
    import csv
    import json

    from ingest.extract import _self_test_all

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "tour-1.html").write_text("<h1>Tour</h1>", encoding="utf-8")
    with (raw_dir / "tour_pages.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["index", "url", "file", "status", "error"])
        writer.writeheader()
        writer.writerow({"index": 1, "url": "https://example.test/tour-1", "file": "tour-1.html",
                         "status": "ok", "error": ""})
    (raw_dir / "tour_urls.txt").write_text("https://example.test/tour-1\n", encoding="utf-8")
    (raw_dir / "survey_fetch_report.json").write_text(json.dumps({
        "discovered_unique": 1, "gaps": ["listing_page_cap:101>100"]
    }), encoding="utf-8")
    output = tmp_path / "selftest.jsonl"

    code = _self_test_all(raw_dir, output, {"fields": {}})

    summary = json.loads(output.with_suffix(".jsonl.summary.json").read_text(encoding="utf-8"))
    assert code == 1
    assert "listing_page_cap:101>100" in summary["gaps"]


def test_extract_all_passes_complete_inventory_with_verified_fields(tmp_path):
    import csv
    import json

    from ingest.extract import _self_test_all

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    url = "https://example.test/tour-a"
    body = '''<html><h1 class="name">Tour Đà Lạt</h1>
      <div class="origin">Hồ Chí Minh</div><div class="destination">Đà Lạt</div>
      <div class="days">3 ngày</div><div class="price">2.000.000</div>
      <div class="currency">VND</div><div class="itinerary">Ngày đầu</div>
      <div class="includes">Ăn sáng</div><div class="excludes">Vé riêng</div>
      <script type="application/ld+json">{"@type":"City","name":"Đà Lạt"}</script></html>'''
    filename = "tour-a.html"
    (raw_dir / filename).write_text(body, encoding="utf-8")
    with (raw_dir / "tour_pages.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["index", "url", "file", "status", "error"])
        writer.writeheader()
        writer.writerow({"index": 1, "url": url, "file": filename, "status": "ok", "error": ""})
    (raw_dir / "tour_urls.txt").write_text(url + "\n", encoding="utf-8")
    (raw_dir / "survey_fetch_report.json").write_text(json.dumps({
        "discovered_unique": 1, "gaps": []
    }), encoding="utf-8")
    profile = {"fields": {
        "tour_name": {"source": "css", "selector": ".name"},
        "departure_city": {"source": "css", "selector": ".origin"},
        "destinations": {"source": "css", "selector": ".destination", "transform": "single_list"},
        "duration_days": {"source": "css", "selector": ".days", "clean": "int(re.sub(r'\\D', '', str(val)))"},
        "price": {"source": "css", "selector": ".price", "clean": "int(re.sub(r'\\D', '', str(val)))"},
        "currency": {"source": "css", "selector": ".currency"},
        "itinerary": {"source": "css", "selector": ".itinerary"},
        "inclusions": {"source": "css", "selector": ".includes"},
        "exclusions": {"source": "css", "selector": ".excludes"},
    }}
    output = tmp_path / "selftest.jsonl"

    code = _self_test_all(raw_dir, output, profile)

    summary = json.loads(output.with_suffix(".jsonl.summary.json").read_text(encoding="utf-8"))
    result = json.loads(output.read_text(encoding="utf-8"))
    assert code == 0
    assert summary["discovered"] == summary["checked"] == 1
    assert all(check["status"] == "verified" for check in result["record_field_checks"].values())
