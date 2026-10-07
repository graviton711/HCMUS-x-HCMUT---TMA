from typing import Annotated, Literal

from pydantic import Field, JsonValue, model_validator

from api.dto import Form, FormCondition
from domain.common import Identifier, Model, now
from domain.crawl import OfferSnapshot
from domain.requirements import Party, Readiness, RequirementState, Target, Tree, Value

VERSION = "2.0-draft"


class PreferenceLevel(Model):
    level: int = Field(ge=0, le=5)
    origin: Literal["user", "system_default"] = "user"


class Preferences(Model):
    cost: PreferenceLevel = Field(default_factory=lambda: PreferenceLevel(level=3, origin="system_default"))
    comfort: PreferenceLevel = Field(
        default_factory=lambda: PreferenceLevel(level=3, origin="system_default")
    )
    pace: PreferenceLevel = Field(default_factory=lambda: PreferenceLevel(level=3, origin="system_default"))
    culture: PreferenceLevel = Field(
        default_factory=lambda: PreferenceLevel(level=3, origin="system_default")
    )


class StructuredForm(Form):
    preference_levels: Preferences = Field(default_factory=Preferences)
    notes: str = Field(default="", max_length=8000)


class StructuredInput(Model):
    kind: Literal["structured"]
    form: StructuredForm


class TextInput(Model):
    kind: Literal["text"]
    text: str = Field(min_length=1, max_length=2000)


class UrlInput(Model):
    kind: Literal["urls"]


def canonical_urls(urls):
    from urllib.parse import urlsplit, urlunsplit

    result = []
    for url in urls:
        Target(target_id="validation", url=url)
        u = urlsplit(url)
        normalized = urlunsplit((u.scheme.lower(), u.netloc.lower(), u.path or "/", u.query, ""))
        if normalized not in result:
            result.append(normalized)
    return result


class CreateRequirementV2(Model):
    input: Annotated[StructuredInput | TextInput | UrlInput, Field(discriminator="kind")]
    reference_urls: list[str] = Field(default_factory=list, max_length=5)
    timezone: str = "Asia/Ho_Chi_Minh"

    @model_validator(mode="after")
    def inputs(self):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Unknown timezone") from exc
        if self.input.kind == "structured":
            fields = {c.field for c in self.input.form.conditions}
            if (
                not {"destinations", "departure_origin", "departure_date", "estimated_cost"} <= fields
                or self.input.form.party.adults is None
            ):
                raise ValueError("Personalized structured form needs destination/origin/date/adults/budget")
        if self.input.kind == "urls" and not self.reference_urls:
            raise ValueError("URL input needs at least one URL")
        canonical_urls(self.reference_urls)
        return self


class ReadinessV2(Readiness):
    blockers: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def mirror_reasons(self):
        object.__setattr__(self, "blockers", list(self.reasons))
        return self


class RequirementV2(RequirementState):
    schema_version: Literal["2.0-draft"] = VERSION
    revision: int = Field(ge=0)
    input_kind: Literal["structured", "text", "urls"]
    preference_levels: Preferences | None = None
    reference_urls: list[str] = Field(default_factory=list, max_length=5)
    notes: str = Field(default="", max_length=8000)
    provenance: dict[str, JsonValue] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: now().isoformat())
    readiness: ReadinessV2 = Field(default_factory=ReadinessV2)

    @model_validator(mode="after")
    def public_bindings(self):
        if self.reference_urls != [t.url for t in self.targets]:
            raise ValueError("reference_urls/targets mismatch")
        if self.revision == 0 and (self.conditions or self.messages):
            raise ValueError("Unconfirmed resource must not contain inferred conditions")
        return self


class TypedEdit(Model):
    op: Literal[
        "upsert_condition",
        "replace_condition_value",
        "remove_condition",
        "replace_party",
        "set_preference_level",
        "replace_reference_urls",
        "set_notes",
        "replace_tree",
    ]
    condition_id: Identifier | None = None
    condition: FormCondition | None = None
    value: Value | None = None
    party: Party | None = None
    dimension: Literal["cost", "comfort", "pace", "culture"] | None = None
    level: int | None = Field(default=None, ge=0, le=5)
    reference_urls: list[str] | None = Field(default=None, max_length=5)
    notes: str | None = Field(default=None, max_length=8000)
    tree: Tree | None = None
    tree_kind: Literal["hard_tree", "preference_tree"] | None = None

    @model_validator(mode="after")
    def fields_for_operation(self):
        required = {
            "upsert_condition": {"condition"},
            "replace_condition_value": {"condition_id", "value"},
            "remove_condition": {"condition_id"},
            "replace_party": {"party"},
            "set_preference_level": {"dimension", "level"},
            "replace_reference_urls": {"reference_urls"},
            "set_notes": {"notes"},
            "replace_tree": {"tree", "tree_kind"},
        }[self.op]
        actual = {k for k, v in self.model_dump().items() if k != "op" and v is not None}
        if actual != required:
            raise ValueError(f"{self.op} requires only {sorted(required)}")
        return self


