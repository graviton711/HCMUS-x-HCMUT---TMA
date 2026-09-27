from __future__ import annotations

import json
import re
import urllib.robotparser
import xml.etree.ElementTree as ET
from collections import deque
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit, urlunsplit

from .fetch import FetchResult, SafeFetcher
from .models import (
    SUPPLIER_FIELD_LABELS,
    CrawlIssue,
    CrawlReport,
    Evidence,
    ObservedField,
    PageRecord,
    TourSample,
    TourSchemaField,
)
from .parser import (
    TOUR_SCHEMA_TYPES,
    PageContent,
    contact_values,
    extract_tour_fields,
    organization_observations,
    parse_html,
)
from .safety import UnsafeURLError, normalized_origin, validate_public_url


@dataclass(slots=True)
class CrawlOptions:
    max_pages: int = 12
    max_requests: int = 20
    max_response_bytes: int = 1_000_000
    timeout: float = 12.0
    delay: float = 1.0

    def __post_init__(self) -> None:
        if not 1 <= self.max_pages <= 50:
            raise ValueError("max_pages must be between 1 and 50")
        if not self.max_pages <= self.max_requests <= 100:
            raise ValueError("max_requests must be between max_pages and 100")
        if not 1_024 <= self.max_response_bytes <= 5_000_000:
            raise ValueError("max_response_bytes must be between 1 KB and 5 MB")
        if not 1 <= self.timeout <= 60:
            raise ValueError("timeout must be between 1 and 60 seconds")
        if not 0 <= self.delay <= 30:
            raise ValueError("delay must be between 0 and 30 seconds")


_SITEMAP_LOC = "{http://www.sitemaps.org/schemas/sitemap/0.9}loc"


def _origin_base(origin: tuple[str, str, int]) -> str:
    scheme, host, port = origin
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    default_port = 443 if scheme == "https" else 80
    authority = host if port == default_port else f"{host}:{port}"
    return f"{scheme}://{authority}"


def _normalize_link(base: str, value: str, origin: tuple[str, str, int]) -> str | None:
    if not value or value.startswith(("mailto:", "tel:", "javascript:", "data:")):
        return None
    absolute = urljoin(base, value)
    try:
        if normalized_origin(absolute) != origin:
            return None
    except UnsafeURLError:
        return None
    parts = urlsplit(absolute)
    return urlunsplit((parts.scheme, parts.netloc, parts.path or "/", parts.query, ""))


def _is_tour_detail_url(url: str) -> bool:
    path = urlsplit(url).path.lower().rstrip("/")
    return bool(re.search(r"/tour/[^/]+$|/[^/]+/tour-[^/]+$", path))


def _page_priority(link: str, label: str = "") -> int:
    path = urlsplit(link).path.lower()
    text = f"{path} {label}".lower()
    if re.search(r"/tour/[^/]+/?$|/[^/]+/tour-[^/]+/?$", path):
        return 250
    scores = (
        (r"about|gioi-thieu|ve-chung-toi|company", 100),
        (r"contact|lien-he|he-thong-chi-nhanh", 95),
        (r"tour|du-lich|hanh-trinh|destination", 80),
        (r"policy|chinh-sach|terms|dieu-khoan", 70),
        (r"review|danh-gia|khach-hang|testimonial", 60),
    )
    for pattern, score in scores:
        if re.search(pattern, text):
            return score
    return 10


