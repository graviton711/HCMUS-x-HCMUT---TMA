"""Single source of truth for backend types. No other model packages exist."""

from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

State = Literal["pass", "fail", "unknown"]
Strength = Literal["hard", "soft"]
PriceBasis = Literal["exact", "from", "contact"]
Freshness = Literal["fresh", "stale", "unknown"]
PricingMetadataState = Literal["missing", "validated", "invalid", "untrusted"]


def uid(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class Condition(BaseModel):
    id: str
    field: str
    operator: str = "eq"
    value: Any = None
    strength: Strength = "hard"
    quote: str = ""


class Requirement(BaseModel):
    id: str
    conditions: list[Condition] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    raw_text: str = ""
    travelers: int = 1

    def hard(self) -> list[Condition]:
        return [c for c in self.conditions if c.strength == "hard"]

    def soft(self) -> list[Condition]:
        return [c for c in self.conditions if c.strength == "soft"]


class Evidence(BaseModel):
    url: str = ""
    method: str = "database_record"
    observed_at: str = ""
    record_ref: str = ""


class OfferSnapshot(BaseModel):
    id: str
    tour_id: str
    departure_date: str = ""
    price: int | None = None
    currency: str = "VND"
    price_basis: PriceBasis = "contact"
    price_trusted: bool = False
    price_freshness: Freshness = "unknown"
    departure_freshness: Freshness = "unknown"
    price_freshness_policy_seconds: int | None = None
    departure_freshness_policy_seconds: int | None = None
    pricing_metadata_state: PricingMetadataState = "missing"
    pricing_issue: str = ""
    pricing_complete: bool | None = None
    price_quotes: list[dict[str, Any]] = Field(default_factory=list)
    extra_charges: list[dict[str, Any]] = Field(default_factory=list)
    availability: str = "unknown"
    conditions: str = ""
    evidence: Evidence = Field(default_factory=Evidence)


class TourSnapshot(BaseModel):
    id: str
    supplier: str = ""
    name: str = ""
    url: str = ""
    destinations: list[str] = Field(default_factory=list)
    raw_destinations: list[str] = Field(default_factory=list)
    route: list[str] = Field(default_factory=list)
    destination_countries: list[str] = Field(default_factory=list)
    destination_country_complete: bool = False
    departure_city: str = ""
    duration_days: int | None = None
    transport: str = ""
    accommodation: str = ""
    itinerary: str = ""
    inclusions: str = ""
    exclusions: str = ""
    cancellation_policy: str = ""
    surcharges: str = ""
    child_policy: str = ""
    evidence: Evidence = Field(default_factory=Evidence)
    observed_at: str = ""
    verification: str = "provider_claimed"
    offers: list[OfferSnapshot] = Field(default_factory=list)


class Evaluation(BaseModel):
    offer_id: str
    condition_id: str
    state: State = "unknown"
    quote: str = ""
    reason_code: str = ""


class RankedCandidate(BaseModel):
    tour_id: str
    offer_id: str
    score: float = 0.0


class Analysis(BaseModel):
    hidden_costs: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    benefits: list[str] = Field(default_factory=list)


class Comparison(BaseModel):
    id: str
    requirement: Requirement
    ranked: list[RankedCandidate] = Field(default_factory=list)
    near_miss: list[RankedCandidate] = Field(default_factory=list)
    tour_snapshots: list[TourSnapshot] = Field(default_factory=list)
    evaluations: list[Evaluation] = Field(default_factory=list)
    analysis: Analysis = Field(default_factory=Analysis)
    candidates_considered: int = 0


class TourRow(BaseModel):
    """Raw catalog row as returned by `data`. `tour`/`offers` mirror DB columns."""

    provider: dict[str, Any] = Field(default_factory=dict)
    tour: dict[str, Any] = Field(default_factory=dict)
    offers: list[dict[str, Any]] = Field(default_factory=list)