class EditInput(Model):
    kind: Literal["structured"]
    edits: list[TypedEdit] = Field(min_length=1, max_length=30)


class MessageInput(Model):
    kind: Literal["message"]
    text: str = Field(min_length=1, max_length=2000)


class CreateProposal(Model):
    expected_revision: int = Field(ge=0)
    proposal_id: Identifier | None = None
    expected_proposal_version: int | None = Field(default=None, ge=1)
    input: Annotated[EditInput | MessageInput, Field(discriminator="kind")]

    @model_validator(mode="after")
    def binding(self):
        if (self.proposal_id is None) != (self.expected_proposal_version is None):
            raise ValueError("proposal_id and expected_proposal_version must be supplied together")
        return self


class ProposalVersion(Model):
    expected_proposal_version: int = Field(ge=1)


class ConfirmProposal(ProposalVersion):
    expected_revision: int = Field(ge=0)


class DiscardChanges(ConfirmProposal):
    change_ids: list[Identifier] = Field(min_length=1, max_length=50)


class Change(Model):
    id: Identifier
    path: str
    condition_id: Identifier | None = None
    before: JsonValue = None
    after: JsonValue = None
    origin: Literal["user_edit", "chat_inference"]
    reason: str


class Proposal(Model):
    id: Identifier
    version: int = Field(ge=1)
    requirement_id: Identifier
    base_revision: int = Field(ge=0)
    status: Literal["pending", "needs_clarification", "confirmed", "cancelled", "superseded", "expired"]
    expires_at: str
    preview: RequirementV2
    changes: list[Change]
    clarifications: list[JsonValue] = Field(default_factory=list)
    requested_action: Literal["search", "next_group"] | None = None
    parse_job_id: Identifier | None = None


class OfferSelectionV2(Model):
    tour_id: Identifier
    offer_snapshot_id: Identifier


class CreateComparisonV2(Model):
    requirement_id: Identifier
    revision: int = Field(ge=1)
    round_intent: Literal["initial", "next_group", "offer_change"] = "initial"
    previous_comparison_id: Identifier | None = None
    excluded_tour_ids: list[Identifier] = Field(default_factory=list, max_length=500)
    offer_selections: list[OfferSelectionV2] = Field(default_factory=list, max_length=100)
    candidate_limit: int = Field(default=20, ge=3, le=100)

    @model_validator(mode="after")
    def round_binding(self):
        if (self.round_intent != "initial" or self.offer_selections) and not self.previous_comparison_id:
            raise ValueError("next_group/offer_change/selections require previous comparison")
        if len({x.tour_id for x in self.offer_selections}) != len(self.offer_selections):
            raise ValueError("Duplicate tour offer selection")
        return self


class ConversationContext(Model):
    requirement_revision: int = Field(ge=0)
    proposal_id: Identifier | None = None
    proposal_version: int | None = Field(default=None, ge=1)
    comparison_id: Identifier | None = None
    result_revision: int | None = Field(default=None, ge=1)
    offer_snapshot_ids: list[Identifier] = Field(default_factory=list, max_length=100)
    evidence_ids: list[Identifier] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def refs(self):
        if (self.proposal_id is None) != (self.proposal_version is None):
            raise ValueError("Proposal context requires version")
        if (self.comparison_id is None) != (self.result_revision is None):
            raise ValueError("Comparison context requires result revision")
        return self


class ConversationMessage(Model):
    text: str = Field(min_length=1, max_length=2000)
    client_message_id: Identifier
    context: ConversationContext


class Interpretation(Model):
    intent: Literal["answer", "edit", "search", "next_group", "clarify"]
    requested_action: Literal["search", "next_group"] | None = None
    metric_ids: list[Identifier] = Field(default_factory=list, max_length=30)
    evaluation_ids: list[Identifier] = Field(default_factory=list, max_length=30)


class PublicSupplier(Model):
    id: Identifier
    display_name: str


