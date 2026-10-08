from decimal import Decimal
from typing import Literal

from pydantic import Field, JsonValue, model_validator

from domain.common import Identifier, Model, instant
from domain.requirements import DATE_FIELDS, FIELDS, Budget, QuerySpec, Target


class Fact[T](Model):
    value: T | None = None
    raw_value: str | None = Field(default=None, max_length=10000)
    data_state: Literal["present", "missing", "conflicting", "invalid", "unsupported"] = "missing"
    verification: Literal["supplier_published", "independently_verified", "unverified"] = "unverified"
    completeness: Literal["complete", "partial", "unknown"] = "unknown"
    observed_at: str
    evidence_ids: list[Identifier] = Field(default_factory=list, max_length=30)
    unit: str | None = None
    scope: str | None = None
    normalization_rule: str | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def valid_fact(self):
        instant(self.observed_at)
        if self.data_state == "present" and (self.value is None or not self.evidence_ids):
            raise ValueError("Present fact requires value and evidence")
        if self.data_state != "present" and self.value is not None:
            raise ValueError("Non-present fact cannot claim a value")
        return self


class Evidence(Model):
    id: Identifier
    snapshot_id: Identifier
    url: str
    publisher: Identifier
    method: Literal["json_ld", "json", "api", "html", "synthetic_fixture"]
    locator: str = Field(max_length=1000)
    raw_quote: str = Field(max_length=10000)
    observed_at: str

    @model_validator(mode="after")
    def timestamp(self):
        instant(self.observed_at)
        Target(target_id="validation", url=self.url)
        return self


class Supplier(Model):
    supplier_id: Identifier
    display_name: str = Field(min_length=1, max_length=200)


class Applicability(Model):
    field: Literal["adults", "children_count", "rooming", "unresolved"]
    value: int | str


class PriceQuote(Model):
    quote_id: Identifier
    kind: Literal["exact", "from", "range"]
    amount: int | str
    upper_amount: int | str | None = None
    currency: str
    basis: Literal["per_adult", "per_child", "per_infant", "per_room", "per_group"]
    coverage: Literal["tour_price", "trip_total", "unspecified"]
    age_min: int | None = Field(default=None, ge=0, le=120)
    age_max_exclusive: int | None = Field(default=None, ge=1, le=121)
    applicability: list[Applicability] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def valid_price(self):
        Budget(amount=self.amount, upper=self.upper_amount, currency=self.currency)
        if self.kind == "range" and self.upper_amount is None:
            raise ValueError("Price range requires upper bound")
        if self.kind != "range" and self.upper_amount is not None:
            raise ValueError("Only range price has upper bound")
        if (self.age_min is None) != (self.age_max_exclusive is None):
            raise ValueError("Age bracket requires both bounds")
        if self.age_min is not None and self.age_min >= self.age_max_exclusive:
            raise ValueError("Invalid age bracket")
        return self


class ExtraCharge(Model):
    charge_id: Identifier
    amount: int | str
    currency: str
    basis: Literal["per_adult", "per_child", "per_person", "per_group", "per_room"]
    required: bool | None
    applicability: list[Applicability] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def valid_price(self):
        Budget(amount=self.amount, currency=self.currency)
        return self


def validate_fields(fields: dict[str, Fact[JsonValue]], *, offer: bool):
    from datetime import date

    static = set(FIELDS) - {"estimated_cost", "unsupported", *DATE_FIELDS}
    allowed = {*DATE_FIELDS, "availability"} if offer else static
    for name, fact in fields.items():
        if name not in allowed:
            raise ValueError(f"Unsupported snapshot field: {name}")
        if fact.data_state != "present":
            continue
        v = fact.value
        if name in {"destinations", "included_services", "transport"}:
            if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
                raise ValueError(f"{name} must be list[str]")
        elif name in {"departure_origin", "supplier"}:
            if not isinstance(v, str):
                raise ValueError(f"{name} must be string")
        elif name in DATE_FIELDS:
            if not isinstance(v, str):
                raise ValueError("Date must be ISO string")
            date.fromisoformat(v)
        else:
            if type(v) is not int or v < 0:
                raise ValueError(f"{name} must be nonnegative integer")
            if name == "hotel_stars_min" and not 1 <= v <= 5:
                raise ValueError("Invalid hotel rating")


class TourSnapshot(Model):
    snapshot_id: Identifier
    tour_id: Identifier
    supplier_id: Identifier
    canonical_url: str
    observed_at: str
    title: str | None = Field(default=None, min_length=1, max_length=500)
    policies: dict[str, Fact[str]] = Field(default_factory=dict, max_length=20)
    fields: dict[str, Fact[JsonValue]] = Field(default_factory=dict, max_length=30)

    @model_validator(mode="after")
    def valid(self):
        instant(self.observed_at)
        Target(target_id="validation", url=self.canonical_url)
        validate_fields(self.fields, offer=False)
        return self


