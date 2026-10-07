"""Offline tests for ingest.dsl strict profile extraction. No network, no browser."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from ingest.extract import crawl_fields, extract_api_field, extract_field, same_origin_getter

HTML_SAMPLE = """<!DOCTYPE html>
<html>
<head>
    <script type="application/ld+json">
    {
        "@type": "TouristTrip",
        "name": "Tour Ha Giang 3N2D",
        "offers": {"price": 2500000, "priceCurrency": "VND"}
    }
    </script>
</head>
<body>
    <h1 class="tour-title">Tour Ha Giang 3N2D Sieu Dep</h1>
    <div class="meta">
        <span>Thoi gian:</span>
        <span class="val">3 ngay 2 dem</span>
    </div>
    <h2>Lich trinh</h2>
    <p>Ngay 1: Ha Noi - Ha Giang</p>
    <p>Ngay 2: Dong Van - Meo Vac</p>
    <h2>Gia tour bao gom</h2>
    <p>Xe du lich chat luong cao</p>
</body>
</html>
"""


def test_extract_field_json_ld():
    soup = BeautifulSoup(HTML_SAMPLE, "html.parser")
    json_ld = [{"@type": "TouristTrip", "name": "Tour Ha Giang 3N2D", "offers": {"price": 2500000}}]

    assert extract_field(soup, json_ld, {"source": "json_ld", "entity": "TouristTrip", "path": "name"}) == "Tour Ha Giang 3N2D"
    assert extract_field(soup, json_ld, {"source": "json_ld", "path": "offers.price", "transform": "int"}) == 2500000


def test_extract_field_css():
    soup = BeautifulSoup(HTML_SAMPLE, "html.parser")
    assert extract_field(soup, [], {"source": "css", "selector": "h1.tour-title"}) == "Tour Ha Giang 3N2D Sieu Dep"


def test_extract_field_label_sibling():
    soup = BeautifulSoup(HTML_SAMPLE, "html.parser")
    rule = {"source": "label_sibling", "label": "Thoi gian:", "transform": "regex", "pattern": r"(\d+)\s*ngay"}
    assert extract_field(soup, [], rule) == "3"


def test_extract_field_section():
    soup = BeautifulSoup(HTML_SAMPLE, "html.parser")
    rule = {"source": "section", "start_label": "Lich trinh", "stop_labels": ["Gia tour bao gom"]}
    val = extract_field(soup, [], rule)
    assert "Ha Noi - Ha Giang" in val
    assert "Dong Van - Meo Vac" in val
    assert "Xe du lich" not in val


def test_extract_field_clean_expression():
    soup = BeautifulSoup(HTML_SAMPLE, "html.parser")
    rule = {"source": "css", "selector": "h1.tour-title", "clean": "val.split()[0].upper()"}
    assert extract_field(soup, [], rule) == "TOUR"


def test_extract_field_not_observed_returns_none():
    soup = BeautifulSoup(HTML_SAMPLE, "html.parser")
    assert extract_field(soup, [], {"source": "css", "selector": "h1", "status": "not_observed"}) is None


def test_extract_api_field_uses_stub_fetcher():
    payload = {"data": {"departures": [
        {"date": "2026-11-18", "p": "8,590,000"},
        {"date": "2026-11-21", "p": "8,990,000"},
    ]}}
    rule = {
        "source": "api",
        "url": "https://example.test/api?code={tour_code}",
        "path": "data.departures",
        "clean": "[{'departure_date': d['date'], 'price': int(d['p'].replace(',', ''))} for d in val]",
    }
    val = extract_api_field(rule, {"tour_code": "ABC123"}, lambda _url: payload)
    assert val == [
        {"departure_date": "2026-11-18", "price": 8590000},
        {"departure_date": "2026-11-21", "price": 8990000},
    ]


def test_extract_api_field_missing_placeholder_returns_none():
    rule = {"source": "api", "url": "https://example.test/api?code={tour_code}", "path": "a"}
    assert extract_api_field(rule, {"url": "https://example.test/tour-1"}, lambda _url: {}) is None


def test_same_origin_getter_refuses_cross_origin():
    class FakeFetcher:
        def fetch(self, url, origin):
            raise AssertionError("must not fetch cross-origin")

    getter = same_origin_getter("https://example.test/tour-1", FakeFetcher())
    with pytest.raises(OSError, match="cross-origin"):
        getter("https://evil.test/api")


def test_crawl_fields_full_row_with_deferred_api():
    profile = {
        "fields": {
            "tour_name": {"source": "json_ld", "path": "name"},
            "price": {"source": "json_ld", "path": "offers.price", "transform": "int"},
            "duration_days": {
                "source": "label_sibling",
                "label": "Thoi gian:",
                "transform": "regex",
                "pattern": r"(\d+)\s*ngay",
            },
            "itinerary": {
                "source": "section",
                "start_label": "Lich trinh",
                "stop_labels": ["Gia tour bao gom"],
            },
            "offers": {"source": "api", "url": "https://example.test/api", "path": "offers"},
        }
    }
    row = crawl_fields(
        HTML_SAMPLE, profile,
        lambda _url: {"offers": [{"departure_date": "2026-11-18", "price": 8590000}]},
    )
    assert row["tour_name"] == "Tour Ha Giang 3N2D"
    assert row["price"] == 2500000
    assert row["duration_days"] == "3"
    assert "Ha Noi - Ha Giang" in row["itinerary"]
    assert row["offers"] == [{"departure_date": "2026-11-18", "price": 8590000}]


def test_crawl_fields_api_empty_without_fetcher():
    profile = {"fields": {"offers": {"source": "api", "url": "https://example.test/api", "path": "offers"}}}
    assert crawl_fields(HTML_SAMPLE, profile) == {"offers": ""}


def test_crawl_fields_json_round_trip(tmp_path: Path):
    profile = {
        "fields": {
            "tour_name": {"source": "css", "selector": "h1.tour-title"},
            "price": {"source": "json_ld", "path": "offers.price"},
        }
    }
    row = crawl_fields(HTML_SAMPLE, profile)
    out = tmp_path / "row.json"
    out.write_text(json.dumps(row, ensure_ascii=False), encoding="utf-8")
    assert json.loads(out.read_text(encoding="utf-8"))["tour_name"] == "Tour Ha Giang 3N2D Sieu Dep"
