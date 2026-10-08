"""Optional evidence-bound semantic facts on v2 snapshots."""

from typing import Literal

from pydantic import Field, JsonValue, model_validator

from domain.common import Identifier, Model, instant
from domain.crawl import CrawlResult, Evidence, Fact, OfferSnapshot, TourSnapshot

NATURE_TAGS = {"beach", "forest", "mountain", "waterfall", "national_park", "river", "lake", "countryside"}


class CatalogRecordRef(Model):
    table: Literal["tours", "offers"]
    record_key: Identifier
    field: Identifier
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class EvidenceV2(Evidence):
    method: Literal["json_ld", "json", "api", "html", "synthetic_fixture", "database_record"]
    record_ref: CatalogRecordRef | None = None

    @model_validator(mode="after")
    def record_binding(self):
        if (self.method == "database_record") != (self.record_ref is not None):
            raise ValueError("Database provenance requires an explicit record reference")
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
    semantic_fields: dict[str, Fact[JsonValue]] = Field(default_factory=dict, max_length=3)
    catalog_fields: dict[str, Fact[JsonValue]] = Field(default_factory=dict, max_length=2)

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
    catalog_fields: dict[str, Fact[JsonValue]] = Field(default_factory=dict, max_length=3)

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
                if fact.verification != "unverified" and any(
                    evidence[eid].method == "database_record" for eid in fact.evidence_ids
                ):
                    raise ValueError("Database record provenance cannot verify website facts")
        return self
