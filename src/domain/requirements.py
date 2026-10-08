from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, JsonValue, model_validator

from domain.common import Identifier, Model, instant

FIELDS = {
    "destinations": {"contains", "contains_any", "contains_all", "excludes"},
    "departure_origin": {"in", "not_in"},
    "supplier": {"in", "not_in"},
    "transport": {"in", "not_in"},
    "included_services": {"contains_all", "excludes"},
    "departure_date": {"eq", "lt", "lte", "gt", "gte", "between"},
    "return_date": {"eq", "lt", "lte", "gt", "gte", "between"},
    "duration_days": {"eq", "lt", "lte", "gt", "gte", "between", "near", "prefer_low", "prefer_high"},
    "duration_nights": {"eq", "lt", "lte", "gt", "gte", "between", "near"},
    "hotel_stars_min": {"eq", "gte", "near", "prefer_high"},
    "shopping_stops": {"eq", "lte", "prefer_low"},
    "flight_stops": {"eq", "lte", "prefer_low"},
    "estimated_cost": {"lt", "lte", "gt", "gte", "between", "near", "prefer_low"},
    "unsupported": {"unresolved"},
}
SET_FIELDS = {"destinations", "departure_origin", "supplier", "transport", "included_services"}
DATE_FIELDS = {"departure_date", "return_date"}
SOFT_OPERATORS = {"near", "prefer_low", "prefer_high"}


class SourceReference(Model):
    kind: Literal["text", "form", "system_default"]
    message_id: Identifier | None = None
    quote: str | None = Field(default=None, max_length=8000)
    start: int | None = Field(default=None, ge=0)
    end: int | None = Field(default=None, ge=1)
    field_path: str | None = None
    submitted_value: JsonValue = None
    rule: str | None = None

    @model_validator(mode="after")
    def valid_source(self):
        if self.kind == "text":
            if not self.message_id or not self.quote or self.start is None or self.end is None:
                raise ValueError("Text provenance needs message, quote and span")
            if self.end - self.start != len(self.quote):
                raise ValueError("Quote span uses Unicode code points")
        elif self.kind == "system_default" and not self.rule:
            raise ValueError("Default requires policy rule")
        elif self.kind == "form" and not self.field_path:
            raise ValueError("Form provenance requires field_path")
        return self


class NumberValue(Model):
    kind: Literal["number"] = "number"
    amount: int = Field(ge=0, le=10**15)
    upper: int | None = Field(default=None, ge=0, le=10**15)

    @model_validator(mode="after")
    def ordered(self):
        if self.upper is not None and self.upper < self.amount:
            raise ValueError("Reversed range")
        return self


class SetValue(Model):
    kind: Literal["set"] = "set"
    items: list[str] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def unique(self):
        if len(set(self.items)) != len(self.items) or any(not x or len(x) > 128 for x in self.items):
            raise ValueError("Set items must be unique nonempty identifiers")
        return self


class DateValue(Model):
    kind: Literal["date"] = "date"
    value: str
    upper: str | None = None

    @model_validator(mode="after")
    def ordered(self):
        lower = date.fromisoformat(self.value)
        if self.upper is not None and date.fromisoformat(self.upper) < lower:
            raise ValueError("Reversed date range")
        return self


class Budget(Model):
    kind: Literal["budget"] = "budget"
    amount: int | str
    upper: int | str | None = None
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    basis: Literal["per_adult", "per_person", "group_total"] | None = None
    coverage: Literal["tour_price", "trip_total"] = "tour_price"
    coverage_origin: Literal["explicit", "system_default"] = "system_default"

    @model_validator(mode="after")
    def amounts(self):
        for value in (self.amount, self.upper):
            if value is None:
                continue
            try:
                number = Decimal(value)
            except InvalidOperation as exc:
                raise ValueError("Invalid money") from exc
            if not number.is_finite() or number < 0 or number > 10**15:
                raise ValueError("Invalid money range")
            if self.currency == "VND" and type(value) is not int:
                raise ValueError("VND must use integer dong")
            if self.currency not in (None, "VND") and not isinstance(value, str):
                raise ValueError("Foreign currency uses decimal string")
        if self.upper is not None and Decimal(self.upper) < Decimal(self.amount):
            raise ValueError("Reversed budget range")
        return self


