from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

SUPPLIER_FIELD_LABELS = {
    "display_name": "Tên hiển thị",
    "legal_name": "Tên pháp lý",
    "description": "Mô tả",
    "email": "Email",
    "phone": "Điện thoại",
    "address": "Địa chỉ",
    "website": "Website",
    "license_claims": "Giấy phép (nhà cung cấp tự khai báo)",
}
TOUR_FIELD_LABELS = {
    "tour_code": "Mã tour",
    "title": "Tên tour",
    "description": "Mô tả",
    "route": "Hành trình/tuyến điểm",
    "duration": "Thời lượng",
    "departure_city": "Điểm khởi hành",
    "departure_dates": "Ngày khởi hành",
    "transport": "Phương tiện",
    "itinerary_by_day": "Lịch trình theo ngày",
    "price_options": "Các lựa chọn giá (Offer: mã, hiệu lực, tình trạng, giá)",
    "included": "Dịch vụ bao gồm",
    "excluded": "Dịch vụ không bao gồm",
    "policies": "Lưu ý/điều kiện",
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(slots=True)
class Evidence:
    url: str
    method: str
    snippet: str
    json_path: str | None = None


@dataclass(slots=True)
class ObservedField:
    value: Any = None
    status: str = "not_observed_in_scope"
    evidence: list[Evidence] = field(default_factory=list)


@dataclass(slots=True)
class TourSchemaField:
    name: str
    value_type: str
    status: str = "not_observed"
    evidence: list[Evidence] = field(default_factory=list)


@dataclass(slots=True)
class TourSample:
    url: str
    fields: dict[str, ObservedField] = field(default_factory=dict)


@dataclass(slots=True)
class PageRecord:
    url: str
    status_code: int | None
    content_type: str
    purpose: str
    method: str


@dataclass(slots=True)
class CrawlIssue:
    code: str
    message: str
    url: str | None = None


@dataclass(slots=True)
class CrawlReport:
    source_url: str
    crawled_at: str = field(default_factory=utc_now)
    status: str = "running"
    pages_scanned: int = 0
    requests_made: int = 0
    supplier: dict[str, ObservedField] = field(default_factory=dict)
    tour_schema: list[TourSchemaField] = field(default_factory=list)
    sample_tour: TourSample | None = None
    limitations: list[str] = field(default_factory=list)
    pages: list[PageRecord] = field(default_factory=list)
    issues: list[CrawlIssue] = field(default_factory=list)
    schema_version: str = "1.2"

    def to_dict(self) -> dict[str, Any]:
        supplier = {
            key: {"label": SUPPLIER_FIELD_LABELS.get(key, key), **asdict(value)}
            for key, value in self.supplier.items()
        }
        tour_schema = [
            {**asdict(value), "label": TOUR_FIELD_LABELS.get(value.name, value.name)}
            for value in self.tour_schema
        ]
        sample_tour = None
        if self.sample_tour:
            sample_tour = {
                "url": self.sample_tour.url,
                "fields": {
                    key: {"label": TOUR_FIELD_LABELS.get(key, key), **asdict(value)}
                    for key, value in self.sample_tour.fields.items()
                },
            }
        return {
            "schema_version": self.schema_version,
            "source_url": self.source_url,
            "crawled_at": self.crawled_at,
            "status": self.status,
            "supplier": supplier,
            "tour_schema": tour_schema,
            "sample_tour": sample_tour,
            "limitations": self.limitations,
        }
