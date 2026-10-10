"""Catalog rows → common snapshots. Mechanical, no per-source branches."""

from __future__ import annotations

import json
import math
import re
import unicodedata
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

from backend.models import Evidence, OfferSnapshot, TourRow, TourSnapshot

_TRANSPORTS = {"flight", "bus", "train", "cruise", "mixed"}
_DEFAULT_FRESHNESS_SECONDS = {"departure_date": 86400, "price": 86400}
_ALIASES = {
    "hcmc": "city:vn:hcmc",
    "tphcm": "city:vn:hcmc",
    "hochiminhcity": "city:vn:hcmc",
    "saigon": "city:vn:hcmc",
    "hochiminh": "city:vn:hcmc",
    "hanoi": "city:vn:hanoi",
    "danang": "city:vn:danang",
    "dalat": "city:vn:dalat",
    "phuquoc": "city:vn:phuquoc",
    "halong": "city:vn:halong",
}
_PLACE_COUNTRY = {
    "vietnam": "vn", "vietnamese": "vn", "trongnuoc": "vn", "trungquoc": "cn", "china": "cn",
    "dailoan": "tw", "taiwan": "tw", "bruneidarussalam": "bn", "brunei": "bn",
    "nhatban": "jp", "japan": "jp", "hanquoc": "kr", "southkorea": "kr",
    "thailan": "th", "thailand": "th", "singapore": "sg", "malaysia": "my", "indonesia": "id",
    "philippines": "ph", "laos": "la", "campuchia": "kh", "cambodia": "kh", "myanmar": "mm",
    "usa": "us", "unitedstates": "us", "australia": "au", "phap": "fr", "france": "fr",
    "italy": "it", "duc": "de", "germany": "de", "anh": "gb", "unitedkingdom": "gb",
    "taybannha": "es", "spain": "es", "tho": "ch", "switzerland": "ch",
    "tokyo": "jp", "kyoto": "jp", "osaka": "jp", "fukuoka": "jp",
    "nagoya": "jp", "hokkaido": "jp", "seoul": "kr", "busan": "kr", "jeju": "kr",
    "thanhphohochiminh": "vn", "hanoi": "vn", "danang": "vn", "dalat": "vn",
    "phuquoc": "vn", "halong": "vn", "nhatrang": "vn", "cantho": "vn",
    "hue": "vn", "sa pa": "vn", "sapa": "vn", "shanghai": "cn", "thuonghai": "cn",
    "hangzhou": "cn", "hangchau": "cn", "wuzhen": "cn", "otran": "cn", "beijing": "cn",
    "guangzhou": "cn", "shenzhen": "cn", "chengdu": "cn", "xian": "cn",
    "taipei": "tw", "daibac": "tw", "nantou": "tw", "namdau": "tw", "taichung": "tw",
    "daitrung": "tw", "kaohsiung": "tw", "caohung": "tw", "bandarseribegawan": "bn",
}
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


def _place_key(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.replace("đ", "d").replace("Đ", "D"))
    folded = "".join(c for c in decomposed if unicodedata.category(c) != "Mn").lower()
    return re.sub(r"[^a-z0-9]", "", folded)


def _canonical_place_key(value: str) -> str:
    key = _place_key(value)
    return _ALIASES.get(key, key)


def _destinations(values: object, origin: str) -> tuple[list[str], list[str], list[str], bool]:
    raw = [v.strip() for v in values if isinstance(v, str) and v.strip()] if isinstance(values, list) else []
    visit = list(raw)
    origin_key = _canonical_place_key(origin)
    if visit and _canonical_place_key(visit[0]) == origin_key:
        visit.pop(0)
    if visit and _canonical_place_key(visit[-1]) == origin_key:
        visit.pop()
    countries: list[str] = []
    complete = bool(visit)
    for place in visit:
        key = _place_key(place)
        country = _PLACE_COUNTRY.get(key)
        if country is None:
            complete = False
        elif country not in countries:
            countries.append(country)
    return visit, raw, countries, complete


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


def _freshness(value: object, ttl: int | None, now: datetime) -> str:
    if not isinstance(ttl, int) or isinstance(ttl, bool) or ttl <= 0:
        return "unknown"
    observed = _parsed_time(value)
    if observed is None or observed > now:
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


