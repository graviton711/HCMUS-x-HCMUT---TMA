"""Catalog rows → common snapshots. Mechanical, no per-source branches."""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from decimal import Decimal

from backend.models import Evidence, Freshness, OfferSnapshot, TourRow, TourSnapshot
from shared.text import fold_vi as _place_key

_TRANSPORTS = {"flight", "bus", "train", "cruise", "mixed"}
_DEFAULT_FRESHNESS_SECONDS: dict[str, int | None] = {"departure_date": None}

def _text(value: object) -> str:
    return value if isinstance(value, str) else ""


def _int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, (float, Decimal)) and math.isfinite(float(value)) and float(value).is_integer():
        return int(value)
    return None


def _evidence(url: str, observed_at: str, record_ref: str) -> Evidence:
    return Evidence(
        url=url,
        method="database_record",
        observed_at=observed_at if isinstance(observed_at, str) else "",
        record_ref=record_ref,
    )


def _destinations(values: object, origin: str) -> tuple[list[str], list[str]]:
    raw = [v.strip() for v in values if isinstance(v, str) and v.strip()] if isinstance(values, list) else []
    visit = list(raw)
    origin_key = _place_key(origin)
    if visit and _place_key(visit[0]) == origin_key:
        visit.pop(0)
    if visit and _place_key(visit[-1]) == origin_key:
        visit.pop()
    return visit, raw


def _parsed_time(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo else None
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo else None


def _freshness(value: object, ttl: int | None, now: datetime) -> Freshness:
    observed = _parsed_time(value)
    if observed is None or observed > now:
        return "unknown"
    if ttl is None:
        return "fresh"
    if not isinstance(ttl, int) or isinstance(ttl, bool) or ttl <= 0:
        return "unknown"
    return "fresh" if (now - observed).total_seconds() <= ttl else "stale"


def _json_object(value: object) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except ValueError:
            return {}
    return {}


def _pricing_details(offer: dict) -> tuple[bool | None, list[dict], list[dict]]:
    """Read optional price annotations without using them to qualify catalog price."""
    offer_meta = _json_object(offer.get("field_meta"))
    pricing = offer_meta.get("pricing")
    if not isinstance(pricing, dict):
        return None, [], []
    complete = pricing.get("complete")
    quotes = pricing.get("quotes")
    extra_charges = pricing.get("extra_charges")
    return (
        complete if isinstance(complete, bool) else None,
        [item for item in quotes if isinstance(item, dict)] if isinstance(quotes, list) else [],
        [item for item in extra_charges if isinstance(item, dict)]
        if isinstance(extra_charges, list)
        else [],
    )


def _age_prices(offer: dict) -> dict[str, int | None]:
    raw = _json_object(offer.get("price_by_age"))
    return {
        key: _int(value)
        for key, value in raw.items()
        if key in {"adult", "child", "small_child", "infant"}
    }


def _offer(
    o: dict,
    tour: dict,
    tour_id: str,
    tour_url: str,
    freshness_seconds: dict[str, int | None],
    now: datetime,
) -> OfferSnapshot:
    price = _int(o.get("price"))
    raw_basis = o.get("price_type")
    basis = {"fixed": "exact", "from": "from", "contact": "contact", "unknown": "unknown"}.get(
        str(raw_basis or "").strip().lower(), "unknown"
    )
    if price is None:
        basis = "unknown"
    complete, quotes, charges = _pricing_details(o)
    availability = o.get("availability", "unknown")
    if availability not in ("available", "sold_out", "unknown"):
        availability = "unknown"
    departure = o.get("departure_date", "")
    observed = o.get("observed_at")
    return OfferSnapshot(
        id=str(o.get("record_key") or f"{tour_id}@{departure}"),
        tour_id=tour_id,
        departure_date=departure if isinstance(departure, str) else "",
        price=price,
        currency=str(o.get("currency") or tour.get("currency") or ""),
        price_basis=basis,  # type: ignore[arg-type]
        price_by_age=_age_prices(o),
        single_supplement=_int(o.get("single_supplement")),
        supplements=_text(o.get("supplements")),
        departure_freshness=_freshness(observed, freshness_seconds.get("departure_date"), now),
        departure_freshness_policy_seconds=freshness_seconds.get("departure_date"),
        pricing_complete=complete,
        price_quotes=quotes,
        extra_charges=charges,
        availability=availability,
        conditions=_text(o.get("conditions")),
        evidence=_evidence(tour_url, str(observed or ""), str(o.get("record_key", ""))),
    )


def rows_to_snapshots(
    rows: list[TourRow],
    *,
    freshness_seconds: dict[str, int | None] | None = None,
    now: datetime | None = None,
) -> list[TourSnapshot]:
    ttl = _DEFAULT_FRESHNESS_SECONDS if freshness_seconds is None else freshness_seconds
    observed_now = (now or datetime.now(UTC)).astimezone(UTC)
    out: list[TourSnapshot] = []
    for row in rows:
        t = row.tour
        tour_id = str(t.get("record_key") or t.get("url") or len(out))
        url = _text(t.get("url") or t.get("source_url"))
        transport = _text(t.get("transport"))
        origin = _text(t.get("departure_city"))
        dests, raw_dests = _destinations(t.get("destinations"), origin)
        route_value = t.get("route")
        route = [v for v in route_value if isinstance(v, str)] if isinstance(route_value, list) else list(raw_dests)
        snapshots: list[OfferSnapshot] = []
        for offer in row.offers:
            if not isinstance(offer, dict):
                continue
            snapshot = _offer(offer, t, tour_id, url, ttl, observed_now)
            snapshots.append(snapshot)
        out.append(
            TourSnapshot(
                id=tour_id,
                supplier=str(row.provider.get("display_name") or row.provider.get("source_key") or ""),
                name=_text(t.get("tour_name")),
                url=url,
                destinations=dests,
                raw_destinations=raw_dests,
                route=route,
                route_observed=isinstance(route_value, list) and len(route_value) >= 2,
                departure_city=origin,
                duration_days=_int(t.get("duration_days")),
                duration_nights=_int(t.get("duration_nights")),
                transport=transport if transport in _TRANSPORTS else "",
                accommodation=_text(t.get("accommodation")),
                itinerary=_text(t.get("itinerary")),
                inclusions=_text(t.get("inclusions")),
                exclusions=_text(t.get("exclusions")),
                cancellation_policy=_text(t.get("cancellation_policy")),
                surcharges=_text(t.get("surcharges")),
                child_policy=_text(t.get("child_policy")),
                evidence=_evidence(url, str(t.get("observed_at", "")), tour_id),
                observed_at=str(t.get("observed_at", "")),
                verification=_text(t.get("verification_status")) or "provider_claimed",
                detail_state=("index" if t.get("_detail_state") == "index" else "complete"),
                offers=snapshots,
            )
        )
    return out