class UnresolvedValue(Model):
    kind: Literal["unresolved"] = "unresolved"
    raw: str = Field(max_length=8000)
    reason: str


Value = Annotated[NumberValue | SetValue | DateValue | Budget | UnresolvedValue, Field(discriminator="kind")]


class Condition(Model):
    id: Identifier
    field: str
    operator: str
    value: Value
    strength: Literal["hard", "soft", "unresolved"]
    sources: list[SourceReference] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def compatible(self):
        if self.field not in FIELDS or self.operator not in FIELDS[self.field]:
            raise ValueError("Unknown field/operator")
        if self.field == "unsupported" and not isinstance(self.value, UnresolvedValue):
            raise ValueError("Unsupported conditions must keep unresolved values")
        if isinstance(self.value, UnresolvedValue):
            return self
        expected = (
            Budget
            if self.field == "estimated_cost"
            else (
                SetValue
                if self.field in SET_FIELDS
                else DateValue
                if self.field in DATE_FIELDS
                else NumberValue
            )
        )
        if not isinstance(self.value, expected):
            raise ValueError("Field/value type mismatch")
        if self.operator in SOFT_OPERATORS and self.strength != "soft":
            raise ValueError("Preference operator cannot be hard")
        if self.operator == "between" and getattr(self.value, "upper", None) is None:
            raise ValueError("Between requires upper bound")
        if self.operator != "between" and getattr(self.value, "upper", None) is not None:
            raise ValueError("A value range requires the between operator")
        if isinstance(self.value, NumberValue):
            if self.field in {"duration_days", "duration_nights"} and self.value.amount < 1:
                raise ValueError("Duration must be positive")
            if self.field == "hotel_stars_min" and not 1 <= self.value.amount <= 5:
                raise ValueError("Hotel stars outside 1..5")
        return self


class Tree(Model):
    kind: Literal["all", "any", "predicate"]
    condition_id: Identifier | None = None
    children: list["Tree"] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def shape(self):
        if self.kind == "predicate":
            if not self.condition_id or self.children:
                raise ValueError("Invalid predicate")
        elif self.condition_id is not None or (self.kind == "any" and not self.children):
            raise ValueError("Invalid group")
        return self


class Child(Model):
    id: Identifier
    age: int | None = Field(default=None, ge=0, le=17)


class Party(Model):
    adults: int | None = Field(default=None, ge=1, le=100)
    children: list[Child] = Field(default_factory=list, max_length=20)
    rooming: str | None = Field(default=None, max_length=300)
    sources: list[SourceReference] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def unique_children(self):
        if len({c.id for c in self.children}) != len(self.children):
            raise ValueError("Duplicate child ID")
        return self


class Target(Model):
    target_id: Identifier
    url: str = Field(max_length=2048)

    @model_validator(mode="after")
    def valid_url(self):
        try:
            u = urlsplit(self.url)
            port = u.port
        except ValueError as exc:
            raise ValueError("Invalid URL") from exc
        if u.scheme not in {"http", "https"} or not u.hostname or u.username or u.password:
            raise ValueError("Public http(s) URL required without credentials")
        if port not in (None, 80, 443) or any(ord(c) < 33 for c in self.url) or "\\" in self.url:
            raise ValueError("Invalid URL port or characters")
        return self


class Clarification(Model):
    id: Identifier
    field_path: str
    reason_code: str
    question: str
    options: list[str] = Field(default_factory=list)
    blocking: bool = True


class Readiness(Model):
    status: Literal["ready", "needs_clarification", "unsupported"] = "ready"
    can_collect_data: bool = False
    can_evaluate_hard_constraints: bool = False
    reasons: list[str] = Field(default_factory=list)


class Message(Model):
    id: Identifier
    text: str = Field(min_length=1, max_length=8000)
    received_at: str

    @model_validator(mode="after")
    def timestamp(self):
        instant(self.received_at)
        return self


