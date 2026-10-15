"""Catalog readers. Supabase is the only live catalog (read-only)."""

from __future__ import annotations

from collections.abc import Iterable
from time import perf_counter

from backend.errors import AppError
from backend.models import TourRow
from shared import get_logger

_log = get_logger("backend.catalog")


class SupabaseCatalog:
    """Read-only live catalog. Raises, never falls back."""

    def __init__(self, db_url: str, scan_limit: int,
                 providers_limit: int, connect_timeout_s: int):
        if not db_url:
            raise AppError("CATALOG_NOT_CONFIGURED", "SUPABASE_TOUR_DB_URL is not configured.", 503)
        self._db_url = db_url
        self._scan_limit = scan_limit
        self._providers_limit = providers_limit
        self._timeout = connect_timeout_s

    def _unavailable(self, operation: str, exc: Exception, started: float) -> AppError:
        sqlstate = getattr(exc, "sqlstate", None) or getattr(exc, "pgcode", None)
        _log.error(
            "catalog_read_failed operation=%s duration_ms=%d exception_type=%s sqlstate=%s",
            operation,
            int((perf_counter() - started) * 1000),
            type(exc).__name__,
            sqlstate or "-",
        )
        return AppError("CATALOG_UNAVAILABLE", "Catalog is unavailable.", 502, retryable=True)

    def list_destinations(self) -> list[str]:
        try:
            import psycopg
        except ImportError as exc:
            raise AppError("CATALOG_DRIVER_MISSING", "Missing psycopg driver.", 500) from exc
        started = perf_counter()
        try:
            with psycopg.connect(self._db_url, connect_timeout=self._timeout, autocommit=True) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT DISTINCT jsonb_array_elements_text(destinations)"
                        " FROM tours LIMIT %s",
                        (self._scan_limit,),
                    )
                    result = sorted({r[0] for r in cur.fetchall() if r[0]})
                    _log.info(
                        "catalog_read_completed operation=list_destinations rows=%d duration_ms=%d",
                        len(result),
                        int((perf_counter() - started) * 1000),
                    )
                    return result
        except AppError:
            raise
        except Exception as exc:
            raise self._unavailable("list_destinations", exc, started) from exc

    def list_tours(self, limit: int) -> list[TourRow]:
        """Compatibility read that returns full records for every requested tour."""
        index = self.list_tour_index(limit)
        keys = [str(row.tour.get("record_key") or row.tour.get("url") or "") for row in index]
        details = self.list_tour_details(keys)
        by_key = {
            str(row.tour.get("record_key") or row.tour.get("url") or ""): row
            for row in details
        }
        return [by_key[key] for key in keys if key in by_key]

    def list_tour_index(self, limit: int) -> list[TourRow]:
        """Load only fields needed to filter, count, and identify catalog candidates."""
        return self._read_tours(limit=min(limit, self._scan_limit), details_for=None)

    def list_tour_details(self, tour_keys: Iterable[str]) -> list[TourRow]:
        """Load long evidence fields for selected record keys/URLs in one catalog read."""
        keys = list(dict.fromkeys(key.strip() for key in tour_keys if isinstance(key, str) and key.strip()))
        if not keys:
            return []
        return self._read_tours(details_for=keys)

    def _read_tours(self, limit: int | None = None, details_for: list[str] | None = None) -> list[TourRow]:
        try:
            import psycopg
        except ImportError as exc:
            raise AppError("CATALOG_DRIVER_MISSING", "Missing psycopg driver.", 500) from exc
        operation = "list_tour_index" if details_for is None else "list_tour_details"
        started = perf_counter()
        try:
            with psycopg.connect(self._db_url, connect_timeout=self._timeout, autocommit=True) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, source_key, display_name FROM providers LIMIT %s",
                        (self._providers_limit,),
                    )
                    providers = {r[0]: {"source_key": r[1], "display_name": r[2]} for r in cur.fetchall()}
                    if details_for is None:
                        cur.execute(
                            "SELECT id, provider_id, record_key, url, tour_name, departure_city,"
                            " destinations, route, transport, accommodation, duration_days,"
                            " duration_nights, price, currency, price_type, verification_status,"
                            " observed_at, updated_at FROM tours"
                            " ORDER BY observed_at DESC NULLS LAST LIMIT %s",
                            (limit,),
                        )
                    else:
                        cur.execute(
                            "SELECT id, provider_id, record_key, url, tour_name, departure_city,"
                            " destinations, route, transport, accommodation, duration_days, duration_nights,"
                            " price, currency, price_type, field_meta, itinerary, inclusions, exclusions,"
                            " cancellation_policy, surcharges, child_policy, verification_status,"
                            " observed_at, updated_at FROM tours"
                            " WHERE record_key = ANY(%s) OR url = ANY(%s)"
                            " ORDER BY observed_at DESC NULLS LAST",
                            (details_for, details_for),
                        )
                    tour_cols = [d[0] for d in (cur.description or [])]
                    tours = [dict(zip(tour_cols, r, strict=False)) for r in cur.fetchall()]
                    if not tours:
                        _log.info(
                            "catalog_read_completed operation=%s rows=0 duration_ms=%d",
                            operation,
                            int((perf_counter() - started) * 1000),
                        )
                        return []
                    offer_fields = (
                        "tour_id, record_key, departure_date, price, availability, price_type, observed_at, updated_at"
                        if details_for is None
                        else "tour_id, record_key, departure_date, price, availability, price_type, price_by_age, "
                             "single_supplement, supplements, conditions, field_meta, observed_at, updated_at"
                    )
                    cur.execute(
                        f"SELECT {offer_fields} FROM offers WHERE tour_id = ANY(%s)",
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
                        if row.get("single_supplement") is not None:
                            row["single_supplement"] = int(row["single_supplement"])
                        for key in ("observed_at", "updated_at"):
                            if row.get(key) is not None:
                                row[key] = str(row[key])
                        by_tour.setdefault(row.pop("tour_id"), []).append(row)
        except AppError:
            raise
        except Exception as exc:
            raise self._unavailable(operation, exc, started) from exc
        out: list[TourRow] = []
        for t in tours:
            tid = t.pop("id")
            pid = t.pop("provider_id")
            for key in ("observed_at", "updated_at"):
                if t.get(key) is not None:
                    t[key] = str(t[key])
            t["_detail_state"] = "index" if details_for is None else "complete"
            out.append(
                TourRow(
                    provider=providers.get(pid, {}),
                    tour=t,
                    offers=by_tour.get(tid, []),
                )
            )
        _log.info(
            "catalog_read_completed operation=%s rows=%d offers=%d duration_ms=%d",
            operation,
            len(out),
            sum(len(row.offers) for row in out),
            int((perf_counter() - started) * 1000),
        )
        return out


def for_settings(settings) -> SupabaseCatalog:
    return SupabaseCatalog(settings.supabase_tour_db_url, settings.supabase_scan_limit,
                           settings.tuning.data.providers_limit,
                           settings.tuning.data.connect_timeout_s)