def _number(value: object) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        return None
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        return None
    return number if number.is_finite() and number >= 0 else None


def _same_observation(left: object, right: object) -> bool:
    a, b = _parsed_time(left), _parsed_time(right)
    return a is not None and a == b


def _trusted_source(host: str, trusted_domains: set[str]) -> bool:
    normalized = host.lower().strip().rstrip(".")
    return bool(normalized and normalized in trusted_domains and "*" not in normalized)


def _validated_pricing(
    offer: dict,
    tour: dict,
    trusted_domains: set[str],
) -> tuple[str, bool | None, list[dict], list[dict], str | None]:
    offer_meta = _json_object(offer.get("field_meta"))
    pricing = offer_meta.get("pricing")
    if pricing is None:
        return "missing", None, [], [], None
    if not isinstance(pricing, dict):
        return "invalid", None, [], [], "CATALOG_PRICING_METADATA_INVALID"
    quotes = pricing.get("quotes")
    extra = pricing.get("extra_charges")
    observed_at = offer.get("observed_at")
    if (
        not _same_observation(pricing.get("observed_at"), observed_at)
        or not isinstance(quotes, list)
        or not quotes
        or not isinstance(extra, list)
        or not isinstance(pricing.get("complete"), bool)
    ):
        return "invalid", None, [], [], "CATALOG_PRICING_METADATA_INVALID"

    currency = str(offer.get("currency") or tour.get("currency") or "").upper()
    raw_price_type = str(offer.get("price_type") or tour.get("price_type") or "")
    kind_by_type = {"fixed": "exact", "from": "from", "contact": "contact"}
    expected_kind = kind_by_type.get(raw_price_type)
    base_price = _number(offer.get("price"))
    age_prices = _json_object(offer.get("price_by_age"))
    adult_price = _number(age_prices.get("adult"))
    if adult_price is None:
        adult_price = base_price
    bound_prices = {
        "per_adult": adult_price,
        "per_child": _number(age_prices.get("child")),
        "per_infant": _number(age_prices.get("infant")),
        "per_room": base_price,
        "per_group": base_price,
    }

    normalized_quotes: list[dict] = []
    for quote in quotes:
        if not isinstance(quote, dict):
            return "invalid", None, [], [], "CATALOG_PRICING_METADATA_INVALID"
        amount = _number(quote.get("amount"))
        if (
            not isinstance(quote.get("quote_id"), str)
            or not quote["quote_id"].strip()
            or amount is None
            or str(quote.get("currency", "")).upper() != currency
            or quote.get("kind") not in {"exact", "from", "range"}
            or quote.get("basis") not in {"per_adult", "per_child", "per_infant", "per_room", "per_group"}
            or quote.get("coverage") not in {"tour_price", "trip_total"}
            or not isinstance(quote.get("applicability", []), list)
        ):
            return "invalid", None, [], [], "CATALOG_PRICING_METADATA_INVALID"
        if expected_kind and quote["kind"] != expected_kind:
            return "invalid", None, [], [], "CATALOG_PRICING_METADATA_INVALID"
        raw_amount = bound_prices.get(quote["basis"])
        if raw_amount is None or amount != raw_amount:
            return "invalid", None, [], [], "CATALOG_PRICING_METADATA_INVALID"
        upper_amount = _number(quote.get("upper_amount"))
        if quote["kind"] == "range" and (upper_amount is None or upper_amount < amount):
            return "invalid", None, [], [], "CATALOG_PRICING_METADATA_INVALID"
        if quote["kind"] == "from" and quote.get("upper_amount") is not None:
            return "invalid", None, [], [], "CATALOG_PRICING_METADATA_INVALID"
        normalized = dict(quote)
        normalized["amount"] = str(amount)
        normalized["upper_amount"] = str(upper_amount) if upper_amount is not None else None
        normalized["currency"] = currency
        normalized_quotes.append(normalized)

    normalized_extra: list[dict] = []
    for charge in extra:
        if not isinstance(charge, dict):
            return "invalid", None, [], [], "CATALOG_PRICING_METADATA_INVALID"
        amount = _number(charge.get("amount"))
        if (
            amount is None
            or str(charge.get("currency", "")).upper() != currency
            or charge.get("basis") not in {"per_adult", "per_child", "per_person", "per_group", "per_room"}
            or charge.get("required") not in {True, False, None}
            or not isinstance(charge.get("applicability", []), list)
        ):
            return "invalid", None, [], [], "CATALOG_PRICING_METADATA_INVALID"
        normalized = dict(charge)
        normalized["amount"] = str(amount)
        normalized["currency"] = currency
        normalized_extra.append(normalized)

    evidence = _json_object(offer_meta.get("evidence"))
    source_url = offer_meta.get("source_url") or evidence.get("source_url") or tour.get("source_url") or tour.get("url")
    host = urlsplit(str(source_url)).hostname or ""
    if not _trusted_source(host, trusted_domains):
        return "untrusted", None, normalized_quotes, normalized_extra, None
    return "validated", pricing["complete"], normalized_quotes, normalized_extra, None


