"""Single source of truth for backend types. No other model packages exist."""

from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

State = Literal["pass", "partial", "fail", "unknown"]
Strength = Literal["hard", "soft"]
PriceBasis = Literal["exact", "from", "contact", "unknown"]
Freshness = Literal["fresh", "stale", "unknown"]
MetricState = Literal["observed", "partial", "unknown"]
RankingField = Literal["price", "departure_date", "duration_days", "tour_name", "soft_fit"]
SortDirection = Literal["asc", "desc"]


def uid(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class Condition(BaseModel):
    id: str
    field: str
    operator: str = "eq"
    value: Any = None
    strength: Strength = "hard"
    quote: str = ""
    weight_percent: int | None = Field(default=None, ge=0, le=100)


class RankingKey(BaseModel):
    field: RankingField
    direction: SortDirection


class RankingSpec(BaseModel):
    order_by: list[RankingKey] = Field(min_length=1, max_length=5)


class RequirementAlternative(BaseModel):
    id: str
    label: str
    conditions: list[Condition] = Field(min_length=1)


class RequirementAssumption(BaseModel):
    id: str
    kind: Literal["date_window"] = "date_window"
    label: str
    quote: str
    date_from: str
    date_to: str
    condition_ids: list[str] = Field(min_length=1)
    timezone: Literal["Asia/Ho_Chi_Minh"] = "Asia/Ho_Chi_Minh"
    edited: bool = False


class Requirement(BaseModel):
    id: str
    conditions: list[Condition] = Field(default_factory=list)
    alternatives: list[RequirementAlternative] = Field(default_factory=list)
    assumptions: list[RequirementAssumption] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    raw_text: str = ""
    travelers: int = 1
    traveler_mix: dict[Literal["adult", "child", "small_child", "infant"], int] = Field(
        default_factory=dict
    )
    ranking: RankingSpec | None = None

    def hard(self) -> list[Condition]:
        return [
            condition
            for group in self.hard_groups()
            for condition in group[1]
        ]

    def shared_hard(self) -> list[Condition]:
        return [c for c in self.conditions if c.strength == "hard"]

    def hard_groups(self) -> list[tuple[str, list[Condition]]]:
        groups = [("common", self.shared_hard())]
        groups.extend(
            (alternative.id, [c for c in alternative.conditions if c.strength == "hard"])
            for alternative in self.alternatives
        )
        return [(group_id, conditions) for group_id, conditions in groups if conditions]

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
    currency: str = ""
    price_basis: PriceBasis = "unknown"
    price_by_age: dict[str, int | None] = Field(default_factory=dict)
    single_supplement: int | None = None
    supplements: str = ""
    departure_freshness: Freshness = "unknown"
    departure_freshness_policy_seconds: int | None = None
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
    route_observed: bool = False
    departure_city: str = ""
    duration_days: int | None = None
    duration_nights: int | None = None
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
    detail_state: Literal["index", "complete"] = "complete"
    offers: list[OfferSnapshot] = Field(default_factory=list)


class Evaluation(BaseModel):
    offer_id: str
    condition_id: str
    alternative_id: str | None = None
    state: State = "unknown"
    quote: str = ""
    reason_code: str = ""
    reason: str = ""


class RankedCandidate(BaseModel):
    tour_id: str
    offer_id: str
    score: float = 0.0


class DecisionView(BaseModel):
    kind: Literal[
        "cheapest", "best_fit", "experience_rich", "fewest_legs",
        "cancellation_flexible", "included_value", "balanced",
    ]
    candidates: list[RankedCandidate] = Field(default_factory=list, max_length=5)
    currencies: list[str] = Field(default_factory=list)
    note: str = ""


class MetricEvidence(BaseModel):
    source_field: str
    quote: str
    observed_at: str = ""
    url: str = ""


class MetricMeasure(BaseModel):
    value: Any = None
    lower_bound: float | None = None
    upper_bound: float | None = None
    unit: str = ""
    state: MetricState = "unknown"
    evidence: list[MetricEvidence] = Field(default_factory=list)
    method_version: str = ""


class CostExposure(BaseModel):
    name: str
    obligation: Literal["mandatory", "optional", "conditional", "unknown"] = "unknown"
    amount: int | None = None
    currency: str = ""
    unit: Literal[
        "per_person", "per_adult", "per_child", "per_night", "per_room",
        "per_booking", "per_day", "per_vehicle", "other", "unknown",
    ] = "unknown"
    applies_when: str = ""
    source_field: str = ""
    quote: str = ""
    calculated_total: int | None = None


class CostProfile(BaseModel):
    listed_price: int | None = None
    price_basis: PriceBasis = "unknown"
    currency: str = ""
    group_total_calculated: int | None = None
    group_total_scope: str = ""
    priced_extras: list[CostExposure] = Field(default_factory=list)
    unpriced_exclusions: list[CostExposure] = Field(default_factory=list)
    optional_or_conditional: list[CostExposure] = Field(default_factory=list)
    state: MetricState = "unknown"


class CostScenarioAssumptions(BaseModel):
    travelers: int = Field(ge=1, le=100)
    traveler_mix: dict[Literal["adult", "child", "small_child", "infant"], int] = Field(
        default_factory=dict
    )
    rooms: int | None = Field(default=None, ge=1, le=100)
    single_rooms: int | None = Field(default=None, ge=0, le=100)
    nights: int | None = Field(default=None, ge=0, le=100)


class CostScenarioItem(BaseModel):
    tour_id: str
    tour_name: str
    offer_id: str
    currency: str
    price_basis: PriceBasis
    listed_price: int | None = None
    group_base_calculated: int | None = None
    priced_mandatory_extras: list[CostExposure] = Field(default_factory=list)
    known_total: int | None = None
    unresolved_exposures: list[CostExposure] = Field(default_factory=list)
    delta_from_original: int | None = None
    state: MetricState = "unknown"
    evidence: list[MetricEvidence] = Field(default_factory=list)


class CostScenarioResult(BaseModel):
    source_comparison_id: str
    assumptions: CostScenarioAssumptions
    scanned_offers: int
    items: list[CostScenarioItem] = Field(default_factory=list)


class ActivityFact(BaseModel):
    name: str
    day: int | None = None
    evidence: MetricEvidence


class RouteLegFact(BaseModel):
    origin: str
    destination: str
    mode: str = ""
    evidence: MetricEvidence


class CoverageFact(BaseModel):
    category: Literal[
        "transport", "accommodation", "meals", "admission_or_activity",
        "guide", "insurance", "other",
    ]
    status: Literal["included", "partial", "excluded", "unknown"]
    evidence: MetricEvidence


class CancellationRule(BaseModel):
    days_before_departure: int | None = None
    refund_percent: int | None = None
    fee_amount: int | None = None
    currency: str = ""
    evidence: MetricEvidence


class FamilyFact(BaseModel):
    kind: Literal["age_range", "age_price", "discount", "room", "bed", "eligibility", "other"]
    min_age: int | None = None
    max_age: int | None = None
    amount: int | None = None
    percent: int | None = None
    condition: str = ""
    evidence: MetricEvidence


class ExtractedTourFacts(BaseModel):
    tour_id: str
    activities: list[ActivityFact] = Field(default_factory=list)
    route_legs: list[RouteLegFact] = Field(default_factory=list)
    inclusions: list[CoverageFact] = Field(default_factory=list)
    exclusions: list[CostExposure] = Field(default_factory=list)
    surcharges: list[CostExposure] = Field(default_factory=list)
    cancellation_rules: list[CancellationRule] = Field(default_factory=list)
    family_facts: list[FamilyFact] = Field(default_factory=list)
    reviewed_fields: list[str] = Field(default_factory=list)
    method_version: str = ""


class PreferenceScore(BaseModel):
    condition_id: str
    lower_score: float = Field(ge=0, le=1)
    upper_score: float = Field(ge=0, le=1)
    state: MetricState = "unknown"
    evidence: list[MetricEvidence] = Field(default_factory=list)


class MetricProfile(BaseModel):
    tour_id: str
    offer_id: str
    cost: CostProfile = Field(default_factory=CostProfile)
    preference_fit: list[PreferenceScore] = Field(default_factory=list)
    metrics: dict[str, MetricMeasure] = Field(default_factory=dict)
    inclusions: list[MetricMeasure] = Field(default_factory=list)
    exclusions: list[CostExposure] = Field(default_factory=list)
    cancellation_rules: list[CancellationRule] = Field(default_factory=list)
    family_facts: list[FamilyFact] = Field(default_factory=list)


class OptionMetricComparison(BaseModel):
    key: str
    value: float | int | None = None
    reference_median: float | int | None = None
    unit: str = ""
    currency: str = ""
    scope: str = ""
    state: MetricState = "unknown"
    relation: Literal["favorable", "tradeoff", "similar", "unknown"] = "unknown"
    higher_is_better: bool | None = None
    evidence: list[MetricEvidence] = Field(default_factory=list)


class DecisionOption(BaseModel):
    tour_id: str
    offer_id: str
    objective: str
    title: str = ""
    reason: str = ""
    tradeoffs: list[str] = Field(default_factory=list)
    metric_comparisons: list[OptionMetricComparison] = Field(default_factory=list)


class RelaxationExample(BaseModel):
    tour_id: str
    offer_id: str
    tour_name: str = ""
    price: int | None = None
    currency: str = ""
    departure_date: str = ""


class RelaxationOption(BaseModel):
    condition_id: str
    gained_offers: int = 0
    gained_tours: int = 0
    examples: list[RelaxationExample] = Field(default_factory=list)


class DecisionConditionCount(BaseModel):
    condition_id: str
    pass_offers: int = 0
    fail_offers: int = 0
    unknown_offers: int = 0
    pass_tours: int = 0
    fail_tours: int = 0
    unknown_tours: int = 0


class DecisionFunnelStep(BaseModel):
    condition_id: str = ""
    label: str = ""
    group_id: str = ""
    stage: int
    offers_before: int
    offers_after: int
    tours_before: int
    tours_after: int


class DecisionBlockerCount(BaseModel):
    condition_id: str
    state: Literal["fail", "unknown"]
    offers: int = 0
    tours: int = 0


class DecisionAlternativeCount(BaseModel):
    alternative_id: str
    label: str
    eligible_offers: int = 0
    eligible_tours: int = 0


class DecisionTrace(BaseModel):
    scanned_tours: int = 0
    scanned_offers: int = 0
    eligible_tours: int = 0
    eligible_offers: int = 0
    excluded_offers: int = 0
    condition_counts: list[DecisionConditionCount] = Field(default_factory=list)
    sequential_funnel: list[DecisionFunnelStep] = Field(default_factory=list)
    first_blockers: list[DecisionBlockerCount] = Field(default_factory=list)
    alternative_counts: list[DecisionAlternativeCount] = Field(default_factory=list)
    snapshot_available: bool = False


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
    decision_trace: DecisionTrace | None = None
    scenario_source_comparison_id: str | None = None
    ranking_currencies: list[str] = Field(default_factory=list)
    decision_views: list[DecisionView] = Field(default_factory=list)
    metric_profiles: list[MetricProfile] = Field(default_factory=list)
    near_miss_profiles: list[MetricProfile] = Field(default_factory=list)
    decision_options: list[DecisionOption] = Field(default_factory=list)
    relaxation_options: list[RelaxationOption] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class TourRow(BaseModel):
    """Raw catalog row as returned by `data`. `tour`/`offers` mirror DB columns."""

    provider: dict[str, Any] = Field(default_factory=dict)
    tour: dict[str, Any] = Field(default_factory=dict)
    offers: list[dict[str, Any]] = Field(default_factory=list)
