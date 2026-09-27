from urllib.parse import urlsplit, urlunsplit

from crawler.engine import Crawler, CrawlOptions, _is_tour_detail_url
from crawler.fetch import FetchResult
from crawler.models import CrawlReport
from crawler.safety import UnsafeURLError

BASE = "https://example.test"


def test_tour_detail_detection_rejects_category_listing_urls():
    assert not _is_tour_detail_url("https://dulichviet.com.vn/tour-trong-ngay")
    assert _is_tour_detail_url("https://dulichviet.com.vn/du-lich-trong-nuoc/tour-dong-bac-4n3d")


class FakeFetcher:
    def __init__(self, pages):
        self.pages = pages
        self.visited = []

    def fetch(self, url, origin):
        self.visited.append(url)
        return self.pages.get(url, FetchResult(url, 404, "text/plain", b"", "HTTP 404"))


def _allow_test_hosts(monkeypatch):
    def validate(url, expected_origin=None):
        parts = urlsplit(url)
        origin = (parts.scheme, (parts.hostname or "").lower(), parts.port or 443)
        if expected_origin is not None and origin != expected_origin:
            raise UnsafeURLError("Cross-origin test URL")
        return urlunsplit((parts.scheme, parts.netloc, parts.path or "/", parts.query, ""))

    monkeypatch.setattr("crawler.engine.validate_public_url", validate)


def test_crawl_returns_evidence_backed_profile_and_capability_report(monkeypatch):
    _allow_test_hosts(monkeypatch)
    robots = b"User-agent: *\nAllow: /\n"
    home = """<html><head><title>Example Tours</title>
      <meta property="og:site_name" content="Fallback Metadata Name">
      <meta name="description" content="Adventure trips">
      <script type="application/ld+json">{"@type":"TravelAgency","name":"Example Tours","legalName":"Example Travel JSC"}</script>
      <script>const endpoint = "/api/public/tours";</script>
      <script src="/assets/site.js"></script></head><body>
      <a href="/gioi-thieu">Giới thiệu</a><a href="/tour/tam-dao">Tour Tam Dao</a>
      <a href="mailto:hello@example.test">Email</a><a href="tel:02812345678">Phone</a>
      <p>Unlinked contact noise@example.test - registration 0310891532</p></body></html>""".encode()
    about = """<html><body><h1>Về chúng tôi</h1>
      <p>Giấy phép lữ hành quốc tế số 79-123/2025/TCDL-GP LHQT</p></body></html>""".encode()
    tour = """<html><head><title>Tour Tam Dao</title></head><body>
      <nav>Khởi hành từ: Liên hệ Trang chủ Tour trong nước</nav>
      <script type="application/ld+json">{"@type":"Product","name":"Tour Tam Dao",
      "identifier":"TD-01","additionalProperty":[
      {"@type":"PropertyValue","name":"Thời lượng","value":"2 ngày"},
      {"@type":"PropertyValue","name":"Khởi hành","value":"Hà Nội"},
      {"@type":"PropertyValue","name":"Phương tiện","value":"Xe"}],
      "offers":{"@type":"AggregateOffer","offers":[
      {"@type":"Offer","name":"TD-01-01","price":2500000,
      "priceCurrency":"VND","validFrom":"2026-10-12"}]}}</script>
      <h1>Tour Tam Dao</h1>
      <p>Mã tour: TD-01. Khởi hành từ: Nội dung menu bị dính.</p>
      <p>Dịch vụ bao gồm và không bao gồm. Giá tour bao gồm: vé xe.
      Không bao gồm: bữa tối. Lưu ý quan trọng. Thanh toán trước ngày đi.</p>
      </body></html>""".encode()
    script = b'const endpoint = "/api/public/tours";'
    pages = {
        f"{BASE}/robots.txt": FetchResult(f"{BASE}/robots.txt", 200, "text/plain", robots),
        f"{BASE}/sitemap.xml": FetchResult(f"{BASE}/sitemap.xml", 404, "text/plain", b""),
        f"{BASE}/": FetchResult(f"{BASE}/", 200, "text/html", home),
        f"{BASE}/gioi-thieu": FetchResult(f"{BASE}/gioi-thieu", 200, "text/html", about),
        f"{BASE}/tour/tam-dao": FetchResult(f"{BASE}/tour/tam-dao", 200, "text/html", tour),
        f"{BASE}/assets/site.js": FetchResult(
            f"{BASE}/assets/site.js", 200, "application/javascript", script
        ),
    }
    fetcher = FakeFetcher(pages)
    crawler = Crawler(CrawlOptions(max_pages=3, max_requests=10, delay=0), fetcher)

    report = crawler.crawl(f"{BASE}/")
    fields = report.supplier
    assert report.status == "completed"
    assert report.pages_scanned == 3
    assert report.requests_made == 5
    assert fields["display_name"].value == "Example Tours"
    assert fields["display_name"].evidence[0].method == "json_ld"
    assert fields["legal_name"].value == "Example Travel JSC"
    assert fields["email"].value == "hello@example.test"
    assert fields["phone"].value == "02812345678"
    assert fields["phone"].evidence[0].method == "tel_link"
    assert fields["email"].evidence[0].method == "mailto_link"
    assert fields["license_claims"].status == "not_observed"
    assert fields["license_claims"].value is None
    assert fields["display_name"].evidence[0].json_path.endswith("/name")
    assert fields["display_name"].evidence[0].url == f"{BASE}/"
    assert report.sample_tour is not None
    assert report.sample_tour.fields["tour_code"].value == "TD-01"
    assert report.sample_tour.fields["title"].value == "Tour Tam Dao"
    assert report.sample_tour.fields["duration"].value == "2 ngày"
    assert report.sample_tour.fields["departure_city"].value == "Hà Nội"
    assert report.sample_tour.fields["price_options"].value[0]["price"] == 2_500_000
    assert "excluded" not in report.sample_tour.fields
    assert all(field.evidence for field in report.sample_tour.fields.values())
    assert "pages" not in report.to_dict()
    assert "capabilities" not in report.to_dict()
    assert f"{BASE}/assets/site.js" not in fetcher.visited


def test_crawl_stops_when_robots_disallows_seed(monkeypatch):
    _allow_test_hosts(monkeypatch)
    robots = b"User-agent: *\nDisallow: /\n"
    fetcher = FakeFetcher(
        {
            f"{BASE}/robots.txt": FetchResult(f"{BASE}/robots.txt", 200, "text/plain", robots),
        }
    )

    report = Crawler(CrawlOptions(max_pages=1, max_requests=2, delay=0), fetcher).crawl(f"{BASE}/")

    assert report.status == "blocked"
    assert report.pages_scanned == 0
    assert report.requests_made == 1


def test_redirect_to_another_origin_is_blocked_before_second_request(monkeypatch):
    _allow_test_hosts(monkeypatch)

    class RedirectFetcher:
        def __init__(self):
            self.visited = []

        def fetch(self, url, origin):
            self.visited.append(url)
            return FetchResult(url, 302, "text/html", b"", redirect_to="https://other.test/")

    fetcher = RedirectFetcher()
    crawler = Crawler(CrawlOptions(max_pages=1, max_requests=2, delay=0), fetcher)
    report = CrawlReport(source_url=f"{BASE}/")

    result = crawler._fetch(f"{BASE}/", ("https", "example.test", 443), report)

    assert result.error == "Unsafe redirect blocked"
    assert report.requests_made == 1
    assert fetcher.visited == [f"{BASE}/"]
