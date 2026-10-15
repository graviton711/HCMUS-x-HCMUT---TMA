"""Offline sample catalog rows. Replaces the deleted configs/fixture-catalog.yaml.

Same 3 tours/offers as the old YAML fixture, built directly as TourRow
mappings (no file, no YAML). `observed_at` is stamped at build time, like
the old fixture loader did.
"""

from __future__ import annotations

from collections.abc import Iterable

from backend.models import TourRow
from shared import now_vn_iso


def sample_rows() -> list[TourRow]:
    now = now_vn_iso()
    return [
        TourRow(
            provider={"source_key": "dulichviet", "display_name": "Du Lịch Việt"},
            tour={
                "record_key": "dlv-dalat-3n",
                "url": "https://dulichviet.com.vn/tour-da-lat-3-ngay",
                "tour_name": "Đà Lạt 3 ngày 2 đêm",
                "departure_city": "Sài Gòn",
                "destinations": ["Đà Lạt"],
                "transport": "bus",
                "accommodation": "3_star",
                "duration_days": 3,
                "itinerary": "Ngày 1: Sài Gòn - Đà Lạt, tham quan Dinh Bảo Đại. "
                    "Ngày 2: Langbiang, Thung lũng Tình yêu. "
                    "Ngày 3: Chợ Đà Lạt, về Sài Gòn.",
                "inclusions": "Xe đưa đón, khách sạn 3 sao, ăn sáng, vé tham quan, hướng dẫn viên.",
                "exclusions": "Chi phí cá nhân, tiền tip.",
                "cancellation_policy": "Hủy trước 7 ngày hoàn 100%, trước 3 ngày hoàn 50%.",
                "surcharges": "Phụ thu phòng đơn 500.000đ/đêm.",
                "child_policy": "Trẻ em dưới 5 tuổi miễn phí, từ 5-10 tuổi tính 50% giá tour.",
                "verification_status": "provider_claimed",
                "observed_at": now,
            },
            offers=[
                {
                    "record_key": "dlv-dalat-3n-20261225",
                    "departure_date": "2026-12-25",
                    "price": 7500000,
                    "currency": "VND",
                    "price_type": "fixed",
                    "availability": "available",
                    "observed_at": now,
                },
                {
                    "record_key": "dlv-dalat-3n-20270109",
                    "departure_date": "2027-01-09",
                    "price": 6900000,
                    "currency": "VND",
                    "price_type": "fixed",
                    "availability": "available",
                    "observed_at": now,
                },
            ],
        ),
        TourRow(
            provider={"source_key": "vietravel", "display_name": "Vietravel"},
            tour={
                "record_key": "vtr-phuquoc-4n",
                "url": "https://vietravel.com/tour-phu-quoc-4-ngay",
                "tour_name": "Phú Quốc 4 ngày 3 đêm",
                "departure_city": "Sài Gòn",
                "destinations": ["Phú Quốc"],
                "transport": "flight",
                "accommodation": "4_star",
                "duration_days": 4,
                "itinerary": "Ngày 1: Bay Sài Gòn - Phú Quốc, tắm biển Bãi Sao. "
                    "Ngày 2: VinWonders, Safari. "
                    "Ngày 3: Tour 4 đảo, lặn ngắm san hô. "
                    "Ngày 4: Chợ Dương Đông, bay về.",
                "inclusions": "Vé máy bay khứ hồi, resort 4 sao, ăn 7 bữa, vé VinWonders, tàu 4 đảo.",
                "exclusions": "Vé lặn bình dưỡng khí, chi phí cá nhân.",
                "cancellation_policy": "Hủy trước 14 ngày hoàn 100%, sau đó thu phí 50-100% tùy thời điểm.",
                "surcharges": "Phụ thu lễ Tết 2.000.000đ/khách. Giá trẻ em tính riêng.",
                "child_policy": "Trẻ em dưới 2 tuổi miễn phí vé máy bay (thu phí dịch vụ), 2-11 tuổi tính 75%.",
                "verification_status": "provider_claimed",
                "observed_at": now,
            },
            offers=[
                {
                    "record_key": "vtr-phuquoc-4n-20261226",
                    "departure_date": "2026-12-26",
                    "price": 12900000,
                    "currency": "VND",
                    "price_type": "fixed",
                    "availability": "available",
                    "observed_at": now,
                },
            ],
        ),
        TourRow(
            provider={"source_key": "saigontourist", "display_name": "Saigontourist"},
            tour={
                "record_key": "sgt-halong-3n",
                "url": "https://saigontourist.net/tour-ha-long-3-ngay",
                "tour_name": "Hạ Long 3 ngày 2 đêm",
                "departure_city": "Hà Nội",
                "destinations": ["Hạ Long"],
                "transport": "cruise",
                "accommodation": "4_star",
                "duration_days": 3,
                "itinerary": "Ngày 1: Hà Nội - Hạ Long, lên du thuyền. "
                    "Ngày 2: Vịnh Lan Hạ, chèo kayak, ngủ đêm trên vịnh. "
                    "Ngày 3: Làng chài, về Hà Nội.",
                "inclusions": "Xe Hà Nội - Hạ Long, du thuyền 4 sao, các bữa ăn trên tàu, kayak, vé vịnh.",
                "exclusions": "Đồ uống, massage, chi phí cá nhân.",
                "cancellation_policy": "Hủy trước 10 ngày hoàn 80%.",
                "surcharges": "",
                "child_policy": "Trẻ em dưới 4 tuổi miễn phí.",
                "verification_status": "provider_claimed",
                "observed_at": now,
            },
            offers=[
                {
                    "record_key": "sgt-halong-3n-20261227",
                    "departure_date": "2026-12-27",
                    "price": 8900000,
                    "currency": "VND",
                    "price_type": "from",
                    "availability": "unknown",
                    "observed_at": now,
                },
            ],
        ),
    ]


class StaticCatalog:
    """In-memory catalog for offline tests. Same interface as SupabaseCatalog."""

    def __init__(self, rows: list[TourRow] | None = None):
        self._rows = rows if rows is not None else sample_rows()

    def list_tours(self, limit: int) -> list[TourRow]:
        return self._rows[:limit]

    def list_tour_index(self, limit: int) -> list[TourRow]:
        return self._rows[:limit]

    def list_tour_details(self, tour_keys: Iterable[str]) -> list[TourRow]:
        keys = {key.strip() for key in tour_keys if isinstance(key, str) and key.strip()}
        if not keys:
            return []
        return [
            row for row in self._rows
            if str(row.tour.get("record_key") or row.tour.get("url") or "") in keys
        ]

    def list_destinations(self) -> list[str]:
        seen: list[str] = []
        for row in self._rows:
            for dest in row.tour.get("destinations", []):
                if isinstance(dest, str) and dest not in seen:
                    seen.append(dest)
        return seen