class OfferSnapshot(Model):
    snapshot_id: Identifier
    offer_id: Identifier
    tour_snapshot_id: Identifier
    fields: dict[str, Fact[JsonValue]] = Field(default_factory=dict, max_length=10)
    price_quotes: list[Fact[PriceQuote]] = Field(default_factory=list, max_length=50)
    extra_charges: list[Fact[ExtraCharge]] = Field(default_factory=list, max_length=50)
    # A sourced assertion that all mandatory charges/discounts are represented.
    pricing_complete: Fact[bool] | None = None

    @model_validator(mode="after")
    def valid(self):
        validate_fields(self.fields, offer=True)
        ids = [q.value.quote_id for q in self.price_quotes if q.value]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate quote ID")
        return self


class SourceResult(Model):
    source_id: Identifier
    target_id: Identifier | None = None
    status: Literal["ok", "partial", "blocked", "unsupported", "timeout", "error"]
    reason_code: str | None = None
    tour_snapshot_ids: list[Identifier] = Field(default_factory=list)
    offer_snapshot_ids: list[Identifier] = Field(default_factory=list)
    truncated: bool = False


class Issue(Model):
    code: str
    source_id: Identifier
    target_id: Identifier | None = None
    snapshot_id: Identifier | None = None
    field_path: str | None = None
    explanation: str
    retryable: bool = False


class CrawlResult(Model):
    schema_version: Literal["1.0"] = "1.0"
    request_id: Identifier
    origin: Literal["source", "synthetic"]
    source_results: list[SourceResult] = Field(max_length=100)
    suppliers: list[Supplier] = Field(default_factory=list, max_length=100)
    tours: list[TourSnapshot] = Field(default_factory=list, max_length=500)
    offers: list[OfferSnapshot] = Field(default_factory=list, max_length=2000)
    evidence: list[Evidence] = Field(default_factory=list, max_length=10000)
    issues: list[Issue] = Field(default_factory=list, max_length=2000)

    @model_validator(mode="after")
    def references(self):
        def unique(items, attr):
            out = {getattr(x, attr): x for x in items}
            if len(out) != len(items):
                raise ValueError(f"Duplicate {attr}")
            return out

        suppliers = unique(self.suppliers, "supplier_id")
        tours = unique(self.tours, "snapshot_id")
        offers = unique(self.offers, "snapshot_id")
        evidence = unique(self.evidence, "id")
        if set(tours) & set(offers):
            raise ValueError("Snapshot IDs collide")
        for t in tours.values():
            if t.supplier_id not in suppliers:
                raise ValueError("Dangling supplier")
        for o in offers.values():
            if o.tour_snapshot_id not in tours:
                raise ValueError("Dangling offer tour")
        for e in evidence.values():
            tour = tours.get(e.snapshot_id)
            if tour is None and e.snapshot_id in offers:
                tour = tours[offers[e.snapshot_id].tour_snapshot_id]
            if tour is None or e.publisher != tour.supplier_id:
                raise ValueError("Evidence entity/publisher mismatch")
            if (e.method == "synthetic_fixture") != (self.origin == "synthetic"):
                raise ValueError("Evidence origin mismatch")
        for snapshot in [*tours.values(), *offers.values()]:
            facts = list(snapshot.fields.values())
            if isinstance(snapshot, TourSnapshot):
                facts += list(snapshot.policies.values())
            if isinstance(snapshot, OfferSnapshot):
                facts += [*snapshot.price_quotes, *snapshot.extra_charges]
                if snapshot.pricing_complete:
                    facts.append(snapshot.pricing_complete)
            for fact in facts:
                if any(
                    eid not in evidence or evidence[eid].snapshot_id != snapshot.snapshot_id
                    for eid in fact.evidence_ids
                ):
                    raise ValueError("Fact/evidence snapshot mismatch")
        for result in self.source_results:
            if any(x not in tours for x in result.tour_snapshot_ids) or any(
                x not in offers for x in result.offer_snapshot_ids
            ):
                raise ValueError("Source result has dangling snapshots")
            if any(
                offers[x].tour_snapshot_id not in result.tour_snapshot_ids for x in result.offer_snapshot_ids
            ):
                raise ValueError("Source result offer/tour mismatch")
        return self


class SourceCapability(Model):
    source_id: Identifier
    supplier_id: Identifier
    approved_domains: list[str] = Field(min_length=1)
    access_status: Literal["approved", "blocked", "unchecked"]
    checked_at: str
    modes: list[Literal["discover", "compare_urls"]]
    searchable_fields: list[str] = Field(default_factory=list)
    returned_fields: list[str] = Field(default_factory=list)
    pushdown_semantics: dict[str, str] = Field(default_factory=dict)
    limits: dict[str, int] = Field(default_factory=dict)
    freshness_seconds: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def valid(self):
        instant(self.checked_at)
        if any(x <= 0 for x in self.freshness_seconds.values()):
            raise ValueError("Freshness TTL must be positive")
        return self


class CrawlRequest(Model):
    schema_version: Literal["1.0"] = "1.0"
    request_id: Identifier
    mode: Literal["discover", "compare_urls"]
    source_ids: list[Identifier]
    query: QuerySpec
    targets: list[Target]
    deadline_at: str


def money_wire(value: Decimal | None, currency: str):
    if value is None:
        return None
    return int(value) if currency == "VND" else format(value, "f")
