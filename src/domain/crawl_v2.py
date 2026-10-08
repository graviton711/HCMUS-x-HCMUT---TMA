"""Optional evidence-bound semantic facts on v2 snapshots."""

from typing import Literal

from pydantic import Field, JsonValue, model_validator

from domain.common import Identifier, Model, instant
from domain.crawl import CrawlResult, Evidence, ExtraCharge, Fact, OfferSnapshot, PriceQuote, TourSnapshot

NATURE_TAGS = {"beach", "forest", "mountain", "waterfall", "national_park", "river", "lake", "countryside"}
CATALOG_POLICY = "catalog-validation-v1"
CATALOG_CHECKS = {"schema", "record_binding", "source_url", "timestamp", "normalization"}


class FactV2[T](Fact[T]):
    verification: Literal[
        "supplier_published", "independently_verified", "catalog_validated", "unverified"
    ] = "unverified"

    @model_validator(mode="before")
    @classmethod
    def legacy_fact(cls, value):
        return value.model_dump() if isinstance(value, Fact) and not isinstance(value, cls) else value


class CatalogValidation(Model):
    policy_version: Literal["catalog-validation-v1"] = CATALOG_POLICY
    source_id: Identifier
    checks: list[Literal["schema", "record_binding", "source_url", "timestamp", "normalization"]]

    @model_validator(mode="after")
    def complete_checks(self):
        if set(self.checks) != CATALOG_CHECKS or len(self.checks) != len(CATALOG_CHECKS):
            raise ValueError("Catalog validation requires every check exactly once")
        return self


class CatalogRecordRef(Model):
    table: Literal["tours", "offers"]
    record_key: Identifier
    field: Identifier
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class EvidenceV2(Evidence):
    method: Literal["json_ld", "json", "api", "html", "synthetic_fixture", "database_record"]
    record_ref: CatalogRecordRef | None = None
    catalog_validation: CatalogValidation | None = None

    @model_validator(mode="after")
    def record_binding(self):
        if (self.method == "database_record") != (self.record_ref is not None):
            raise ValueError("Database provenance requires an explicit record reference")
        if self.catalog_validation is not None and (
            self.method != "database_record"
            or self.publisher != "supplier_" + self.catalog_validation.source_id.removeprefix("catalog_")
            or not self.catalog_validation.source_id.startswith("catalog_")
        ):
            raise ValueError("Catalog receipt requires bound database provenance and supplier")
        return self


class CatalogFieldProof(Model):
    record_key: Identifier
    field: Identifier
    value: JsonValue
    url: str
    raw_value: str = Field(min_length=1, max_length=10000)
    raw_quote: str = Field(min_length=1, max_length=10000)
    locator: str = Field(min_length=1, max_length=1000)
    method: Literal["json_ld", "json", "api", "html"]
    observed_at: str
    scope: str | None = None
    completeness: Literal["complete", "partial", "unknown"] = "unknown"

    @model_validator(mode="after")
    def grounded(self):
        instant(self.observed_at)
        if self.raw_value not in self.raw_quote:
            raise ValueError("Field proof must preserve a verbatim quote")
        return self


class TourSnapshotV2(TourSnapshot):
    fields: dict[str, FactV2[JsonValue]] = Field(default_factory=dict, max_length=30)
    policies: dict[str, FactV2[str]] = Field(default_factory=dict, max_length=20)
    semantic_fields: dict[str, FactV2[JsonValue]] = Field(default_factory=dict, max_length=3)
    catalog_fields: dict[str, FactV2[JsonValue]] = Field(default_factory=dict, max_length=2)

    @model_validator(mode="after")
    def semantic_values(self):
        if set(self.catalog_fields) - {"published_price", "itinerary"}:
            raise ValueError("Unknown catalog preview field")
        for name, fact in self.semantic_fields.items():
            if name not in {"tour_type", "route", "nature"}:
                raise ValueError("Semantic fact needs an implemented field policy")
            if fact.data_state != "present":
                continue
            value = fact.value
            if name == "tour_type":
                if not isinstance(value, str) or value not in {"join_group", "private_group"}:
                    raise ValueError("Invalid tour type")
            elif not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                raise ValueError("Route/nature must be list[str]")
            elif name == "nature" and set(value) - NATURE_TAGS:
                raise ValueError("Nature tags require the reviewed taxonomy")
            if name in {"route", "nature"} and fact.scope != "itinerary":
                raise ValueError("Route/nature facts require itinerary scope")
        return self


