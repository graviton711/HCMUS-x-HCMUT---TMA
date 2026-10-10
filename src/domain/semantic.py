"""Versioned v2 semantics; legacy requirement models remain unchanged."""

from datetime import date
from typing import Annotated, Literal

from pydantic import BeforeValidator, Field, model_validator

from domain.common import Identifier, Model
from domain.requirements import (
    FIELDS,
    Budget,
    Condition,
    DateValue,
    NumberValue,
    Readiness,
    RequirementState,
    SetValue,
    UnresolvedValue,
)

SEMANTIC_POLICY = "requirements-v2.3-listed"
QUALITATIVE_FIELDS = {"supplier_reputation", "service_quality", "price_value", "nature"}
CORE_FIELDS = ("destinations", "departure_origin", "departure_date", "party.adults", "estimated_cost")
COMPLETENESS_POLICY = "personalized-core-v1"
ENTITY_FIELDS = {
    "destinations",
    "departure_origin",
    "supplier",
    "transport",
    "included_services",
    "tour_type",
    "route",
}
FIELDS_V2 = {
    **FIELDS,
    "tour_type": {"in", "not_in"},
    "route": {"contains_any", "contains_all", "excludes"},
    **{name: {"prefer", "requires", "excludes"} for name in sorted(QUALITATIVE_FIELDS)},
}


class EntityMember(Model):
    raw: str = Field(min_length=1, max_length=800)
    entity_type: Literal["place", "transport", "service", "supplier", "tour_type"]
    entity_id: str | None = Field(default=None, max_length=128)
    status: Literal["resolved", "catalog_missing"]

    @model_validator(mode="after")
    def binding(self):
        if (self.status == "resolved") != (self.entity_id is not None):
            raise ValueError("Resolved member requires an entity ID; missing member cannot have one")
        return self


class EntitySetValue(Model):
    kind: Literal["entities"] = "entities"
    members: list[EntityMember] = Field(min_length=1, max_length=30)
    catalog_version: str

    @model_validator(mode="after")
    def unique(self):
        keys = [(m.entity_type, m.entity_id or m.raw.casefold()) for m in self.members]
        if len(keys) != len(set(keys)) or len({m.entity_type for m in self.members}) != 1:
            raise ValueError("Entity members must be distinct and share their type")
        return self


class TemporalValue(Model):
    kind: Literal["temporal"] = "temporal"
    raw: str = Field(min_length=1, max_length=800)
    calendar: Literal["gregorian", "vietnamese_lunar", "unresolved"]
    group_id: Identifier
    role: Literal["start", "end", "single"]
    semantics: Literal["availability", "exact", "departure_window", "ambiguous", "single"]
    day: int | None = Field(default=None, ge=1, le=31)
    month: int | None = Field(default=None, ge=1, le=12)
    year: int | None = Field(default=None, ge=2000, le=2099)
    year_origin: Literal["explicit", "holiday_anchor"] | None = None
    holiday: Literal["tet"] | None = None
    holiday_year: int | None = Field(default=None, ge=2001, le=2099)
    leap: bool | None = None
    resolved_date: str | None = None
    reason: str | None = None
    converter_version: str | None = None

    @model_validator(mode="after")
    def coherent(self):
        if self.calendar == "vietnamese_lunar" and self.day is not None and self.day > 30:
            raise ValueError("Lunar day cannot exceed 30")
        if self.resolved_date is not None:
            date.fromisoformat(self.resolved_date)
            if self.reason or self.calendar == "unresolved" or self.semantics == "ambiguous":
                raise ValueError("Resolved temporal cannot retain ambiguity")
            if self.day is None or self.month is None:
                raise ValueError("Resolved temporal needs a parsed day and month")
            if self.year is None:
                raise ValueError("Resolved temporal needs a year")
        elif self.reason is None:
            raise ValueError("Unresolved temporal needs a reason")
        if self.holiday_year is not None and self.holiday != "tet":
            raise ValueError("Holiday year needs its Tet anchor")
        return self


class QualitativeValue(Model):
    kind: Literal["qualitative"] = "qualitative"
    concept: Literal["supplier_reputation", "service_quality", "price_value", "nature"]
    raw: str = Field(min_length=1, max_length=800)
    metric_policy: str | None = None

    @model_validator(mode="after")
    def supported_policy(self):
        if self.metric_policy is not None and (
            self.concept != "nature" or self.metric_policy != "nature-itinerary-tags-v1"
        ):
            raise ValueError("Qualitative metric has no reviewed implementation")
        return self


class BudgetV2(Budget):
    # Missing in persisted payloads retains the original conservative cost policy.
    measure: Literal["listed", "payable"] = "payable"

    @model_validator(mode="after")
    def measure_scope(self):
        if self.measure == "listed" and self.coverage != "tour_price":
            raise ValueError("Listed price applies only to tour_price coverage")
        return self


ValueV2 = Annotated[
    NumberValue
    | SetValue
    | DateValue
    | BudgetV2
    | UnresolvedValue
    | EntitySetValue
    | TemporalValue
    | QualitativeValue,
    Field(discriminator="kind"),
    BeforeValidator(lambda v: v.model_dump() if isinstance(v, Budget) and not isinstance(v, BudgetV2) else v),
]