class Column(Model):
    id: Identifier
    candidate_id: Identifier | None
    tour_id: Identifier | None
    tour_snapshot_id: Identifier | None
    offer_snapshot_id: Identifier | None
    selected_offer_snapshot_id: Identifier | None
    title: str | None
    title_reason: str | None = None
    supplier: PublicSupplier | None
    canonical_url: str
    origin: Literal["reference", "discovery", "both"]
    target_ids: list[Identifier]
    source_ids: list[Identifier]
    offer_reason: str | None
    offer_options: list[OfferSnapshot]

    @model_validator(mode="after")
    def offers(self):
        if self.offer_snapshot_id != self.selected_offer_snapshot_id:
            raise ValueError("Selected offer mismatch")
        if any(o.tour_snapshot_id != self.tour_snapshot_id for o in self.offer_options):
            raise ValueError("Offer option belongs to another tour snapshot")
        if self.offer_snapshot_id and self.offer_snapshot_id not in {
            o.snapshot_id for o in self.offer_options
        }:
            raise ValueError("Selected offer must be an option")
        return self


class Row(Model):
    id: str
    field: str
    label: str
    scope: Literal["tour", "offer", "cost", "evaluation"]
    value_type: Literal["date", "number", "set", "text", "boolean", "price_list"]
    unit: str | None
    order: int = Field(ge=0)
    condition_ids: list[Identifier]


class Freshness(Model):
    state: Literal["fresh", "stale", "unknown"]
    checked_at: str
    expires_at: str | None
    policy_version: str


class Cell(Model):
    row_id: str
    column_id: Identifier
    value: JsonValue
    raw_value: list[str | None]
    data_state: Literal["present", "missing", "conflicting", "invalid", "unsupported"]
    verification: Literal["supplier_published", "independently_verified", "unverified"]
    completeness: Literal["complete", "partial", "unknown"]
    observed_at: str | None
    freshness: Freshness
    evidence_ids: list[Identifier]
    reason_code: str | None
    evaluation_ids: list[Identifier]


class Evaluation(Model):
    id: Identifier
    condition_id: Identifier
    candidate_id: Identifier
    field: str
    strength: Literal["hard", "soft", "unresolved"]
    expected: JsonValue
    actual: JsonValue
    status: Literal["pass", "fail", "unknown", "not_evaluated"]
    reason_code: str
    evidence_ids: list[Identifier]
    data_quality: dict[str, JsonValue]


class ComparisonV2(Model):
    id: Identifier
    requirement_id: Identifier
    revision: int = Field(ge=1)
    requirement_snapshot: RequirementV2
    origin: Literal["source", "synthetic"]
    evaluated_at: str
    policy_versions: dict[str, str]
    columns: list[Column]
    rows: list[Row]
    cells: list[Cell]
    evaluations: list[Evaluation]
    recommendations: dict[str, JsonValue]
    analysis: dict[str, JsonValue]
    source_coverage: list[dict[str, JsonValue]]
    warnings: list[dict[str, JsonValue]]
    empty_reason: str | None

    @model_validator(mode="after")
    def bindings(self):
        if (self.requirement_id, self.revision) != (
            self.requirement_snapshot.id,
            self.requirement_snapshot.revision,
        ):
            raise ValueError("Comparison revision binding mismatch")
        cols, rows = {c.id for c in self.columns}, {r.id for r in self.rows}
        if len(cols) != len(self.columns) or len(rows) != len(self.rows):
            raise ValueError("Duplicate matrix identities")
        pairs = {(c.row_id, c.column_id) for c in self.cells}
        if len(pairs) != len(self.cells) or pairs != {(r, c) for r in rows for c in cols}:
            raise ValueError("Every row/column needs exactly one cell")
        evals = {e.id for e in self.evaluations}
        if any(set(c.evaluation_ids) - evals for c in self.cells):
            raise ValueError("Dangling evaluation")
        recommended = self.recommendations["candidate_ids"]
        if len(set(recommended)) != len(recommended) or len(recommended) > 3 or set(recommended) - cols:
            raise ValueError("Invalid recommendation bindings")
        return self


class JobEvent(Model):
    seq: int
    job_id: Identifier
    stage: str
    status: Literal["started", "completed", "partial", "failed", "cancelled", "skipped"]
    occurred_at: str
    source_id: Identifier | None = None
    summary: str
    counts: dict[str, int] | None = None
    error_code: str | None = None


class Envelope[T](Model):
    schema_version: Literal["2.0-draft"] = VERSION
    request_id: Identifier
    data: T