class RequirementState(Model):
    schema_version: Literal["1.0"] = "1.0"
    policy_version: Literal["requirements-v1"] = "requirements-v1"
    id: Identifier
    revision: int = Field(ge=1)
    mode: Literal["discover", "compare_urls", "hybrid"]
    timezone: str = "Asia/Ho_Chi_Minh"
    messages: list[Message] = Field(default_factory=list, max_length=100)
    targets: list[Target] = Field(default_factory=list, max_length=5)
    party: Party = Field(default_factory=Party)
    conditions: list[Condition] = Field(default_factory=list, max_length=50)
    hard_tree: Tree = Field(default_factory=lambda: Tree(kind="all"))
    preference_tree: Tree = Field(default_factory=lambda: Tree(kind="all"))
    clarifications: list[Clarification] = Field(default_factory=list)
    readiness: Readiness = Field(default_factory=Readiness)

    @model_validator(mode="after")
    def references(self):
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Unknown timezone") from exc
        if self.mode == "discover" and self.targets:
            raise ValueError("Discover cannot have URL targets")
        if self.mode in {"compare_urls", "hybrid"} and not 1 <= len(self.targets) <= 5:
            raise ValueError("Reference collection needs 1..5 URL targets")
        if len({t.url for t in self.targets}) != len(self.targets) or len(
            {t.target_id for t in self.targets}
        ) != len(self.targets):
            raise ValueError("Duplicate targets")
        by_id = {c.id: c for c in self.conditions}
        if len(by_id) != len(self.conditions):
            raise ValueError("Duplicate condition ID")
        for tree, soft in ((self.hard_tree, False), (self.preference_tree, True)):
            stack, seen, count = [(tree, 0)], set(), 0
            while stack:
                node, depth = stack.pop()
                count += 1
                if depth > 8 or count > 150:
                    raise ValueError("Condition tree too large")
                if node.kind == "predicate":
                    if node.condition_id in seen or node.condition_id not in by_id:
                        raise ValueError("Duplicate or dangling condition reference")
                    seen.add(node.condition_id)
                    if (by_id[node.condition_id].strength == "soft") != soft:
                        raise ValueError("Condition strength/tree mismatch")
                else:
                    stack.extend((x, depth + 1) for x in node.children)
            expected = {c.id for c in self.conditions if (c.strength == "soft") == soft}
            if seen != expected:
                raise ValueError("Every condition must occur in its tree")
        messages = {m.id: m.text for m in self.messages}
        for source in [s for c in self.conditions for s in c.sources] + self.party.sources:
            if source.kind == "text":
                text = messages.get(source.message_id, "")
                if text[source.start : source.end] != source.quote:
                    raise ValueError("Ungrounded source quote")
        return self


class Requirement(RequirementState):
    mode: Literal["discover", "compare_urls"]

    @model_validator(mode="after")
    def v1_input_policy(self):
        if self.mode == "compare_urls" and len(self.targets) < 2:
            raise ValueError("Compare needs 2..5 URL targets")
        return self


class QuerySpec(Model):
    requirement_id: Identifier
    revision: int
    mode: Literal["discover", "compare_urls"]
    conditions: list[Condition]
    hard_tree: Tree
    preference_tree: Tree
    party: Party

    @classmethod
    def from_requirement(cls, r: Requirement):
        # Exclude raw messages and text provenance from upstream payloads.
        conditions = [
            c.model_copy(
                update={
                    "sources": [
                        SourceReference(kind="form", field_path=f"conditions.{c.id}", rule="validated_query")
                    ],
                    **(
                        {"value": c.value.model_copy(update={"raw": ""})}
                        if isinstance(c.value, UnresolvedValue)
                        else {}
                    ),
                }
            )
            for c in r.conditions
        ]
        return cls(
            requirement_id=r.id,
            revision=r.revision,
            mode=r.mode,
            conditions=conditions,
            hard_tree=r.hard_tree,
            preference_tree=r.preference_tree,
            party=r.party.model_copy(update={"sources": []}),
        )
