"""Measured conditional analysis, never an automatic requirement change."""

from typing import Literal

from pydantic import Field, JsonValue, model_validator

from domain.common import Identifier, Model

POLICY = "what-if-v1"


class CreateWhatIf(Model):
    expected_revision: int = Field(ge=1)
    candidate_limit: int = Field(default=100, ge=3, le=500)
    max_scenarios: int = Field(default=32, ge=1, le=64)
    condition_ids: list[Identifier] = Field(default_factory=list, max_length=50)
    include_soft: bool = True
    include_pairs: bool = True
    max_budget_increase_ratio: float = Field(default=0.25, ge=0, le=1)
    max_date_shift_days: int = Field(default=7, ge=0, le=30)


class ApplyWhatIf(Model):
    expected_revision: int = Field(ge=1)


class ConditionGroup(Model):
    id: Identifier
    strength: Literal["hard", "soft"]
    condition_ids: list[Identifier] = Field(min_length=1)
    fields: list[str] = Field(min_length=1)
    label: str


class Population(Model):
    eligible: int = Field(ge=0)
    ineligible: int = Field(ge=0)
    unknown: int = Field(ge=0)
    eligible_candidate_ids: list[Identifier]
    has_hard_constraints: bool

    @model_validator(mode="after")
    def counts(self):
        if self.eligible != len(set(self.eligible_candidate_ids)):
            raise ValueError("Eligible count mismatch")
        return self


class RankingItem(Model):
    candidate_id: Identifier
    rank: int = Field(ge=1)
    score_lower: float | None = Field(ge=0, le=1)
    score_upper: float | None = Field(ge=0, le=1)
    coverage: float | None = Field(ge=0, le=1)
    tied: bool

    @model_validator(mode="after")
    def interval(self):
        if (self.score_lower is None) != (self.score_upper is None) or (
            self.score_lower is not None and self.score_lower > self.score_upper
        ):
            raise ValueError("Invalid ranking interval")
        return self


class RestrictionRatio(Model):
    state: Literal["computed", "blocked", "not_applicable"]
    numerator: int = Field(ge=0)
    denominator: int = Field(ge=0)
    percent: float | None = Field(default=None, ge=0, le=100)
    reason_code: str | None = None
    meaning: str = (
        "Tỷ lệ lựa chọn đạt kịch bản nhưng đã bị yêu cầu gốc loại có bằng chứng, trong snapshot đã đọc."
    )

    @model_validator(mode="after")
    def arithmetic(self):
        if self.numerator > self.denominator:
            raise ValueError("Invalid percentage cohort")
        if self.state == "computed":
            if (
                not self.denominator
                or self.percent is None
                or abs(self.percent - 100 * self.numerator / self.denominator) > 0.000001
            ):
                raise ValueError("Percentage must match operands")
        elif self.percent is not None:
            raise ValueError("Blocked percentage must be null")
        return self


class Witness(Model):
    candidate_id: Identifier
    title: str | None
    canonical_url: str
    tour_snapshot_id: Identifier
    offer_snapshot_id: Identifier | None
    original_status: Literal["pass", "fail", "unknown"]
    original_evaluations: list[dict[str, JsonValue]]
    scenario_evaluations: list[dict[str, JsonValue]]
    evidence_ids: list[Identifier]


class RankChange(Model):
    candidate_id: Identifier
    before: RankingItem
    after: RankingItem
    rank_delta: int
    evidence_ids: list[Identifier]