def _offer(
    o: dict,
    tour: dict,
    tour_id: str,
    tour_url: str,
    trusted_domains: set[str],
    freshness_seconds: dict[str, int],
    now: datetime,
    require_trusted_pricing: bool,
) -> OfferSnapshot:
    price = _int(o.get("price"))
    raw_basis = o.get("price_type") or tour.get("price_type") or ""
    basis = {"fixed": "exact", "from": "from", "contact": "contact"}.get(str(raw_basis))
    if price is None:
        basis = "contact"
    elif basis is None:
        # A number without an explicit fixed/from qualifier is not proven exact.
        basis = "contact"
    metadata_state, complete, quotes, charges, issue = _validated_pricing(o, tour, trusted_domains)
    if metadata_state == "validated":
        adult_quote = next(
            (q for q in quotes if q.get("basis") == "per_adult" and q.get("kind") in {"exact", "from"}),
            None,
        )
        if adult_quote is not None:
            basis = "exact" if adult_quote["kind"] == "exact" else "from"
            if price is None:
                price = _int(adult_quote["amount"])
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
        currency=str(o.get("currency") or tour.get("currency") or "VND"),
        price_basis=basis,  # type: ignore[arg-type]
        price_trusted=(not require_trusted_pricing or metadata_state == "validated"),
        price_freshness=_freshness(observed, freshness_seconds.get("price"), now),
        departure_freshness=_freshness(observed, freshness_seconds.get("departure_date"), now),
        price_freshness_policy_seconds=freshness_seconds.get("price"),
        departure_freshness_policy_seconds=freshness_seconds.get("departure_date"),
        pricing_metadata_state=metadata_state,  # type: ignore[arg-type]
        pricing_issue=issue or "",
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
    trusted_domains: list[str] | None = None,
    freshness_seconds: dict[str, int] | None = None,
    require_trusted_pricing: bool = False,
    now: datetime | None = None,
) -> list[TourSnapshot]:
    trusted = {domain.lower().strip().rstrip(".") for domain in (trusted_domains or []) if domain.strip()}
    ttl = _DEFAULT_FRESHNESS_SECONDS if freshness_seconds is None else freshness_seconds
    observed_now = (now or datetime.now(UTC)).astimezone(UTC)
    out: list[TourSnapshot] = []
    for row in rows:
        t = row.tour
        tour_id = str(t.get("record_key") or t.get("url") or len(out))
        url = _text(t.get("url") or t.get("source_url"))
        transport = _text(t.get("transport"))
        origin = _text(t.get("departure_city"))
        dests, raw_dests, countries, countries_complete = _destinations(t.get("destinations"), origin)
        route_value = t.get("route")
        route = [v for v in route_value if isinstance(v, str)] if isinstance(route_value, list) else list(raw_dests)
        snapshots: list[OfferSnapshot] = []
        for offer in row.offers:
            if not isinstance(offer, dict):
                continue
            snapshot = _offer(
                offer, t, tour_id, url, trusted, ttl, observed_now, require_trusted_pricing
            )
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
                destination_countries=countries,
                destination_country_complete=countries_complete,
                departure_city=origin,
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