class OfferSnapshotV2(OfferSnapshot):
    fields: dict[str, FactV2[JsonValue]] = Field(default_factory=dict, max_length=10)
    price_quotes: list[FactV2[PriceQuote]] = Field(default_factory=list, max_length=50)
    extra_charges: list[FactV2[ExtraCharge]] = Field(default_factory=list, max_length=50)
    pricing_complete: FactV2[bool] | None = None
    catalog_fields: dict[str, FactV2[JsonValue]] = Field(default_factory=dict, max_length=3)

    @model_validator(mode="after")
    def catalog_values(self):
        if set(self.catalog_fields) - {"availability_status", "unclassified_prices", "single_supplement"}:
            raise ValueError("Unknown offer preview field")
        return self


class CrawlResultV2(CrawlResult):
    retrieval: dict[str, JsonValue] = Field(default_factory=dict)
    offer_coverage: dict[str, bool] = Field(default_factory=dict)
    tours: list[TourSnapshotV2] = Field(default_factory=list, max_length=500)
    offers: list[OfferSnapshotV2] = Field(default_factory=list, max_length=2000)
    evidence: list[EvidenceV2] = Field(default_factory=list, max_length=10000)

    @model_validator(mode="before")
    @classmethod
    def legacy_instances(cls, data):
        if isinstance(data, dict):
            data = dict(data)
            for field, legacy, current in [
                ("tours", TourSnapshot, TourSnapshotV2),
                ("offers", OfferSnapshot, OfferSnapshotV2),
                ("evidence", Evidence, EvidenceV2),
            ]:
                if field in data:
                    data[field] = [
                        item.model_dump()
                        if isinstance(item, legacy) and not isinstance(item, current)
                        else item
                        for item in data[field]
                    ]
        return data

    @model_validator(mode="after")
    def semantic_evidence(self):
        evidence = {e.id: e for e in self.evidence}
        tours = {t.snapshot_id: t for t in self.tours}
        offers = {o.snapshot_id: o for o in self.offers}
        if set(self.offer_coverage) - tours.keys():
            raise ValueError("Offer coverage belongs to a different snapshot")
        for ev in self.evidence:
            if ev.method == "database_record":
                ref = ev.record_ref
                owner = offers.get(ev.snapshot_id) if ref.table == "offers" else tours.get(ev.snapshot_id)
                eid = (
                    getattr(owner, "offer_id", None)
                    if ref.table == "offers"
                    else getattr(owner, "tour_id", None)
                )
                prefix = "catalog_offer_" if ref.table == "offers" else "catalog_tour_"
                if owner is None or eid != prefix + ref.record_key:
                    raise ValueError("Database provenance belongs to a different record")
        for snapshot in [*self.tours, *self.offers]:
            expected_columns = {
                id(fact): "departure_city" if name == "departure_origin" else name
                for name, fact in snapshot.fields.items()
            }
            expected_columns.update({id(fact): name for name, fact in snapshot.catalog_fields.items()})
            if isinstance(snapshot, TourSnapshotV2):
                expected_columns.update({id(fact): name for name, fact in snapshot.semantic_fields.items()})
                expected_columns.update(
                    {
                        id(fact): "cancellation_policy" if name == "cancellation" else name
                        for name, fact in snapshot.policies.items()
                    }
                )
            facts = list(snapshot.catalog_fields.values())
            if isinstance(snapshot, TourSnapshotV2):
                facts += list(snapshot.semantic_fields.values())
            for fact in facts:
                if any(
                    eid not in evidence or evidence[eid].snapshot_id != snapshot.snapshot_id
                    for eid in fact.evidence_ids
                ):
                    raise ValueError("Semantic fact/evidence snapshot mismatch")
            facts += list(snapshot.fields.values())
            if isinstance(snapshot, TourSnapshotV2):
                facts += list(snapshot.policies.values())
            else:
                facts += snapshot.price_quotes + snapshot.extra_charges
                if snapshot.pricing_complete:
                    facts.append(snapshot.pricing_complete)
            for fact in facts:
                if fact.verification == "catalog_validated":
                    if (
                        fact.data_state != "present"
                        or id(fact) not in expected_columns
                        or any(
                            evidence[eid].catalog_validation is None
                            or evidence[eid].observed_at != fact.observed_at
                            or evidence[eid].record_ref is None
                            or evidence[eid].record_ref.field != expected_columns[id(fact)]
                            or evidence[eid].raw_quote != fact.raw_value
                            for eid in fact.evidence_ids
                        )
                    ):
                        raise ValueError("Catalog fact requires receipt and matching observation")
                elif fact.verification != "unverified" and any(
                    evidence[eid].method == "database_record" for eid in fact.evidence_ids
                ):
                    raise ValueError("Database record provenance cannot verify website facts")
        return self
