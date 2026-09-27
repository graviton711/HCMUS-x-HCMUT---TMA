from pathlib import Path

from crawler.parser import (
    contact_values,
    extract_tour_fields,
    organization_observations,
    parse_html,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_parser_extracts_metadata_links_scripts_and_json_ld():
    html = """<!doctype html><html><head>
      <title>Example Tours</title>
      <meta property="og:site_name" content="Example Travel">
      <meta name="description" content="Tours in Vietnam">
      <link rel="canonical" href="https://example.test/">
      <script type="application/ld+json">{"@type":"TravelAgency","name":"Example Tours","legalName":"Example Travel JSC"}</script>
      <script>const endpoint = "/api/public/tours";</script>
      <script src="/assets/site.js"></script>
    </head><body><a href="/gioi-thieu">Giới thiệu</a>
      <a href="mailto:hello@example.test">Email</a><a href="tel:+84281234567">Phone</a>
      <p>Unlinked email: noise@example.test; registration: 0310891532</p></body></html>""".encode()

    page = parse_html("https://example.test/", html, "text/html; charset=utf-8")

    assert page.title == "Example Tours"
    assert page.metadata["og:site_name"] == "Example Travel"
    assert page.metadata["canonical"] == "https://example.test/"
    assert page.links[0].url == "https://example.test/gioi-thieu"
    assert page.links[0].text == "Giới thiệu"
    assert page.scripts == ["https://example.test/assets/site.js"]
    assert "/api/public/tours" in page.inline_scripts[0]
    observations = organization_observations(page.json_ld)
    assert observations["display_name"][0].value == "Example Tours"
    assert observations["legal_name"][0].value == "Example Travel JSC"
    assert contact_values(page)[0] == ["hello@example.test"]
    assert contact_values(page)[1] == ["+84281234567"]


def test_organization_observations_keep_structured_paths_and_contactpoint_fields():
    page = parse_html(
        "https://example.test/",
        b'''<script type="application/ld+json">{"@graph":[{"@type":"TravelAgency",
        "name":"Example Travel","address":{"@type":"PostalAddress",
        "streetAddress":"1 Main St","addressLocality":"Hanoi"},
        "contactPoint":{"@type":"ContactPoint","telephone":"+84281234567"},
        "hasCredential":{"@type":"EducationalOccupationalCredential",
        "name":"International travel license","identifier":"LIC-42"}}]}</script>''',
    )

    observations = organization_observations(page.json_ld)

    assert observations["display_name"][0].value == "Example Travel"
    assert observations["address"][0].value == "1 Main St, Hanoi"
    assert observations["phone"][0].value == "+84281234567"
    assert observations["license_claims"][0].value["identifier"] == "LIC-42"
    assert observations["address"][0].path.endswith("/address")
    assert observations["phone"][0].path.endswith("/contactPoint/telephone")


def test_parser_ignores_script_and_style_text_as_visible_content():
    page = parse_html(
        "https://example.test/",
        b"<html><body><script>fake@example.test</script><style>noise</style><p>Visible</p></body></html>",
    )

    assert page.text == "Visible"
    assert not contact_values(page)[0]


def test_parser_ignores_meta_without_name_property_or_itemprop():
    page = parse_html(
        "https://example.test/",
        b'<html><head><meta content="decorative"><meta name="description" content="Tours"></head></html>',
    )

    assert page.metadata == {"description": "Tours"}


def test_tour_parser_extracts_jsonld_and_ignores_noisy_visible_text():
    url = "https://www.saigontourist.net/tour/ha-noi-yen-tu-du-thuyen-cao-cap-halong-quang-yen"
    page = parse_html(url, (FIXTURE_DIR / "saigontourist_tour.html").read_bytes())

    fields = extract_tour_fields(page)

    assert fields["title"].value == "Hà Nội - Yên Tử - Du Thuyền Cao Cấp Hạ Long - Quảng Yên"
    assert fields["description"].value.startswith("Tham quan Hà Nội")
    assert fields["duration"].value == "4 ngày 3 đêm"
    assert fields["departure_city"].value == "TP Hồ Chí Minh"
    assert fields["transport"].value == "Vietnam Airlines"
    assert fields["price_options"].value[0] == {
        "name": "STN084-2026-03036",
        "sku": "STN084-2026-03036",
        "price": 12379000,
        "price_currency": "VND",
        "availability": "https://schema.org/InStock",
        "valid_from": "2026-10-17T00:00:00.000Z",
        "url": url,
    }
    assert "tour_code" not in fields  # Product.sku is the URL slug, not a tour code.
    assert "included" not in fields  # No structured source; do not infer from visible text.
    assert fields["departure_city"].evidence[0].url == page.url
    assert fields["departure_city"].evidence[0].method == "json_ld"
    assert fields["departure_city"].evidence[0].json_path.endswith(
        "/@graph/1/additionalProperty/2/value"
    )
    assert fields["price_options"].evidence[0].json_path.endswith("/offers/offers/0")


def test_tour_parser_does_not_fall_back_to_flattened_text_matching():
    page = parse_html(
        "https://example.test/tour/sample",
        """<html><body><nav>Khởi hành từ: Liên hệ Trang chủ Tour</nav>
        <p>Mã tour: WRONG. Thời gian: 2 ngày. Ngày khởi hành: 12/10/2026.</p>
        </body></html>""".encode(),
    )

    assert extract_tour_fields(page) == {}


def test_tour_parser_preserves_aggregate_offer_when_departure_offers_are_not_listed():
    page = parse_html(
        "https://example.test/tour/sample",
        b'''<script type="application/ld+json">
        {"@type":"Product","name":"Sample tour","offers":{
          "@type":"AggregateOffer","lowPrice":100,"highPrice":200,
          "priceCurrency":"VND","offerCount":3}}
        </script>''',
    )

    fields = extract_tour_fields(page)

    assert fields["price_options"].value == [
        {"low_price": 100, "high_price": 200, "offer_count": 3, "price_currency": "VND"}
    ]
