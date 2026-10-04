"""Tests for scripts/crawl_with_profile.py runner."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from bs4 import BeautifulSoup

_script = Path(__file__).resolve().parents[1] / "scripts" / "crawl_with_profile.py"
_spec = importlib.util.spec_from_file_location("crawl_with_profile", _script)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Cannot load {_script}")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

crawl_tour = _mod.crawl_tour
extract_field = _mod.extract_field

HTML_SAMPLE = """<!DOCTYPE html>
<html>
<head>
    <script type="application/ld+json">
    {
        "@type": "TouristTrip",
        "name": "Tour Hà Giang 3N2Đ",
        "offers": {"price": 2500000, "priceCurrency": "VND"}
    }
    </script>
</head>
<body>
    <h1 class="tour-title">Tour Hà Giang 3N2Đ Siêu Đẹp</h1>
    <div class="meta">
        <span>Thời gian:</span>
        <span class="val">3 ngày 2 đêm</span>
    </div>
    <h2>Lịch trình</h2>
    <p>Ngày 1: Hà Nội - Hà Giang</p>
    <p>Ngày 2: Đồng Văn - Mèo Vạc</p>
    <h2>Giá tour bao gồm</h2>
    <p>Xe du lịch chất lượng cao</p>
</body>
</html>
"""


def test_extract_field_json_ld():
    soup = BeautifulSoup(HTML_SAMPLE, "html.parser")
    json_ld = [{"@type": "TouristTrip", "name": "Tour Hà Giang 3N2Đ", "offers": {"price": 2500000}}]
    
    rule_name = {"source": "json_ld", "entity": "TouristTrip", "path": "name"}
    assert extract_field(soup, json_ld, rule_name) == "Tour Hà Giang 3N2Đ"

    rule_price = {"source": "json_ld", "path": "offers.price", "transform": "int"}
    assert extract_field(soup, json_ld, rule_price) == 2500000


def test_extract_field_css():
    soup = BeautifulSoup(HTML_SAMPLE, "html.parser")
    rule = {"source": "css", "selector": "h1.tour-title"}
    assert extract_field(soup, [], rule) == "Tour Hà Giang 3N2Đ Siêu Đẹp"


def test_extract_field_label_sibling():
    soup = BeautifulSoup(HTML_SAMPLE, "html.parser")
    rule = {
        "source": "label_sibling",
        "label": "Thời gian:",
        "transform": "regex",
        "pattern": r"(\d+)\s*ngày",
    }
    assert extract_field(soup, [], rule) == "3"


def test_extract_field_section():
    soup = BeautifulSoup(HTML_SAMPLE, "html.parser")
    rule = {
        "source": "section",
        "start_label": "Lịch trình",
        "stop_labels": ["Giá tour bao gồm"],
    }
    val = extract_field(soup, [], rule)
    assert "Hà Nội - Hà Giang" in val
    assert "Đồng Văn - Mèo Vạc" in val
    assert "Xe du lịch" not in val


def test_crawl_tour_offline(tmp_path: Path):
    html_file = tmp_path / "tour.html"
    html_file.write_text(HTML_SAMPLE, encoding="utf-8")

    profile = {
        "fields": {
            "tour_name": {"source": "json_ld", "path": "name"},
            "price": {"source": "json_ld", "path": "offers.price", "transform": "int"},
            "duration_days": {
                "source": "label_sibling",
                "label": "Thời gian:",
                "transform": "regex",
                "pattern": r"(\d+)\s*ngày",
            },
            "itinerary": {
                "source": "section",
                "start_label": "Lịch trình",
                "stop_labels": ["Giá tour bao gồm"],
            },
        }
    }

    row = crawl_tour(str(html_file), profile)
    assert row["tour_name"] == "Tour Hà Giang 3N2Đ"
    assert row["price"] == 2500000
    assert row["duration_days"] == "3"
    assert "Ngày 1: Hà Nội - Hà Giang" in row["itinerary"]


def test_crawl_tour_render_flow(tmp_path: Path, monkeypatch):
    """Test that render: true triggers playwright branch."""
    class FakePage:
        def goto(self, url, wait_until, timeout):
            pass
        def content(self):
            return "<html><body><h1>Rendered Title</h1></body></html>"

    class FakeBrowser:
        def new_page(self):
            return FakePage()

    class FakeChromium:
        def launch(self, headless=True):
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    import playwright.sync_api
    monkeypatch.setattr(playwright.sync_api, "sync_playwright", lambda: FakePlaywright())

    profile = {
        "render": True,
        "fields": {"tour_name": {"source": "css", "selector": "h1"}},
    }
    row = crawl_tour("https://example.test/tour-1", profile)
    assert row["tour_name"] == "Rendered Title"


def test_extract_field_clean_expression():
    soup = BeautifulSoup(HTML_SAMPLE, "html.parser")
    rule = {
        "source": "css",
        "selector": "h1.tour-title",
        "clean": "val.split()[0].upper()",
    }
    assert extract_field(soup, [], rule) == "TOUR"


def test_extract_api_field_from_file_uri(tmp_path: Path):
    payload = {"data": {"departures": [
        {"date": "2026-11-18", "p": "8,590,000"},
        {"date": "2026-11-21", "p": "8,990,000"},
    ]}}
    api_file = tmp_path / "api.json"
    api_file.write_text(json.dumps(payload), encoding="utf-8")
    rule = {
        "source": "api",
        "url": api_file.as_uri(),
        "path": "data.departures",
        "clean": "[{'departure_date': d['date'], 'price': int(d['p'].replace(',', ''))} for d in val]",
    }
    val = _mod.extract_api_field(rule, {"url": "https://example.test/tour-1", "tour_code": "ABC123"})
    assert val == [
        {"departure_date": "2026-11-18", "price": 8590000},
        {"departure_date": "2026-11-21", "price": 8990000},
    ]


def test_extract_api_field_missing_placeholder_returns_none():
    rule = {"source": "api", "url": "https://example.test/api?code={tour_code}", "path": "a"}
    assert _mod.extract_api_field(rule, {"url": "https://example.test/tour-1"}) is None


def test_crawl_tour_api_deferred_until_other_fields(tmp_path: Path):
    html_file = tmp_path / "tour.html"
    html_file.write_text(HTML_SAMPLE, encoding="utf-8")
    api_file = tmp_path / "api.json"
    api_file.write_text(json.dumps(
        {"offers": [{"departure_date": "2026-11-18", "price": 8590000}]}), encoding="utf-8")
    profile = {
        "fields": {
            "offers": {"source": "api", "url": api_file.as_uri(), "path": "offers"},
            "tour_code": {"source": "css", "selector": "h1.tour-title", "clean": "'ABC123'"},
        }
    }
    row = crawl_tour(str(html_file), profile)
    assert row["tour_code"] == "ABC123"
    assert row["offers"] == [{"departure_date": "2026-11-18", "price": 8590000}]


def test_main_jsonl_output(tmp_path: Path):
    html_file = tmp_path / "tour.html"
    html_file.write_text(HTML_SAMPLE, encoding="utf-8")
    profile_file = tmp_path / "profile.yaml"
    profile_file.write_text("""
origin: https://example.test
fields:
  tour_name:
    source: css
    selector: h1.tour-title
  destinations:
    source: css
    selector: h1.tour-title
    clean: "['Hà Giang']"
  price:
    source: json_ld
    path: offers.price
""", encoding="utf-8")
    out_file = tmp_path / "tours.jsonl"
    _mod.main([str(html_file), "--profile", str(profile_file), "-o", str(out_file)])
    
    lines = out_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    import json
    data = json.loads(lines[0])
    assert data["tour_name"] == "Tour Hà Giang 3N2Đ Siêu Đẹp"
    assert data["destinations"] == ["Hà Giang"]
    assert data["price"] == 2500000


