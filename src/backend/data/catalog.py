"""Catalog readers. Fixture is explicit dev data; Supabase is read-only live."""

from __future__ import annotations

from pathlib import Path

from backend.errors import AppError
from backend.models import TourRow
from shared import get_logger, now_vn_iso

log = get_logger("catalog")


def _resolve_fixture(path: str | Path | None) -> Path:
    if path is not None:
        candidate = Path(path)
        if candidate.is_file():
            return candidate
        raise AppError("FIXTURE_NOT_FOUND", f"Catalog fixture not found: {path}.", 500)
    for candidate in (Path(__file__).resolve().parents[2] / "configs" / "fixture-catalog.yaml",
                      Path.cwd() / "configs" / "fixture-catalog.yaml"):
        if candidate.is_file():
            return candidate
    raise AppError("FIXTURE_NOT_FOUND", "Missing configs/fixture-catalog.yaml.", 500)


def _fixture_rows(path: str | Path | None = None) -> list[TourRow]:
    import yaml

    data = yaml.safe_load(_resolve_fixture(path).read_text(encoding="utf-8")) or []
    if not isinstance(data, list):
        raise AppError("FIXTURE_INVALID", "Fixture catalog must be a list.", 500)
    now = now_vn_iso()
    rows: list[TourRow] = []
    for entry in data:
        if not isinstance(entry, dict):
            raise AppError("FIXTURE_INVALID", "Each fixture entry must be a mapping.", 500)
        tour = dict(entry.get("tour", {}))
        tour.setdefault("observed_at", now)
        offers = []
        for offer in entry.get("offers", []):
            row = dict(offer)
            row.setdefault("observed_at", now)
            offers.append(row)
        rows.append(TourRow(provider=dict(entry.get("provider", {})), tour=tour, offers=offers))
    return rows


class FixtureCatalog:
    """Explicit dev/test catalog. Never a silent fallback."""

    def __init__(self, path: str | Path | None = None):
        self._rows = _fixture_rows(path)

    def list_tours(self, limit: int) -> list[TourRow]:
        return self._rows[:limit]

    def list_destinations(self) -> list[str]:
        seen: list[str] = []
        for row in self._rows:
            for dest in row.tour.get("destinations", []):
                if isinstance(dest, str) and dest not in seen:
                    seen.append(dest)
        return seen


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

    def list_destinations(self) -> list[str]:
        try:
            import psycopg
        except ImportError as exc:
            raise AppError("CATALOG_DRIVER_MISSING", "Missing psycopg driver.", 500) from exc
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
            log.warning("catalog unavailable: %s", exc)
            raise AppError("CATALOG_UNAVAILABLE", "Catalog is unavailable.", 502, retryable=True) from exc

    def list_tours(self, limit: int) -> list[TourRow]:
        try:
            import psycopg
        except ImportError as exc:
            raise AppError("CATALOG_DRIVER_MISSING", "Missing psycopg driver.", 500) from exc
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
                        " destinations, route, transport, accommodation, duration_days,"
                        " price, currency, price_type, field_meta, itinerary,"
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
                        " price_by_age, field_meta, observed_at"
                        " FROM offers WHERE tour_id = ANY(%s)",
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
            log.warning("catalog unavailable: %s", exc)
            raise AppError("CATALOG_UNAVAILABLE", "Catalog is unavailable.", 502, retryable=True) from exc
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

