"""Catalog rows → common snapshots. Mechanical, no per-source branches."""

from __future__ import annotations

from backend.models import Evidence, OfferSnapshot, TourRow, TourSnapshot

_TRANSPORTS = {"flight", "bus", "train", "cruise", "mixed"}


def _text(value: object) -> str:
    return value if isinstance(value, str) else ""


def _int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _evidence(url: str, observed_at: str, record_ref: str) -> Evidence:
    return Evidence(
        url=url,
        method="database_record",
        observed_at=observed_at if isinstance(observed_at, str) else "",
        record_ref=record_ref,
    )


def _offer(o: dict, tour_id: str, tour_url: str) -> OfferSnapshot:
    price = _int(o.get("price"))
    raw_basis = o.get("price_type", "")
    if price is None:
        basis = "contact"
    elif raw_basis == "from":
        basis = "from"
    else:
        basis = "exact"
    availability = o.get("availability", "unknown")
    if availability not in ("available", "sold_out", "unknown"):
        availability = "unknown"
    departure = o.get("departure_date", "")
    return OfferSnapshot(
        id=str(o.get("record_key") or f"{tour_id}@{departure}"),
        tour_id=tour_id,
        departure_date=departure if isinstance(departure, str) else "",
        price=price,
        currency=o.get("currency", "VND") or "VND",
        price_basis=basis,  # type: ignore[arg-type]
        availability=availability,
        conditions=_text(o.get("conditions")),
        evidence=_evidence(tour_url, str(o.get("observed_at", "")), str(o.get("record_key", ""))),
    )


def rows_to_snapshots(rows: list[TourRow]) -> list[TourSnapshot]:
    out: list[TourSnapshot] = []
    for row in rows:
        t = row.tour
        tour_id = str(t.get("record_key") or t.get("url") or len(out))
        url = _text(t.get("url") or t.get("source_url"))
        transport = _text(t.get("transport"))
        snapshots = [
            _offer(o, tour_id, url) for o in row.offers if isinstance(o, dict)
        ]
        dests = t.get("destinations")
        out.append(
            TourSnapshot(
                id=tour_id,
                supplier=str(row.provider.get("display_name") or row.provider.get("source_key") or ""),
                name=_text(t.get("tour_name")),
                url=url,
                destinations=[d for d in dests if isinstance(d, str)] if isinstance(dests, list) else [],
                departure_city=_text(t.get("departure_city")),
                duration_days=_int(t.get("duration_days")),
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
                offers=snapshots,
            )
        )
    return out
