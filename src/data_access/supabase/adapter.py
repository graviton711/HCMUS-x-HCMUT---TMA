"""Translate catalog rows without fabricating website evidence or qualifiers."""

import hashlib
import json
import re
from datetime import date, datetime, timedelta
from decimal import Decimal
from functools import wraps
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from data_access.supabase.policy import CATALOG_FIELDS, TEXT_FIELDS, receipt, trusted_source
from domain.common import instant, now
from domain.crawl_v2 import CatalogFieldProof, CrawlResultV2
from requirements.catalog import expand_entities, resolve_entities
from requirements.normalize import fold


def wire(value):
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else format(value, "f")
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): wire(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [wire(v) for v in value]
    return value


def encoded(value):
    return json.dumps(wire(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def source_id(provider):
    return "catalog_" + provider["source_key"].strip()


def supplier_id(provider):
    return "supplier_" + provider["source_key"].strip()


def entity_id(row):
    return "catalog_tour_" + row["record_key"].strip()


def candidate_id(row, provider):
    return (
        "tour_"
        + hashlib.sha256(json.dumps([supplier_id(provider), entity_id(row)]).encode()).hexdigest()[:32]
    )


def lookup_url(url):
    """Only discard known tracking keys/fragments; preserve functional query parameters."""
    u = urlsplit(url)
    if u.scheme not in {"https", "http"} or not u.hostname or u.username or u.password:
        raise ValueError("Invalid catalog URL")
    params = [
        (k, v)
        for k, v in parse_qsl(u.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in {"gclid", "fbclid"}
    ]
    host = u.hostname.lower()
    if u.port and not (u.scheme == "https" and u.port == 443 or u.scheme == "http" and u.port == 80):
        host += f":{u.port}"
    return urlunsplit((u.scheme.lower(), host, u.path or "/", urlencode(params), ""))


def places(values):
    if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
        raise ValueError("Catalog place list must contain strings")
    members = resolve_entities("destinations", values).members
    return list(dict.fromkeys(m.entity_id for m in members if m.entity_id)), any(
        m.entity_id is None for m in members
    )


def relevance(row, conditions):
    """Retrieval priority only. Unverified mismatches never become hard exclusions."""
    found, _ = places(row.get("destinations", []))
    origins = resolve_entities("departure_origin", [row.get("departure_city", "")]).members
    score = 0
    for c in conditions:
        if c.field not in {"destinations", "departure_origin"} or c.operator in {"excludes", "not_in"}:
            continue
        expected = set(getattr(c.value, "items", [])) | {
            m.entity_id for m in getattr(c.value, "members", []) if m.entity_id
        }
        actual = (
            expand_entities(found, "place") if c.field == "destinations" else {m.entity_id for m in origins}
        )
        score += bool(expected & actual)
    return score


def proof_grounded(value, raw, field):
    if isinstance(value, date) and not isinstance(value, datetime):
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                if datetime.strptime(raw.strip(), fmt).date() == value:
                    return True
            except ValueError:
                pass
        return False
    if isinstance(value, str):
        if fold(value) == fold(raw):
            return True
        entity_field = (
            "departure_origin" if field == "departure_city" else "transport" if field == "transport" else None
        )
        if entity_field:
            enum = {"bus": "coach", "flight": "flight", "train": "train"}.get(value)
            ids = resolve_entities(entity_field, [value, raw]).members
            return bool(ids and ids[-1].entity_id and (enum or ids[0].entity_id) == ids[-1].entity_id)
        return False
    if isinstance(value, list):
        return bool(value) and all(isinstance(x, str) and fold(x) in fold(raw) for x in value)
    if isinstance(value, (int, Decimal)) and not isinstance(value, bool):
        matches = re.findall(r"[+-]?\d+(?:[.,]\d+)*", raw)
        if len(matches) != 1:
            return False
        numeric = matches[0]
        if re.fullmatch(r"[+-]?\d{1,3}(?:[.,]\d{3})+", numeric):
            numeric = numeric.replace(".", "").replace(",", "")
        try:
            return Decimal(numeric) == Decimal(str(value))
        except ArithmeticError:
            return False
    return encoded(value) == raw


def atomic_record(fn):
    @wraps(fn)
    def guarded(self, *args, **kwargs):
        lengths = {k: len(v) for k, v in self.payload.items() if isinstance(v, list)}
        providers, tours = dict(self.providers), dict(self.tour_rows)
        try:
            return fn(self, *args, **kwargs)
        except (ValueError, TypeError, KeyError, AttributeError, ArithmeticError):
            for k, length in lengths.items():
                del self.payload[k][length:]
            self.providers, self.tour_rows = providers, tours
            raise

    return guarded


class CatalogAdapter:
    def __init__(self, request_id, *, registry=(), trusted_domains=()):
        self.sources = {s.source_id: s for s in registry}
        self.trusted_domains = set(trusted_domains)
        self.payload = {
            "request_id": request_id,
            "origin": "source",
            "source_results": [],
            "suppliers": [],
            "tours": [],
            "offers": [],
            "evidence": [],
            "issues": [],
        }
        self.providers, self.tour_rows = {}, {}

    def catalog_source(self, row, table, provider, url):
        source = self.sources.get(source_id(provider))
        if not trusted_source(source, provider, url, self.trusted_domains):
            return None
        tour_row = row if table == "tours" else self.tour_rows[row["tour_id"]][0]
        if any(
            urlsplit(candidate).hostname != urlsplit(url).hostname
            for candidate in [tour_row.get("url"), tour_row.get("canonical_url")]
            if candidate
        ):
            return None
        return source

    def issue(self, code, source, explanation, **refs):
        if len(self.payload["issues"]) < 1900:
            self.payload["issues"].append(
                {"code": code, "source_id": source, "explanation": explanation, **refs}
            )

    def fact(
        self,
        row,
        table,
        field,
        value,
        snapshot,
        provider,
        url,
        *,
        state="present",
        scope=None,
        normalization=None,
        reason=None,
        allow_proof=True,
    ):
        original = row
        for part in field.split("."):
            original = original.get(part) if isinstance(original, dict) else None
        timestamp = wire(row["observed_at"])
        if instant(timestamp) > now() + timedelta(minutes=5):
            raise ValueError("Catalog observation is in the future")
        raw = original if isinstance(original, str) else encoded(original)
        raw = raw[:10000]
        ev = {
            "id": "ev_" + digest([snapshot, field])[:32],
            "snapshot_id": snapshot,
            "url": url,
            "publisher": supplier_id(provider),
            "method": "database_record",
            "locator": f"public.{table}/{row['record_key'].strip()}/{field}",
            "raw_quote": raw,
            "observed_at": timestamp,
            "record_ref": {
                "table": table,
                "record_key": row["record_key"].strip(),
                "field": field,
                "content_hash": digest(row),
            },
        }
        verification, completeness = "unverified", "unknown"
        metadata = row.get("evidence")
        proofs = metadata.get("fields", {}) if isinstance(metadata, dict) else {}
        proof_raw = proofs.get(field) if isinstance(proofs, dict) else None
        if not isinstance(proofs, dict):
            self.issue(
                "CATALOG_FIELD_PROOF_INVALID",
                source_id(provider),
                "Field evidence metadata không đúng cấu trúc; giữ record chưa kiểm chứng.",
                snapshot_id=snapshot,
                field_path=field,
            )
        proof_requested = isinstance(proofs, dict) and field in proofs
        if proof_requested and allow_proof:
            try:
                proof = CatalogFieldProof.model_validate(proof_raw)
                if (
                    proof.record_key != row["record_key"].strip()
                    or proof.field != field
                    or encoded(proof.value) != encoded(original)
                    or instant(proof.observed_at) != instant(timestamp)
                    or lookup_url(proof.url) != lookup_url(url)
                    or scope
                    and proof.scope != scope
                    or not proof_grounded(original, proof.raw_value, field)
                ):
                    raise ValueError("Field proof binding mismatch")
                ev.update(
                    method=proof.method,
                    url=proof.url,
                    locator=proof.locator,
                    raw_quote=proof.raw_quote,
                    observed_at=proof.observed_at,
                    record_ref=None,
                )
                raw, verification, completeness = proof.raw_value, "supplier_published", proof.completeness
                scope = scope or proof.scope
            except (ValueError, TypeError, AttributeError):
                self.issue(
                    "CATALOG_FIELD_PROOF_INVALID",
                    source_id(provider),
                    "Bằng chứng field không khớp record/value/time/URL/scope; giữ dữ kiện chưa kiểm chứng.",
                    snapshot_id=snapshot,
                    field_path=field,
                )
        elif (
            allow_proof
            and isinstance(proofs, dict)
            and (metadata is None or isinstance(metadata, dict))
            and field in CATALOG_FIELDS
            and state == "present"
            and self.catalog_source(row, table, provider, url) is not None
        ):
            try:
                if (
                    isinstance(metadata, dict)
                    and "observed_at" in metadata
                    and instant(metadata["observed_at"]) != instant(timestamp)
                ):
                    raise ValueError("Catalog metadata timestamp mismatch")
                ev["catalog_validation"] = receipt(self.sources[source_id(provider)])
                verification = "catalog_validated"
                completeness = "unknown" if field in TEXT_FIELDS else "complete"
            except (ValueError, TypeError, AttributeError):
                self.issue(
                    "CATALOG_METADATA_INVALID",
                    source_id(provider),
                    "Metadata catalog không khớp thời điểm row; giữ dữ kiện chưa kiểm tra.",
                    snapshot_id=snapshot,
                    field_path=field,
                )
        self.payload["evidence"].append(ev)
        return {
            "value": wire(value) if state == "present" else None,
            "raw_value": raw,
            "data_state": state,
            "verification": verification,
            "completeness": completeness,
            "observed_at": timestamp,
            "evidence_ids": [ev["id"]],
            "scope": scope,
            "normalization_rule": normalization,
            "reason": reason or ("DATABASE_FIELD_EVIDENCE_MISSING" if verification == "unverified" else None),
        }

    @atomic_record
    def add_tour(self, row, provider):
        key = row["record_key"].strip()
        url = row.get("canonical_url") or row["url"]
        lookup_url(url)
        policy = (
            receipt(self.sources[source_id(provider)])
            if self.catalog_source(row, "tours", provider, url) is not None
            else None
        )
        snapshot = "catalog_ts_" + digest([row, policy] if policy else row)[:40]
        if provider["id"] not in self.providers:
            self.providers[provider["id"]] = provider
            self.payload["suppliers"].append(
                {"supplier_id": supplier_id(provider), "display_name": provider["display_name"]}
            )
        origin = resolve_entities("departure_origin", [row.get("departure_city", "")]).members[0].entity_id
        destinations, partial = places(row.get("destinations", []))

        def f(column, value, **kw):
            return self.fact(row, "tours", column, value, snapshot, provider, url, **kw)

        fields = {
            "departure_origin": f(
                "departure_city",
                origin,
                state="present" if origin else "unsupported",
                normalization="tour-entities-v2.1",
            ),
            "destinations": f(
                "destinations",
                destinations,
                state="present" if destinations else "unsupported",
                normalization="tour-entities-v2.1",
            ),
        }
        if partial:
            fields["destinations"]["completeness"] = "partial"
            self.issue(
                "CATALOG_PLACE_UNRESOLVED",
                source_id(provider),
                "Một số địa danh chưa có canonical ID; giữ nguyên dữ liệu gốc.",
                snapshot_id=snapshot,
            )
        for name in ("duration_days", "duration_nights"):
            v = row.get(name)
            fields[name] = f(name, v, state="present" if type(v) is int and v >= 0 else "invalid")
        transport = {"bus": "coach", "flight": "flight", "train": "train"}.get(row.get("transport"))
        fields["transport"] = f(
            "transport",
            [transport] if transport else None,
            state="present" if transport else "unsupported",
            normalization="catalog-transport-enum-v1",
        )
        policies = {}
        for column, name in [
            ("inclusions", "inclusions"),
            ("exclusions", "exclusions"),
            ("cancellation_policy", "cancellation"),
            ("surcharges", "surcharges"),
            ("child_policy", "child_policy"),
        ]:
            text = row.get(column)
            if isinstance(text, str) and text:
                policies[name] = f(column, text[:10000])
        previews = {}
        if row.get("price") is not None:
            previews["published_price"] = f(
                "price",
                {
                    "amount": wire(row["price"]),
                    "currency": row.get("currency"),
                    "kind": row.get("price_type"),
                    "basis": "unspecified",
                    "coverage": "unspecified",
                },
                allow_proof=False,
                reason="CATALOG_PRICE_QUALIFIERS_UNCONFIRMED",
            )
        if row.get("itinerary"):
            previews["itinerary"] = f("itinerary", row["itinerary"][:10000])
        routes, route_partial = places(row.get("route", []))
        semantic = {}
        if routes:
            semantic["route"] = f("route", routes, scope="itinerary", normalization="tour-entities-v2.1")
            if route_partial:
                semantic["route"]["completeness"] = "partial"
        tour = {
            "snapshot_id": snapshot,
            "tour_id": "catalog_tour_" + key,
            "supplier_id": supplier_id(provider),
            "canonical_url": url,
            "observed_at": wire(row["observed_at"]),
            "title": row["tour_name"][:500],
            "fields": fields,
            "policies": policies,
            "catalog_fields": previews,
            "semantic_fields": semantic,
        }
        from domain.crawl_v2 import TourSnapshotV2

        TourSnapshotV2.model_validate(tour)
        self.payload["tours"].append(tour)
        self.tour_rows[row["id"]] = (row, tour, provider)
        return tour

    @atomic_record
    def add_offer(self, row):
        tour_row, tour, provider = self.tour_rows[row["tour_id"]]
        snapshot = "catalog_os_" + digest([row, tour["snapshot_id"]])[:40]

        def f(column, value, **kw):
            return self.fact(row, "offers", column, value, snapshot, provider, tour["canonical_url"], **kw)

        departure = wire(row.get("departure_date"))
        fields = {
            "departure_date": f("departure_date", departure, state="present" if departure else "missing")
        }
        previews = {"availability_status": f("availability", row.get("availability"))}
        prices = row.get("price_by_age")
        if isinstance(prices, dict) and prices:
            previews["unclassified_prices"] = f(
                "price_by_age", prices, allow_proof=False, reason="CATALOG_AGE_BRACKETS_UNCONFIRMED"
            )
        if row.get("single_supplement") is not None:
            previews["single_supplement"] = f(
                "single_supplement",
                row["single_supplement"],
                allow_proof=False,
                reason="CATALOG_SUPPLEMENT_APPLICABILITY_UNKNOWN",
            )
        quotes = []
        adult = prices.get("adult") if isinstance(prices, dict) else None
        if (
            adult is not None
            and tour_row.get("currency") == "VND"
            and tour_row.get("price_type") in {"from", "exact"}
        ):
            amount = Decimal(str(adult))
            if amount >= 0 and amount == amount.to_integral_value():
                quotes.append(
                    f(
                        "price_by_age.adult",
                        {
                            "quote_id": "catalog_pq_" + digest([snapshot, "adult"])[:32],
                            "kind": tour_row["price_type"],
                            "amount": int(amount),
                            "currency": "VND",
                            "basis": "per_adult",
                            "coverage": "unspecified",
                        },
                        allow_proof=False,
                        reason="CATALOG_PRICE_QUALIFIERS_UNCONFIRMED",
                    )
                )
        offer = {
            "snapshot_id": snapshot,
            "offer_id": "catalog_offer_" + row["record_key"].strip(),
            "tour_snapshot_id": tour["snapshot_id"],
            "fields": fields,
            "price_quotes": quotes,
            "extra_charges": [],
            "catalog_fields": previews,
        }
        from domain.crawl_v2 import OfferSnapshotV2

        OfferSnapshotV2.model_validate(offer)
        self.payload["offers"].append(offer)
        return offer

    def finish(self):
        return CrawlResultV2.model_validate(self.payload)