class ResolutionTrace(Model):
    raw_values: list[str] = Field(default_factory=list, max_length=30)
    rule: str
    version: str


class ConditionV2(Condition):
    value: ValueV2
    scope: Literal["main_journey", "itinerary"] | None = None
    trace: ResolutionTrace | None = None

    @model_validator(mode="after")
    def compatible(self):
        if self.field not in FIELDS_V2 or self.operator not in FIELDS_V2[self.field]:
            raise ValueError("Unknown v2 field/operator")
        if isinstance(self.value, EntitySetValue):
            if self.field not in ENTITY_FIELDS:
                raise ValueError("Entity value requires an entity field")
            expected = {
                "transport": "transport",
                "included_services": "service",
                "supplier": "supplier",
                "tour_type": "tour_type",
            }.get(self.field, "place")
            if any(m.entity_type != expected for m in self.value.members):
                raise ValueError("Entity type does not match its field")
        elif isinstance(self.value, TemporalValue):
            if self.field not in {"departure_date", "return_date"}:
                raise ValueError("Temporal value requires a date field")
            if self.value.role == "end" and self.field != "return_date":
                raise ValueError("End boundary must constrain return_date")
            if self.value.semantics == "availability":
                wanted = "gte" if self.field == "departure_date" else "lte"
                if self.operator != wanted:
                    raise ValueError("Availability requires gte departure/lte return")
            if self.value.semantics == "exact" and self.operator != "eq":
                raise ValueError("Exact interval requires eq")
        elif isinstance(self.value, QualitativeValue):
            if self.field != self.value.concept:
                raise ValueError("Qualitative concept must match its field")
            if self.operator == "prefer" and self.strength != "soft":
                raise ValueError("Prefer requires soft strength")
            if self.operator == "requires" and self.strength != "hard":
                raise ValueError("Requires requires hard strength")
        elif self.field in FIELDS:
            legacy = self.model_dump(exclude={"scope", "trace"})
            if isinstance(self.value, BudgetV2):
                legacy["value"].pop("measure")
            Condition.model_validate(legacy)
        elif not isinstance(self.value, UnresolvedValue):
            raise ValueError("New fields require a semantic value")
        if self.scope == "main_journey" and self.field != "transport":
            raise ValueError("main_journey only applies to transport")
        if self.scope == "itinerary" and self.field not in {"route", "nature"}:
            raise ValueError("itinerary scope only applies to route/nature")
        return self


class SemanticIssue(Model):
    reason_code: str
    responsibility: Literal["user", "backend", "data"]
    condition_ids: list[Identifier]
    explanation: str
    blocking: bool = False


class SemanticReadiness(Readiness):
    scope_coverage: Literal["complete", "partial", "unavailable"] = "complete"
    unassessed_preferences: list[Identifier] = Field(default_factory=list)


class CoreFieldState(Model):
    field_path: Literal[
        "destinations", "departure_origin", "departure_date", "party.adults", "estimated_cost"
    ]
    status: Literal["missing", "needs_clarification", "resolved", "unsupported"]
    responsibility: Literal["user", "backend"] | None = None
    condition_ids: list[Identifier] = Field(default_factory=list)
    clarification_ids: list[Identifier] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class CompletenessReport(Model):
    policy_version: Literal["personalized-core-v1"] = COMPLETENESS_POLICY
    profile: Literal["personalized", "url_only"] = "personalized"
    fields: list[CoreFieldState] = Field(default_factory=list, max_length=5)
    is_complete: bool = False

    @model_validator(mode="after")
    def complete(self):
        paths = [f.field_path for f in self.fields]
        if len(paths) != len(set(paths)) or self.profile == "url_only" and paths:
            raise ValueError("Invalid completeness field bindings")
        object.__setattr__(
            self,
            "is_complete",
            self.profile == "url_only"
            or set(paths) == set(CORE_FIELDS)
            and all(f.status == "resolved" for f in self.fields),
        )
        return self


class SemanticRequirement(RequirementState):
    policy_version: str = SEMANTIC_POLICY
    conditions: list[ConditionV2] = Field(default_factory=list, max_length=50)
    issues: list[SemanticIssue] = Field(default_factory=list, max_length=100)
    readiness: SemanticReadiness = Field(default_factory=SemanticReadiness)

    @model_validator(mode="after")
    def temporal_groups(self):
        groups = {}
        for c in self.conditions:
            if isinstance(c.value, TemporalValue):
                groups.setdefault(c.value.group_id, []).append(c.value)
        for values in groups.values():
            if len(values) > 2 or len({v.role for v in values}) != len(values):
                raise ValueError("Temporal group has duplicate roles")
            if len(values) == 2:
                keys = {(v.calendar, v.semantics, v.holiday, v.holiday_year) for v in values}
                if len(keys) != 1 or {v.role for v in values} != {"start", "end"}:
                    raise ValueError("Temporal boundaries must share calendar/semantics/anchor")
        known = {c.id for c in self.conditions}
        if any(set(issue.condition_ids) - known for issue in self.issues):
            raise ValueError("Issue references a missing condition")
        return self
