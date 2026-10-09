"""Catalog readers. Fixture is explicit dev data; Supabase is read-only live."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from backend.errors import AppError
from backend.models import TourRow

_VN = ZoneInfo("Asia/Ho_Chi_Minh")


def _now_vn() -> str:
    return datetime.now(_VN).isoformat()


def _fixture_rows() -> list[TourRow]:
    now = _now_vn()
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
                "itinerary": "Ngày 1: Sài Gòn - Đà Lạt, tham quan Dinh Bảo Đại. Ngày 2: Langbiang, Thung lũng Tình yêu. Ngày 3: Chợ Đà Lạt, về Sài Gòn.",
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
                "itinerary": "Ngày 1: Bay Sài Gòn - Phú Quốc, tắm biển Bãi Sao. Ngày 2: VinWonders, Safari. Ngày 3: Tour 4 đảo, lặn ngắm san hô. Ngày 4: Chợ Dương Đông, bay về.",
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
                "itinerary": "Ngày 1: Hà Nội - Hạ Long, lên du thuyền. Ngày 2: Vịnh Lan Hạ, chèo kayak, ngủ đêm trên vịnh. Ngày 3: Làng chài, về Hà Nội.",
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


class FixtureCatalog:
    """Explicit dev/test catalog. Never a silent fallback."""

    def list_tours(self, limit: int = 20) -> list[TourRow]:
        return _fixture_rows()[:limit]

    def list_destinations(self) -> list[str]:
        seen: list[str] = []
        for row in _fixture_rows():
            for dest in row.tour.get("destinations", []):
                if isinstance(dest, str) and dest not in seen:
                    seen.append(dest)
        return seen


class SupabaseCatalog:
    """Read-only live catalog. Raises, never falls back."""

    def __init__(self, db_url: str, scan_limit: int = 1000,
                 providers_limit: int = 100, connect_timeout_s: int = 8):
        if not db_url:
            raise AppError("CATALOG_NOT_CONFIGURED", "Chưa cấu hình SUPABASE_TOUR_DB_URL.", 503)
        self._db_url = db_url
        self._scan_limit = scan_limit
        self._providers_limit = providers_limit
        self._timeout = connect_timeout_s

    def list_destinations(self) -> list[str]:
        try:
            import psycopg
        except ImportError as exc:
            raise AppError("CATALOG_DRIVER_MISSING", "Thiếu psycopg.", 500) from exc
        try:
            with psycopg.connect(self._db_url, connect_timeout=self._timeout, autocommit=True) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT DISTINCT jsonb_array_elements_text(destinations)"
                        " FROM tours LIMIT %s",
                        (self._scan_limit,),
                    )
                    return sorted({r[0] for r in cur.fetchall() if r[0]})
        except AppError:
            raise
        except Exception as exc:
            raise AppError("CATALOG_UNAVAILABLE", "Không đọc được catalog.", 502, retryable=True) from exc

    def list_tours(self, limit: int = 20) -> list[TourRow]:
        try:
            import psycopg
        except ImportError as exc:
            raise AppError("CATALOG_DRIVER_MISSING", "Thiếu psycopg.", 500) from exc
        bound = min(limit, self._scan_limit)
        try:
            with psycopg.connect(self._db_url, connect_timeout=self._timeout, autocommit=True) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, source_key, display_name FROM providers LIMIT %s",
                        (self._providers_limit,),
                    )
                    providers = {r[0]: {"source_key": r[1], "display_name": r[2]} for r in cur.fetchall()}
                    cur.execute(
                        "SELECT id, provider_id, record_key, url, tour_name, departure_city,"
                        " destinations, transport, accommodation, duration_days, itinerary,"
                        " inclusions, exclusions, cancellation_policy, surcharges, child_policy,"
                        " verification_status, observed_at FROM tours LIMIT %s",
                        (bound,),
                    )
                    tour_cols = [d[0] for d in (cur.description or [])]
                    tours = [dict(zip(tour_cols, r, strict=False)) for r in cur.fetchall()]
                    if not tours:
                        return []
                    cur.execute(
                        "SELECT tour_id, record_key, departure_date, price, availability,"
                        " observed_at FROM offers WHERE tour_id = ANY(%s)",
                        ([t["id"] for t in tours],),
                    )
                    offer_cols = [d[0] for d in (cur.description or [])]
                    by_tour: dict[int, list[dict]] = {}
                    for r in cur.fetchall():
                        row = dict(zip(offer_cols, r, strict=False))
                        if row["departure_date"] is not None:
                            row["departure_date"] = str(row["departure_date"])
                        if row["price"] is not None:
                            row["price"] = int(row["price"])
                        if row["observed_at"] is not None:
                            row["observed_at"] = str(row["observed_at"])
                        by_tour.setdefault(row.pop("tour_id"), []).append(row)
        except AppError:
            raise
        except Exception as exc:
            raise AppError("CATALOG_UNAVAILABLE", "Không đọc được catalog.", 502, retryable=True) from exc
        out: list[TourRow] = []
        for t in tours:
            tid = t.pop("id")
            pid = t.pop("provider_id")
            for key in ("observed_at",):
                if t.get(key) is not None:
                    t[key] = str(t[key])
            out.append(
                TourRow(
                    provider=providers.get(pid, {}),
                    tour=t,
                    offers=by_tour.get(tid, []),
                )
            )
        return out


def for_settings(settings) -> FixtureCatalog | SupabaseCatalog:
    if settings.data_provider == "supabase":
        return SupabaseCatalog(settings.supabase_tour_db_url, settings.supabase_scan_limit,
                               settings.tuning.data.providers_limit,
                               settings.tuning.data.connect_timeout_s)
    return FixtureCatalog()