class Crawler:
    def __init__(self, options: CrawlOptions | None = None, fetcher: SafeFetcher | None = None):
        self.options = options or CrawlOptions()
        self.fetcher = fetcher or SafeFetcher(
            self.options.timeout, self.options.max_response_bytes, self.options.delay
        )

    def crawl(self, seed_url: str) -> CrawlReport:
        seed = validate_public_url(seed_url)
        origin = normalized_origin(seed)
        report = CrawlReport(source_url=seed)
        robots, sitemap_urls = self._robots(origin, report)
        if robots is None:
            report.status = "blocked"
            report.issues.append(
                CrawlIssue(
                    "robots_unavailable",
                    "Could not safely determine the site's crawl policy; stopped.",
                )
            )
            return report
        if not robots.can_fetch("MLAITourSourceAuditor/0.1", seed):
            report.status = "blocked"
            report.issues.append(
                CrawlIssue("robots_disallow", "robots.txt disallows crawling the seed URL.", seed)
            )
            return report

        candidates: list[tuple[int, str, str]] = [(200, seed, "seed")]
        candidates.extend(self._sitemap_candidates(sitemap_urls, origin, robots, report))
        visited: set[str] = set()
        queue = deque(candidates)
        candidate_cap = self.options.max_pages * 10
        queued_urls = {url for _, url, _ in candidates}
        supplier_evidence: dict[str, list[Evidence]] = {}
        supplier_values: dict[str, list[object]] = {}
        supplier_priorities: dict[str, int] = {}

        while (
            queue
            and report.pages_scanned < self.options.max_pages
            and report.requests_made < self.options.max_requests
        ):
            queue = deque(sorted(queue, key=lambda entry: entry[0], reverse=True))
            _, url, purpose = queue.popleft()
            if url in visited:
                continue
            visited.add(url)
            if not robots.can_fetch("MLAITourSourceAuditor/0.1", url):
                report.issues.append(
                    CrawlIssue("robots_disallow", "URL skipped by robots.txt.", url)
                )
                continue
            result = self._fetch(url, origin, report)
            if result is None:
                break
            if result.error:
                report.pages.append(
                    PageRecord(
                        result.url, result.status_code or None, result.content_type, purpose, "http"
                    )
                )
                report.issues.append(CrawlIssue("fetch_error", result.error, url))
                continue
            if not _is_html(result.content_type, result.body):
                report.pages.append(
                    PageRecord(result.url, result.status_code, result.content_type, purpose, "http")
                )
                continue

            page = parse_html(result.url, result.body, result.content_type)
            report.pages_scanned += 1
            report.pages.append(
                PageRecord(result.url, result.status_code, result.content_type, purpose, "html")
            )
            self._extract_supplier(
                page, supplier_values, supplier_evidence, supplier_priorities, seed
            )
            if _is_tour_detail_url(page.url) and report.sample_tour is None:
                fields = extract_tour_fields(page)
                if fields:
                    report.sample_tour = TourSample(url=page.url, fields=fields)
                    report.tour_schema = [
                        TourSchemaField(
                            name=name,
                            value_type=value_type,
                            status="found" if name in fields else "not_observed",
                            evidence=fields[name].evidence if name in fields else [],
                        )
                        for name, value_type in TOUR_SCHEMA_TYPES.items()
                    ]
            discovered: list[tuple[int, str, str]] = []
            discovered_urls: set[str] = set()
            for link in page.links:
                normalized = _normalize_link(page.url, link.url, origin)
                if (
                    normalized
                    and normalized not in visited
                    and normalized not in queued_urls
                    and normalized not in discovered_urls
                ):
                    discovered_urls.add(normalized)
                    discovered.append(
                        (_page_priority(normalized, link.text), normalized, "internal_link")
                    )
            discovered.sort(key=lambda entry: entry[0], reverse=True)
            for candidate in discovered:
                if len(queued_urls) >= candidate_cap:
                    break
                _, normalized, _ = candidate
                queued_urls.add(normalized)
                queue.append(candidate)

        for name in SUPPLIER_FIELD_LABELS:
            values = supplier_values.get(name, [])
            report.supplier[name] = ObservedField(
                value=(values[0] if len(values) == 1 else values) if values else None,
                status=(
                    "provider_claimed"
                    if name == "license_claims" and values
                    else "found"
                    if values
                    else "not_observed"
                ),
                evidence=supplier_evidence.get(name, []),
            )
        pending_pages = any(url not in visited for _, url, _ in queue)
        if pending_pages:
            report.status = "partial"
            report.issues.append(
                CrawlIssue("crawl_limit", "Crawl stopped at a configured page or request limit.")
            )
            report.limitations.append(
                "Đã chạm giới hạn crawl; thông tin nhà cung cấp có thể chưa bao quát hết website."
            )
        elif report.pages_scanned == 0:
            report.status = "error"
        else:
            report.status = "completed"
        if report.sample_tour is None:
            report.status = "partial" if report.pages_scanned else report.status
            report.limitations.append(
                "No tour-detail page was found and extracted within the crawl scope."
            )
        return report

    def _fetch(
        self, url: str, origin: tuple[str, str, int], report: CrawlReport
    ) -> FetchResult | None:
        current = url
        redirects = 0
        while report.requests_made < self.options.max_requests:
            report.requests_made += 1
            try:
                result = self.fetcher.fetch(current, origin)
            except (UnsafeURLError, OSError, ValueError) as exc:
                return FetchResult(current, 0, "", b"", str(exc))
            if not result.redirect_to:
                return result
            if redirects >= 5:
                return FetchResult(
                    current, result.status_code, result.content_type, b"", "Too many redirects"
                )
            target = urljoin(current, result.redirect_to)
            try:
                current = validate_public_url(target, origin)
            except UnsafeURLError:
                return FetchResult(
                    current, result.status_code, result.content_type, b"", "Unsafe redirect blocked"
                )
            redirects += 1
        return FetchResult(current, 0, "", b"", "Request limit reached while following redirect")

    def _robots(self, origin: tuple[str, str, int], report: CrawlReport):
        base = _origin_base(origin)
        robots_url = f"{base}/robots.txt"
        result = self._fetch(robots_url, origin, report)
        if result is None:
            return None, []
        if result.status_code == 404:
            parser = urllib.robotparser.RobotFileParser()
            parser.parse([])
            return parser, []
        if result.error:
            return None, []
        if result.status_code != 200:
            return None, []
        parser = urllib.robotparser.RobotFileParser()
        parser.set_url(robots_url)
        parser.parse(result.body.decode("utf-8", errors="replace").splitlines())
        sitemaps = [
            line.split(":", 1)[1].strip()
            for line in result.body.decode("utf-8", errors="replace").splitlines()
            if line.lower().startswith("sitemap:")
        ]
        return parser, sitemaps[:3]

    def _sitemap_candidates(
        self,
        urls: list[str],
        origin: tuple[str, str, int],
        robots: urllib.robotparser.RobotFileParser,
        report: CrawlReport,
    ) -> list[tuple[int, str, str]]:
        base = _origin_base(origin)
        if not urls:
            urls = [f"{base}/sitemap.xml"]
        output: list[tuple[int, str, str]] = []
        for sitemap_url in urls[:3]:
            if report.requests_made >= self.options.max_requests:
                break
            try:
                safe_sitemap = validate_public_url(sitemap_url, origin)
            except UnsafeURLError:
                report.issues.append(
                    CrawlIssue(
                        "unsafe_sitemap", "Out-of-scope sitemap URL was skipped.", sitemap_url
                    )
                )
                continue
            if not robots.can_fetch("MLAITourSourceAuditor/0.1", safe_sitemap):
                report.issues.append(
                    CrawlIssue(
                        "robots_disallow", "Sitemap URL skipped by robots.txt.", safe_sitemap
                    )
                )
                continue
            result = self._fetch(safe_sitemap, origin, report)
            if result is None or result.error or result.status_code != 200:
                continue
            try:
                root = ET.fromstring(result.body)
            except ET.ParseError:
                report.issues.append(
                    CrawlIssue("invalid_sitemap", "Sitemap XML could not be parsed.", safe_sitemap)
                )
                continue
            for node in root.iter():
                if node.tag.rsplit("}", 1)[-1] not in {"loc", "url"} or not node.text:
                    continue
                link = _normalize_link(base, node.text.strip(), origin)
                if link and link != safe_sitemap:
                    output.append((_page_priority(link), link, "sitemap"))
                if len(output) >= self.options.max_pages * 3:
                    break
        return output

    def _extract_supplier(
        self,
        page: PageContent,
        values: dict[str, list[object]],
        evidence: dict[str, list[Evidence]],
        priorities: dict[str, int],
        seed_url: str,
    ) -> None:
        def record(
            field_name: str,
            value: object,
            source: Evidence,
            priority: int,
        ) -> None:
            if field_name in {"email", "phone"}:
                existing = values.setdefault(field_name, [])
                normalized = (
                    str(value).casefold()
                    if field_name == "email"
                    else "".join(ch for ch in str(value) if ch.isdigit())
                )
                seen = {
                    str(item).casefold()
                    if field_name == "email"
                    else "".join(ch for ch in str(item) if ch.isdigit())
                    for item in existing
                }
                if normalized and normalized not in seen:
                    existing.append(value)
                    evidence.setdefault(field_name, []).append(source)
                return

            if priority > priorities.get(field_name, -1):
                values[field_name] = [value]
                evidence[field_name] = [source]
                priorities[field_name] = priority

        for field_name, observations in organization_observations(page.json_ld).items():
            for observation in observations:
                snippet = json.dumps(
                    observation.raw_value, ensure_ascii=False, separators=(",", ":")
                )
                record(
                    field_name,
                    observation.value,
                    Evidence(page.url, "json_ld", snippet[:240], observation.path),
                    observation.priority,
                )

        site_name = page.metadata.get("og:site_name")
        if site_name:
            record(
                "display_name",
                site_name,
                Evidence(page.url, "html_metadata", f"og:site_name={site_name}"[:240]),
                2,
            )

        if page.url == seed_url:
            description_key = next(
                (key for key in ("description", "og:description") if page.metadata.get(key)),
                None,
            )
            if description_key:
                description = page.metadata[description_key]
                record(
                    "description",
                    description,
                    Evidence(
                        page.url,
                        "html_metadata",
                        f"{description_key}={description}"[:240],
                    ),
                    2,
                )
            website = _origin_base(normalized_origin(page.url))
            record("website", website, Evidence(page.url, "seed_url", website), 5)

        emails, phones = contact_values(page)
        for email in emails:
            record(
                "email",
                email,
                Evidence(page.url, "mailto_link", f"mailto:{email}"),
                1,
            )
        for phone in phones:
            record(
                "phone",
                phone,
                Evidence(page.url, "tel_link", f"tel:{phone}"),
                1,
            )


def _is_html(content_type: str, body: bytes) -> bool:
    kind = content_type.lower()
    return (
        "text/html" in kind
        or "application/xhtml" in kind
        or (not kind and body.lstrip().lower().startswith((b"<!doctype html", b"<html")))
    )