class WhatIfScenario(Model):
    id: Identifier
    kind: Literal["remove_hard_group", "remove_soft_group", "relax_bound", "remove_hard_pair"]
    group_ids: list[Identifier] = Field(min_length=1, max_length=2)
    condition_ids: list[Identifier]
    label: str
    state: Literal["measured", "insufficient_data"]
    population: Population
    additional_candidate_ids: list[Identifier]
    proven_blocked_candidate_ids: list[Identifier]
    previously_unknown_candidate_ids: list[Identifier]
    joint_only_candidate_ids: list[Identifier] = Field(default_factory=list)
    restriction_ratio: RestrictionRatio
    top_before: list[RankingItem]
    top_after: list[RankingItem]
    top_changed: bool
    rank_changes: list[RankChange]
    rank_changes_truncated: bool
    witnesses: list[Witness]
    witnesses_truncated: bool
    edits: list[dict[str, JsonValue]]
    tradeoffs: list[dict[str, JsonValue]]
    limitations: list[str]
    minimal_within_tested_subsets: bool = False
    insight: str


class WhatIfAnalysis(Model):
    id: Identifier
    comparison_id: Identifier
    requirement_id: Identifier
    revision: int = Field(ge=1)
    policy_version: str = POLICY
    origin: Literal["source", "synthetic"]
    evaluated_at: str
    scope: dict[str, JsonValue]
    baseline: Population
    baseline_top: list[RankingItem]
    groups: list[ConditionGroup]
    scenarios: list[WhatIfScenario]
    candidates: list[dict[str, JsonValue]]
    semantic_assessment: dict[str, JsonValue]
    explanation: dict[str, JsonValue]
    limits: dict[str, JsonValue]
    limitations: list[str]

    @model_validator(mode="after")
    def bindings(self):
        ids = {g.id for g in self.groups}
        groups = {g.id: set(g.condition_ids) for g in self.groups}
        candidates = {c["candidate_id"] for c in self.candidates}
        if len(ids) != len(self.groups) or len({s.id for s in self.scenarios}) != len(self.scenarios):
            raise ValueError("Duplicate analysis identity")
        if len(candidates) != len(
            self.candidates
        ) or self.baseline.eligible + self.baseline.ineligible + self.baseline.unknown != len(candidates):
            raise ValueError("Baseline universe mismatch")
        for scenario in self.scenarios:
            if set(scenario.group_ids) - ids or set(scenario.population.eligible_candidate_ids) - candidates:
                raise ValueError("Scenario binding mismatch")
            if (
                scenario.population.eligible + scenario.population.ineligible + scenario.population.unknown
                != len(candidates)
            ):
                raise ValueError("Scenario universe mismatch")
            added = set(scenario.population.eligible_candidate_ids) - set(
                self.baseline.eligible_candidate_ids
            )
            if (
                added != set(scenario.additional_candidate_ids)
                or set(scenario.proven_blocked_candidate_ids) | set(scenario.previously_unknown_candidate_ids)
                != added
            ):
                raise ValueError("Scenario delta mismatch")
            if set(scenario.condition_ids) != set().union(*(groups[gid] for gid in scenario.group_ids)):
                raise ValueError("Scenario condition/group mismatch")
            if set(scenario.proven_blocked_candidate_ids) & set(scenario.previously_unknown_candidate_ids):
                raise ValueError("Proven and unknown cohorts overlap")
            if set(scenario.joint_only_candidate_ids) - added:
                raise ValueError("Joint cohort must belong to additions")
            if (
                scenario.restriction_ratio.numerator != len(scenario.proven_blocked_candidate_ids)
                or scenario.restriction_ratio.denominator != scenario.population.eligible
            ):
                raise ValueError("Restriction ratio cohort mismatch")
            if scenario.previously_unknown_candidate_ids and scenario.restriction_ratio.state == "computed":
                raise ValueError("Unknown original cohort cannot establish restriction percentage")
            if any(w.candidate_id not in added for w in scenario.witnesses):
                raise ValueError("Witness must belong to additional cohort")
            for ranking in [*scenario.top_before, *scenario.top_after]:
                if ranking.candidate_id not in candidates:
                    raise ValueError("Unbound ranking item")
            for change in scenario.rank_changes:
                if (
                    change.candidate_id != change.before.candidate_id
                    or change.candidate_id != change.after.candidate_id
                    or change.rank_delta != change.before.rank - change.after.rank
                ):
                    raise ValueError("Invalid rank change")
        return self
