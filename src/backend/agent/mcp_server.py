"""Local MCP tool server for grounded travel-agent workflows."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from functools import wraps
from threading import RLock
from typing import Annotated, Any, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.agent.results import limit_comparison
from backend.data.catalog import for_settings
from backend.data.sessions import BaseStore, SessionStore
from backend.decide.engine import compare, eval_hard, soft_review_candidates
from backend.decide.metrics import fact_cache_id
from backend.error_logging import log_app_error, log_unexpected_error
from backend.errors import AppError
from backend.input.lunar import resolve_lunar
from backend.models import (
    ActivityFact,
    CancellationRule,
    Comparison,
    CostExposure,
    CoverageFact,
    ExtractedTourFacts,
    FamilyFact,
    MetricEvidence,
    Requirement,
    RouteLegFact,
    State,
    TourSnapshot,
    uid,
)
from backend.settings import Settings
from backend.workflows import TourWorkflows
from shared.text import fold_vi

_VERDICT_STATES: dict[str, State] = {
    "fit": "pass", "partial": "partial", "unknown": "unknown", "not_fit": "fail"
}


class QueryConditionInput(BaseModel):
    """Structured MCP input; semantic constraints are rechecked by the workflow."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Unique condition ID, e.g. c1.")
    field: Literal[
        "destination", "departure_city", "date_from", "date_to", "budget_max",
        "duration_days", "transport", "accommodation", "preference",
    ] = Field(description="Condition field: destination, departure_city, date_from, date_to, "
              "budget_max, duration_days, transport, accommodation, or preference (soft only).")
    operator: Literal["contains", "any", "eq", "lte"] = Field(
        description="Operator for the selected field: contains (single text match: destination, "
        "departure_city, accommodation, preference), any (list of destination choices), "
        "eq (exact value: dates, duration_days, transport), lte (budget_max only)."
    )

    @field_validator("operator", mode="before")
    @classmethod
    def _normalize_operator_alias(cls, value: object) -> object:
        # Unambiguous English synonyms agents emit; anything else still fails
        # the Literal check below instead of being guessed.
        if isinstance(value, str) and value.strip().lower() == "equals":
            return "eq"
        return value
    value: str | int | list[str] = Field(
        description="Condition value: text, positive integer, or destination choices. "
        "Transport must be one of flight, bus, train, cruise, mixed."
    )
    strength: Literal["hard", "soft"] = Field(description="Whether this is a hard or soft condition.")
    quote: str = Field(description="Exact substring from the conversation "
                        "that supports this condition.")
    weight_percent: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="User-reviewed weight for a soft preference; all soft weights must total 100.",
    )


class QueryAlternativeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Stable unique branch ID, e.g. option_1.")
    label: str = Field(description="Short user-facing description of this option.")
    conditions: list[QueryConditionInput] = Field(
        min_length=1,
        description="Hard conditions that must all pass for this option.",
    )


class RequirementAssumptionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Stable unique assumption ID.")
    kind: Literal["date_window"] = "date_window"
    label: str = Field(description="Human-readable explanation of the date interpretation.")
    quote: str = Field(description="Exact user wording that required this assumption.")
    date_from: str = Field(description="First ISO date included in the interpreted range.")
    date_to: str = Field(description="Last ISO date included in the interpreted range.")
    condition_ids: list[str] = Field(
        min_length=1,
        description="Date condition IDs that implement this assumption.",
    )
    timezone: Literal["Asia/Ho_Chi_Minh"] = "Asia/Ho_Chi_Minh"
    edited: bool = False


class RankingKeyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: Literal["price", "departure_date", "duration_days", "tour_name", "soft_fit"] = Field(
        description="A ranking field supported by the catalog decision engine."
    )
    direction: Literal["asc", "desc"] = Field(description="Sort direction for this field.")


class QueryRankingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_by: list[RankingKeyInput] = Field(
        min_length=1,
        max_length=5,
        description="Ordered ranking keys; earlier fields always take priority.",
    )


class TravelerMixInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    adult: int | None = Field(default=None, ge=0, description="Number of adults.")
    child: int | None = Field(default=None, ge=0, description="Number of children.")
    small_child: int | None = Field(default=None, ge=0, description="Number of small children.")
    infant: int | None = Field(default=None, ge=0, description="Number of infants.")


class SoftVerdictInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    offer_id: str = Field(description="Offer ID from the active soft_review batch.")
    condition_id: str = Field(description="Soft condition ID from the active soft_review batch.")
    verdict: Literal["fit", "partial", "unknown", "not_fit"] = Field(
        description="Full fit=1, partial fit=0.5, contradicted=0, unknown=not established."
    )
    quote: str = Field(default="", description="Exact short quote from the candidate evidence.")
    reason: str = Field(default="", description="At most two concise sentences grounded in the quote.")


class ActivityInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Short activity name copied from the itinerary quote.")
    day: int | None = Field(default=None, ge=1)
    quote: str = Field(description="Exact substring from the itinerary source field.")


class RouteLegInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin: str
    destination: str
    mode: str = ""
    quote: str = Field(description="Exact source quote explicitly stating this route leg.")


class CoverageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Literal[
        "transport", "accommodation", "meals", "admission_or_activity",
        "guide", "insurance", "other",
    ]
    status: Literal["included", "partial", "excluded", "unknown"]
    quote: str


class CostExposureInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    obligation: Literal["mandatory", "optional", "conditional", "unknown"] = "unknown"
    amount: int | None = Field(default=None, ge=0)
    currency: str = ""
    unit: Literal[
        "per_person", "per_adult", "per_child", "per_night", "per_room",
        "per_booking", "per_day", "per_vehicle", "other", "unknown",
    ] = "unknown"
    applies_when: str = ""
    quote: str


class CancellationRuleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    days_before_departure: int | None = Field(default=None, ge=0)
    refund_percent: int | None = Field(default=None, ge=0, le=100)
    fee_amount: int | None = Field(default=None, ge=0)
    currency: str = ""
    quote: str


class FamilyFactInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["age_range", "age_price", "discount", "room", "bed", "eligibility", "other"]
    min_age: int | None = Field(default=None, ge=0)
    max_age: int | None = Field(default=None, ge=0)
    amount: int | None = Field(default=None, ge=0)
    percent: int | None = Field(default=None, ge=0, le=100)
    condition: str = ""
    quote: str


class TourMetricFactsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tour_id: str
    reviewed_fields: list[
        Literal[
            "itinerary", "route", "inclusions", "exclusions",
            "surcharges", "cancellation_policy", "child_policy",
        ]
    ] = Field(default_factory=list)
    activities: list[ActivityInput] = Field(default_factory=list)
    route_legs: list[RouteLegInput] = Field(default_factory=list)
    inclusions: list[CoverageInput] = Field(default_factory=list)
    exclusions: list[CostExposureInput] = Field(default_factory=list)
    surcharges: list[CostExposureInput] = Field(default_factory=list)
    cancellation_rules: list[CancellationRuleInput] = Field(default_factory=list)
    family_facts: list[FamilyFactInput] = Field(default_factory=list)


@dataclass
class _RankingContext:
    id: str
    requirement: Requirement
    comparison: Comparison
    candidates: list[tuple[TourSnapshot, str]]
    batches: list[list[tuple[TourSnapshot, str]]]
    decision_run_id: str | None = None
    batch_index: int = 0
    verdicts: dict[tuple[str, str], tuple[State, str, str]] = field(default_factory=dict)
    metric_facts: dict[str, ExtractedTourFacts] = field(default_factory=dict)


def _json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _effective_raw_text(
    store: BaseStore | None,
    settings: Settings,
    conversation_id: str,
    raw_text: str,
) -> str:
    """Resolve the server-side conversation transcript for a chat token.

    The backend stores every user message under the conversation id it puts in the
    chat header; the agent only copies that token. Falls back to the call's raw_text
    when the token is missing or unknown, so older single-turn callers keep working.
    """
    token = (conversation_id or "").strip()
    if token:
        active = store or SessionStore(settings.database_url)
        should_close = store is None
        try:
            history = active.get_conversation_text(token)
        except Exception:
            history = None
        finally:
            if should_close:
                active.close()
        if history:
            return history
    return raw_text


class AgentTools:
    def __init__(
        self,
        settings: Settings,
        catalog: Any,
        workflows: TourWorkflows,
        result_store: BaseStore | None = None,
    ):
        self.settings = settings
        self.catalog = catalog
        self.workflows = workflows
        self.result_store = result_store
        self._destination_names: dict[str, str] | None = None
        self._ranking_contexts: dict[str, _RankingContext] = {}
        self._ranking_context_lock = RLock()

    def ask_choice(
        self,
        question: Annotated[str, Field(description="Single question for the user.")],
        options: Annotated[
            list[dict[str, str]],
            Field(description="Two to eight choices as {label, value} objects."),
        ],
        allow_custom: Annotated[bool, Field(description="Whether the user may answer freely.")] = True,
    ) -> str:
        clean = []
        seen: set[str] = set()
        for option in options[:8]:
            label = option.get("label", "").strip()
            value = option.get("value", "").strip()
            canonical_value = self._canonical_destination(value)
            if _fold_catalog_text(label) == _fold_catalog_text(value):
                label = canonical_value
            else:
                label = self._canonical_destination(label)
            value = canonical_value
            key = _fold_catalog_text(value)
            if label and value and key not in seen:
                clean.append({"label": label[:100], "value": value[:200]})
                seen.add(key)
        if not question.strip() or len(clean) < 2:
            return _json({"error": "Provide a question and at least two distinct choices."})
        return _json({"question": question[:240], "options": clean, "allow_custom": allow_custom})

    def _canonical_destination(self, value: str) -> str:
        if self._destination_names is None:
            names = self.catalog.list_destinations()
            folded: dict[str, set[str]] = {}
            for name in names:
                if isinstance(name, str) and name.strip():
                    folded.setdefault(_fold_catalog_text(name), set()).add(name.strip())
            self._destination_names = {
                key: next(iter(matches)) for key, matches in folded.items() if len(matches) == 1
            }
        return self._destination_names.get(_fold_catalog_text(value), value)

    def catalog_facets(
        self,
        fields: Annotated[
            list[Literal["destinations", "departure_cities", "prices_vnd", "departure_dates"]] | None,
            Field(description="Facet groups to return; omit for the full legacy response."),
        ] = None,
    ) -> str:
        """Return only requested facet groups; omitted fields preserve the legacy full response.

        Valid fields: destinations, departure_cities, prices_vnd, departure_dates.
        Transport, accommodation, and duration are per-tour fields — check them in query
        results, not facets.
        """
        tours = self.workflows.snapshots(self.settings.supabase_scan_limit)
        requested = set(fields) if fields is not None else {
            "destinations", "departure_cities", "prices_vnd", "departure_dates"
        }
        result: dict[str, Any] = {
            "scanned_tours": len(tours),
            "scan_limit": self.settings.supabase_scan_limit,
        }
        if "destinations" in requested:
            result["destinations"] = sorted({value for tour in tours for value in tour.destinations})
        if "departure_cities" in requested:
            result["departure_cities"] = sorted({
                tour.departure_city for tour in tours if tour.departure_city
            })
        if "prices_vnd" in requested:
            result["prices_vnd"] = sorted({
                offer.price for tour in tours for offer in tour.offers
                if offer.price is not None and offer.currency == "VND"
            })
        if "departure_dates" in requested:
            result["departure_dates"] = sorted({
                offer.departure_date for tour in tours for offer in tour.offers
                if _is_iso_date(offer.departure_date)
            })
        return _json(result)

    def discover_destinations(
        self,
        raw_text: Annotated[str, Field(description="Verbatim user message for this turn.")],
        conditions: Annotated[
            list[QueryConditionInput],
            Field(description="Shared hard conditions, each with id, field, operator, value, "
                  "strength hard, and an exact quote from the conversation."),
        ],
        alternatives: Annotated[
            list[QueryAlternativeInput] | None,
            Field(description="OR branches with id, label, and hard conditions; at most 20."),
        ] = None,
        travelers: Annotated[int, Field(description="Total party size, at least 1.")] = 1,
        traveler_mix: Annotated[
            TravelerMixInput | None,
            Field(description="Age-group counts (adult, child, small_child, infant) summing to travelers."),
        ] = None,
        conversation_id: Annotated[
            str,
            Field(description="Conversation token from the chat header; checks quotes against "
                  "the stored user-side history."),
        ] = "",
    ) -> str:
        """Preview catalog options under common conditions and OR branches.

        This read-only feasibility scan is used before the user reviews a brief.
        It never ranks soft preferences or creates a comparison. Pass conversation_id
        from the chat header to check quotes against the stored user-side history.
        """
        raw_text = _effective_raw_text(self.result_store, self.settings, conversation_id, raw_text)
        structured_conditions = [
            item.model_dump(mode="json")
            if isinstance(item, QueryConditionInput)
            else QueryConditionInput.model_validate(item).model_dump(mode="json")
            for item in conditions
        ]
        if not structured_conditions and not alternatives:
            raise AppError(
                "DISCOVERY_CONSTRAINTS_REQUIRED",
                "Provide at least one known hard condition or alternative for the feasibility scan.",
                422,
            )
        if any(item["strength"] != "hard" for item in structured_conditions):
            raise AppError(
                "DISCOVERY_HARD_CONDITIONS_ONLY",
                "Feasibility preview accepts hard conditions only.",
                422,
            )
        structured_alternatives = [
            {
                "id": branch.id,
                "label": branch.label,
                "conditions": [condition.model_dump(mode="json") for condition in branch.conditions],
            }
            for branch in (alternatives or [])
        ]
        if any(
            condition["strength"] != "hard"
            for branch in structured_alternatives
            for condition in branch["conditions"]
        ):
            raise AppError(
                "DISCOVERY_HARD_CONDITIONS_ONLY",
                "Feasibility preview accepts hard conditions only.",
                422,
            )

        requirement = self.workflows.requirement(
            raw_text,
            structured_conditions,
            travelers=travelers,
            traveler_mix=(traveler_mix.model_dump(exclude_none=True) if traveler_mix else None),
            alternatives=structured_alternatives,
        )
        tours = self.workflows.snapshots(self.settings.supabase_scan_limit)
        catalog_destinations = sorted({dest for tour in tours for dest in tour.destinations})
        catalog_departures = sorted({tour.departure_city for tour in tours if tour.departure_city})

        unresolved = _unresolved_location_labels(
            requirement.hard(), catalog_destinations, catalog_departures
        )
        if unresolved:
            return _json({
                "status": "resolve_catalog_labels",
                "unresolved": unresolved,
                "available_destinations": catalog_destinations,
                "available_departure_cities": catalog_departures,
                "scanned_tours": len(tours),
                "scan_limit": self.settings.supabase_scan_limit,
            })

        destinations: dict[str, dict[str, Any]] = {}
        passing_tour_ids: set[str] = set()
        alternative_tour_ids: dict[str, set[str]] = {
            branch.id: set() for branch in requirement.alternatives
        }
        condition_counts: dict[str, dict[str, int]] = {
            condition.id: {"pass": 0, "fail": 0, "unknown": 0}
            for condition in requirement.hard()
        }
        near_matches: list[tuple[int, int, int, str, dict[str, Any]]] = []

        for tour in tours:
            tour_passed = False
            tour_best_by_destination: dict[str, dict[str, Any]] = {}
            for offer in tour.offers:
                evaluations_by_id: dict[str, tuple[Any, str, str]] = {}
                for _group_id, group_conditions in requirement.hard_groups():
                    for condition in group_conditions:
                        state, reason = eval_hard(condition, tour, offer)
                        evaluations_by_id[condition.id] = (condition, state, reason)
                        condition_counts[condition.id][state] += 1
                common_conditions = requirement.shared_hard()
                common_pass = all(
                    evaluations_by_id[condition.id][1] == "pass"
                    for condition in common_conditions
                )
                branch_passes = {
                    branch.id: all(
                        evaluations_by_id[condition.id][1] == "pass"
                        for condition in branch.conditions
                    )
                    for branch in requirement.alternatives
                }
                passed = common_pass and (
                    not requirement.alternatives or any(branch_passes.values())
                )
                for branch_id, branch_passed in branch_passes.items():
                    if common_pass and branch_passed:
                        alternative_tour_ids[branch_id].add(tour.id)
                example = {
                    "tour_id": tour.id,
                    "tour_name": tour.name,
                    "destinations": tour.destinations,
                    "departure_city": tour.departure_city,
                    "departure_date": offer.departure_date,
                    "duration_days": tour.duration_days,
                    "price": offer.price,
                    "currency": offer.currency,
                    "price_basis": offer.price_basis,
                    "availability": offer.availability,
                    "url": tour.url,
                }
                if passed:
                    tour_passed = True
                    passing_branches = (
                        [branch for branch in requirement.alternatives if branch_passes[branch.id]]
                        if requirement.alternatives
                        else [None]
                    )
                    for branch in passing_branches:
                        scope_conditions = [
                            *common_conditions,
                            *(branch.conditions if branch is not None else []),
                        ]
                        requested_destinations = [
                            str(value)
                            for condition in scope_conditions
                            if condition.field == "destination"
                            for value in (condition.value if isinstance(condition.value, list) else [condition.value])
                        ]
                        matched_destinations = (
                            [
                                item for item in tour.destinations
                                if any(_fold_catalog_label(item) == _fold_catalog_label(value)
                                       for value in requested_destinations)
                            ]
                            if requested_destinations
                            else tour.destinations
                        )
                        for destination in matched_destinations:
                            current = tour_best_by_destination.get(destination)
                            if current is None or _preflight_offer_key(example) < _preflight_offer_key(current):
                                tour_best_by_destination[destination] = example
                else:
                    relevant_conditions = list(common_conditions)
                    if requirement.alternatives:
                        best_branch = min(
                            requirement.alternatives,
                            key=lambda branch: (
                                sum(evaluations_by_id[item.id][1] == "fail" for item in branch.conditions),
                                sum(evaluations_by_id[item.id][1] == "unknown" for item in branch.conditions),
                                -sum(evaluations_by_id[item.id][1] == "pass" for item in branch.conditions),
                                branch.id,
                            ),
                        )
                        relevant_conditions.extend(best_branch.conditions)
                    failures = [
                        (condition, *evaluations_by_id[condition.id][1:])
                        for condition in relevant_conditions
                        if evaluations_by_id[condition.id][1] != "pass"
                    ]
                    relevant_passes = sum(
                        evaluations_by_id[condition.id][1] == "pass"
                        for condition in relevant_conditions
                    )
                    relevant_fails = sum(state == "fail" for _condition, state, _reason in failures)
                    relevant_unknowns = sum(state == "unknown" for _condition, state, _reason in failures)
                    near_matches.append((relevant_passes, -relevant_fails, -relevant_unknowns, tour.id, {
                        **example,
                        "conditions": [
                            {
                                "field": condition.field,
                                "state": state,
                                "reason_code": reason,
                            }
                            for condition, state, reason in failures
                        ],
                    }))
            if not tour_passed:
                continue
            passing_tour_ids.add(tour.id)
            for destination, example in tour_best_by_destination.items():
                group = destinations.setdefault(destination, {"tour_ids": set(), "examples": []})
                group["tour_ids"].add(tour.id)
                if all(example["tour_id"] != tour.id for example in group["examples"]):
                    group["examples"].append(example)

        feasible_destinations = []
        for destination, group in destinations.items():
            all_examples = sorted(group["examples"], key=_preflight_offer_key)
            priced_by_currency: dict[str, int] = {}
            for example in all_examples:
                if example["price"] is None or not str(example["currency"]).strip():
                    continue
                currency = str(example["currency"]).upper()
                if currency:
                    priced_by_currency[currency] = min(
                        priced_by_currency.get(currency, example["price"]),
                        example["price"],
                    )
            feasible_destinations.append({
                "destination": destination,
                "tour_count": len(group["tour_ids"]),
                "lowest_listed_prices": [
                    {"amount": amount, "currency": currency}
                    for currency, amount in sorted(priced_by_currency.items())
                ],
                "examples": all_examples[:3],
            })
        feasible_destinations.sort(key=lambda item: (
            -item["tour_count"],
            item["destination"].casefold(),
        ))
        near_matches.sort(key=lambda row: (-row[0], -row[1], -row[2], row[3]))
        diagnostics = [
            {
                "id": condition.id,
                "field": condition.field,
                **condition_counts[condition.id],
            }
            for condition in requirement.hard()
        ]
        alternative_diagnostics = [
            {
                "id": branch.id,
                "label": branch.label,
                "matching_tour_count": len(alternative_tour_ids[branch.id]),
            }
            for branch in requirement.alternatives
        ]
        return _json({
            "status": "matching_options_found" if feasible_destinations else "no_verified_options",
            "scanned_tours": len(tours),
            "scan_limit": self.settings.supabase_scan_limit,
            "matching_tour_count": len(passing_tour_ids),
            "alternative_diagnostics": alternative_diagnostics,
            "party_size_checked": False,
            "matching_destinations": feasible_destinations[:12],
            "condition_diagnostics": diagnostics,
            "near_matches": [row[4] for row in near_matches[:5]],
        })

    def query_tours(
        self,
        raw_text: Annotated[str, Field(description="Verbatim user message for this turn.")],
        conditions: Annotated[
            list[QueryConditionInput],
            Field(description="Shared conditions: hard filters plus soft preferences with "
                  "weight_percent summing to 100 when present."),
        ],
        decision_run_id: Annotated[
            str, Field(description="Opaque run id from the reviewed-decision instruction (dec_ + 32 hex).")
        ],
        alternatives: Annotated[
            list[QueryAlternativeInput] | None,
            Field(description="Reviewed OR branches, unchanged from the signed-off brief."),
        ] = None,
        assumptions: Annotated[
            list[RequirementAssumptionInput] | None,
            Field(description="Reviewed date_window assumptions linking date condition pairs."),
        ] = None,
        travelers: Annotated[int, Field(description="Total party size, at least 1.")] = 1,
        ranking: Annotated[
            QueryRankingInput | None,
            Field(description="Ordered ranking keys; earlier keys take priority."),
        ] = None,
        requirement_id: Annotated[
            str, Field(description="Reviewed requirement id to reuse; empty starts a new one.")
        ] = "",
        traveler_mix: Annotated[
            TravelerMixInput | None,
            Field(description="Age-group counts (adult, child, small_child, infant) summing to travelers."),
        ] = None,
        snapshot_comparison_id: Annotated[
            str, Field(description="Baseline comparison id for a what-if run; empty scans live.")
        ] = "",
        conversation_id: Annotated[
            str,
            Field(description="Conversation token from the chat header; checks quotes against "
                  "the stored user-side history."),
        ] = "",
    ) -> str:
        """Filter the active catalog, or the signed-off scan snapshot for a what-if run."""
        raw_text = _effective_raw_text(self.result_store, self.settings, conversation_id, raw_text)
        if not re.fullmatch(r"dec_[0-9a-f]{32}", decision_run_id):
            raise AppError("DECISION_RUN_INVALID", "Invalid decision run ID.", 422)
        structured_conditions = [
            item.model_dump(mode="json")
            if isinstance(item, QueryConditionInput)
            else QueryConditionInput.model_validate(item).model_dump(mode="json")
            for item in conditions
        ]
        structured_alternatives = [
            {
                "id": branch.id,
                "label": branch.label,
                "conditions": [condition.model_dump(mode="json") for condition in branch.conditions],
            }
            for branch in (alternatives or [])
        ]
        structured_assumptions = [
            item.model_dump(mode="json") if isinstance(item, RequirementAssumptionInput)
            else RequirementAssumptionInput.model_validate(item).model_dump(mode="json")
            for item in (assumptions or [])
        ]
        ranking_value = (
            ranking.model_dump(mode="json")
            if isinstance(ranking, QueryRankingInput)
            else QueryRankingInput.model_validate(ranking).model_dump(mode="json")
            if ranking is not None
            else None
        )
        requirement = self.workflows.requirement(
            raw_text,
            structured_conditions,
            travelers,
            ranking_value,
            requirement_id=requirement_id or None,
            require_weights=True,
            traveler_mix=(traveler_mix.model_dump(exclude_none=True) if traveler_mix else None),
            alternatives=structured_alternatives,
            assumptions=structured_assumptions,
        )
        if snapshot_comparison_id:
            store = self.result_store or SessionStore(self.settings.database_url)
            should_close = self.result_store is None
            try:
                baseline = store.get_scenario_snapshot_handoff(decision_run_id)
            finally:
                if should_close:
                    store.close()
            if baseline.id != snapshot_comparison_id:
                raise AppError("SCENARIO_SNAPSHOT_MISMATCH", "Scenario scan snapshot mismatch.", 409)
            comparison = self.workflows.comparison_on_snapshot(
                requirement,
                baseline.tour_snapshots,
            ).model_copy(update={"scenario_source_comparison_id": baseline.id})
        else:
            comparison = self.workflows.comparison(requirement, self.settings.supabase_scan_limit)
        return self._comparison_payload(
            requirement, comparison, decision_run_id=decision_run_id or None
        )

    def draft_requirement(
        self,
        raw_text: Annotated[str, Field(description="Verbatim user message for this turn.")],
        conditions: Annotated[
            list[QueryConditionInput],
            Field(description="Shared conditions: hard filters plus soft preferences (preference + "
                  "contains); every quote exact from the conversation."),
        ],
        alternatives: Annotated[
            list[QueryAlternativeInput] | None,
            Field(description="OR branches with id, label, and hard conditions; at most 20."),
        ] = None,
        assumptions: Annotated[
            list[RequirementAssumptionInput] | None,
            Field(description="Date_window assumptions linking date_from/date_to pairs."),
        ] = None,
        travelers: Annotated[int, Field(description="Total party size, at least 1.")] = 1,
        ranking: Annotated[
            QueryRankingInput | None,
            Field(description="Ordered ranking keys; earlier keys take priority."),
        ] = None,
        traveler_mix: Annotated[
            TravelerMixInput | None,
            Field(description="Age-group counts (adult, child, small_child, infant) summing to travelers."),
        ] = None,
        conversation_id: Annotated[
            str,
            Field(description="Conversation token from the chat header; checks quotes against "
                  "the stored user-side history."),
        ] = "",
    ) -> str:
        """Validate a reviewable brief without reading the tour catalog.

        Pass conversation_id from the chat header to check quotes against the stored
        user-side history.
        """
        raw_text = _effective_raw_text(self.result_store, self.settings, conversation_id, raw_text)
        structured_conditions = [
            item.model_dump(mode="json")
            if isinstance(item, QueryConditionInput)
            else QueryConditionInput.model_validate(item).model_dump(mode="json")
            for item in conditions
        ]
        structured_alternatives = [
            {
                "id": branch.id,
                "label": branch.label,
                "conditions": [condition.model_dump(mode="json") for condition in branch.conditions],
            }
            for branch in (alternatives or [])
        ]
        structured_assumptions = [
            item.model_dump(mode="json") if isinstance(item, RequirementAssumptionInput)
            else RequirementAssumptionInput.model_validate(item).model_dump(mode="json")
            for item in (assumptions or [])
        ]
        ranking_value = (
            ranking.model_dump(mode="json")
            if isinstance(ranking, QueryRankingInput)
            else QueryRankingInput.model_validate(ranking).model_dump(mode="json")
            if ranking is not None
            else None
        )
        requirement = self.workflows.requirement(
            raw_text,
            structured_conditions,
            travelers,
            ranking_value,
            traveler_mix=(traveler_mix.model_dump(exclude_none=True) if traveler_mix else None),
            alternatives=structured_alternatives,
            assumptions=structured_assumptions,
        )
        soft = requirement.soft()
        if soft:
            base, remainder = divmod(100, len(soft))
            weights = {
                item.id: base + (1 if index < remainder else 0)
                for index, item in enumerate(soft)
            }
            requirement = requirement.model_copy(update={
                "conditions": [
                    item.model_copy(update={"weight_percent": weights[item.id]})
                    if item.strength == "soft" else item
                    for item in requirement.conditions
                ],
            })
        return _json({"requirement_draft": requirement.model_dump(mode="json")})

    def tour_detail(
        self,
        tour_id: Annotated[str, Field(description="Tour id from a discover or query result.")],
    ) -> str:
        tour = self.workflows.tour_detail(tour_id)
        if tour is None:
            return _json({"error": "Tour not found in the active catalog."})
        return _json(tour.model_dump(mode="json"))

    def score_soft(
        self,
        context_id: Annotated[str, Field(description="Ranking context id from the soft_review batch.")],
        verdicts: Annotated[
            list[SoftVerdictInput],
            Field(description="Exactly one verdict per candidate/preference pair in the active batch."),
        ],
        metric_facts: Annotated[
            list[TourMetricFactsInput],
            Field(description="One metric-facts object per tour in the active batch."),
        ],
    ) -> str:
        with self._ranking_context_lock:
            context = self._ranking_contexts.get(context_id)
            if context is None:
                raise AppError(
                    "RANKING_CONTEXT_NOT_FOUND",
                    "The ranking context is no longer available. Run the catalog query again.",
                    409,
                )
            batch = context.batches[context.batch_index]
            expected = {
                (offer_id, condition.id)
                for _, offer_id in batch
                for condition in context.requirement.soft()
            }
            parsed = [
                item if isinstance(item, SoftVerdictInput) else SoftVerdictInput.model_validate(item)
                for item in verdicts
            ]
            supplied = [(item.offer_id, item.condition_id) for item in parsed]
            if len(supplied) != len(set(supplied)) or set(supplied) != expected:
                raise AppError(
                    "SOFT_BATCH_INCOMPLETE",
                    "Submit exactly one verdict for every candidate and soft condition in the active batch.",
                    422,
                )

            parsed_facts = [
                item if isinstance(item, TourMetricFactsInput)
                else TourMetricFactsInput.model_validate(item)
                for item in metric_facts
            ]
            batch_tour_ids = {tour.id for tour, _ in batch if tour.id not in context.metric_facts}
            supplied_tour_ids = [item.tour_id for item in parsed_facts]
            if len(supplied_tour_ids) != len(set(supplied_tour_ids)) or set(supplied_tour_ids) != batch_tour_ids:
                raise AppError(
                    "METRIC_FACTS_INCOMPLETE",
                    "Submit one metric fact object for every tour in the active batch.",
                    422,
                )

            batch_tour_by_offer = {offer_id: tour for tour, offer_id in batch}
            max_sentences = self.settings.tuning.decide.quote_max_sentences
            for item in parsed:
                key = (item.offer_id, item.condition_id)
                tour = batch_tour_by_offer[item.offer_id]
                source = "\n".join(
                    _metric_source_fields(tour).values()
                )
                if item.verdict == "unknown":
                    state: State = "unknown"
                    quote, reason = "", item.reason.strip()[:500]
                else:
                    snapped = _snap_quote(source, item.quote, max_sentences)
                    quote_is_grounded = snapped is not None
                    reason_is_bounded = (
                        bool(item.reason.strip())
                        and len(item.reason) <= 500
                        and _sentence_count(item.reason) <= 2
                    )
                    if quote_is_grounded and reason_is_bounded:
                        state = _VERDICT_STATES[item.verdict]
                        quote, reason = snapped, item.reason.strip()
                    else:
                        state, quote, reason = "unknown", "", "Chưa có trích dẫn hợp lệ để xác nhận."
                context.verdicts[key] = (state, quote, reason)
                for same_tour_offer in tour.offers:
                    context.verdicts[(same_tour_offer.id, item.condition_id)] = (state, quote, reason)

            accepted_facts = 0
            rejected_facts = 0
            batch_tour_by_id = {tour.id: tour for tour, _ in batch}
            facts_to_cache: list[tuple[TourSnapshot, ExtractedTourFacts]] = []
            for item in parsed_facts:
                extracted, rejected = _validate_metric_facts(
                    batch_tour_by_id[item.tour_id], item, max_sentences
                )
                context.metric_facts[item.tour_id] = extracted
                facts_to_cache.append((batch_tour_by_id[item.tour_id], extracted))
                accepted_facts += len(extracted.activities) + len(extracted.route_legs)
                accepted_facts += len(extracted.inclusions) + len(extracted.exclusions)
                accepted_facts += len(extracted.surcharges) + len(extracted.cancellation_rules)
                accepted_facts += len(extracted.family_facts)
                rejected_facts += rejected
            self._save_metric_fact_cache_batch(facts_to_cache)

            context.batch_index += 1
            if context.batch_index < len(context.batches):
                response: dict[str, Any] = {
                    "requirement": context.requirement.model_dump(mode="json"),
                    "soft_review": self._soft_review_payload(context),
                    "metric_fact_validation": {
                        "accepted": accepted_facts,
                        "rejected": rejected_facts,
                    },
                }
                if context.decision_run_id:
                    response["decision_run_id"] = context.decision_run_id
                return _json(response)

            comparison = compare(
                context.requirement,
                context.comparison.tour_snapshots,
                cfg=self.settings.tuning.decide,
                soft_verdicts=context.verdicts,
                metric_facts=context.metric_facts,
            )
            if context.comparison.scenario_source_comparison_id:
                comparison = comparison.model_copy(update={
                    "scenario_source_comparison_id": context.comparison.scenario_source_comparison_id,
                })
            self._ranking_contexts.pop(context_id, None)
            if context.decision_run_id:
                self._save_decision_result(context.decision_run_id, comparison)
                return _json(self._decision_receipt(context.decision_run_id, comparison))
            comparison = limit_comparison(comparison)
            return _json({
                "requirement": context.requirement.model_dump(mode="json"),
                "comparison": comparison.model_dump(mode="json"),
                "ranking_complete": True,
            })

    def _soft_review_payload(self, context: _RankingContext) -> dict[str, Any]:
        batch = context.batches[context.batch_index]
        candidates = []
        for tour, offer_id in batch:
            offer = next(item for item in tour.offers if item.id == offer_id)
            source_fields = _metric_source_fields(tour)
            candidates.append({
                "tour_id": tour.id,
                "offer_id": offer_id,
                "tour_name": tour.name,
                "departure_date": offer.departure_date,
                "price": offer.price,
                "currency": offer.currency,
                "price_basis": offer.price_basis,
                "metric_facts_required": tour.id not in context.metric_facts,
                "source_fields": source_fields,
            })
        return {
            "context_id": context.id,
            "batch_index": context.batch_index + 1,
            "batch_count": len(context.batches),
            "review_candidate_count": len(context.candidates),
            "soft_conditions": [
                {
                    "id": item.id,
                    "preference": item.value,
                    "weight_percent": item.weight_percent,
                }
                for item in context.requirement.soft()
            ],
            "candidates": candidates,
        }

    def _comparison_payload(
        self,
        requirement: Requirement,
        comparison: Comparison,
        additional: dict[str, Any] | None = None,
        decision_run_id: str | None = None,
    ) -> str:
        review_candidates = soft_review_candidates(
            requirement, comparison.tour_snapshots, comparison.evaluations
        )
        payload: dict[str, Any] = {
            "requirement": requirement.model_dump(mode="json"),
            "scanned_tours": len(comparison.tour_snapshots),
            "scan_limit": self.settings.supabase_scan_limit,
        }
        if review_candidates:
            cached_facts = self._load_metric_fact_cache(review_candidates)
            candidates_to_review = [
                pair for pair in review_candidates
                if requirement.soft() or pair[0].id not in cached_facts
            ]
            batches = _review_batches(candidates_to_review)
            if not batches:
                scenario_source_id = comparison.scenario_source_comparison_id
                comparison = compare(
                    requirement,
                    comparison.tour_snapshots,
                    cfg=self.settings.tuning.decide,
                    metric_facts=cached_facts,
                )
                if scenario_source_id:
                    comparison = comparison.model_copy(update={
                        "scenario_source_comparison_id": scenario_source_id,
                    })
                if decision_run_id:
                    self._save_decision_result(decision_run_id, comparison)
                    return _json(self._decision_receipt(decision_run_id, comparison))
                comparison = limit_comparison(comparison)
                payload["comparison"] = comparison.model_dump(mode="json")
                if additional:
                    payload.update(additional)
                return _json(payload)
            context_id = uid("rank")
            context = _RankingContext(
                id=context_id,
                requirement=requirement,
                comparison=comparison,
                candidates=review_candidates,
                batches=batches,
                decision_run_id=decision_run_id,
                metric_facts=cached_facts,
            )
            with self._ranking_context_lock:
                self._ranking_contexts[context_id] = context
            payload["soft_review"] = self._soft_review_payload(context)
        else:
            if decision_run_id:
                self._save_decision_result(decision_run_id, comparison)
                return _json(self._decision_receipt(decision_run_id, comparison))
            comparison = limit_comparison(comparison)
            payload["comparison"] = comparison.model_dump(mode="json")
        if additional:
            payload.update(additional)
        return _json(payload)

    def _save_decision_result(self, run_id: str, comparison: Comparison) -> None:
        store = self.result_store or SessionStore(self.settings.database_url)
        should_close = self.result_store is None
        try:
            store.save_decision_result(run_id, comparison)
        finally:
            if should_close:
                store.close()

    def _load_metric_fact_cache(
        self, candidates: list[tuple[TourSnapshot, str]]
    ) -> dict[str, ExtractedTourFacts]:
        store = self.result_store or SessionStore(self.settings.database_url)
        should_close = self.result_store is None
        cached: dict[str, ExtractedTourFacts] = {}
        try:
            for tour, _offer_id in candidates:
                payload = store.get_metric_cache(fact_cache_id(tour))
                if not payload:
                    continue
                try:
                    facts = ExtractedTourFacts.model_validate(payload)
                except Exception:
                    continue
                if facts.tour_id == tour.id and facts.method_version == "tour-facts-v3":
                    cached[tour.id] = facts
        finally:
            if should_close:
                store.close()
        return cached

    def _save_metric_fact_cache_batch(
        self, entries: list[tuple[TourSnapshot, ExtractedTourFacts]]
    ) -> None:
        if not entries:
            return
        store = self.result_store or SessionStore(self.settings.database_url)
        should_close = self.result_store is None
        try:
            for tour, facts in entries:
                store.save_metric_cache(fact_cache_id(tour), facts.model_dump(mode="json"))
        finally:
            if should_close:
                store.close()

    @staticmethod
    def _decision_receipt(run_id: str, comparison: Comparison) -> dict[str, Any]:
        return {
            "decision_run_id": run_id,
            "requirement_id": comparison.requirement.id,
            "comparison_id": comparison.id,
            "scanned_tours": comparison.candidates_considered,
            "ranking_complete": True,
        }

    def clarify_date(
        self,
        calendar: Annotated[str, Field(description="lunar or solar.")],
        year: Annotated[int, Field(description="Full year, e.g. 2026.")],
        month: Annotated[int, Field(description="Month 1-12.")],
        day: Annotated[int, Field(description="Day of month.")],
        leap: Annotated[bool, Field(description="Lunar leap month flag.")] = False,
    ) -> str:
        if calendar == "lunar":
            result = resolve_lunar({"year": year, "month": month, "day": day, "leap": leap})
        elif calendar == "solar":
            try:
                result = date(year, month, day).isoformat()
            except ValueError:
                result = None
        else:
            result = None
        return _json({"calendar": calendar, "iso_date": result, "valid": result is not None})


def _is_iso_date(value: str) -> bool:
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _sentence_count(value: str) -> int:
    sentences = [item for item in re.split(r"(?<=[.!?。！？])\s+", value.strip()) if item]
    return len(sentences) or (1 if value.strip() else 0)


def _snap_quote(source: str, quote: str, max_sentences: int) -> str | None:
    """Snap a submitted quote outward to word boundaries within its source.

    Returns the snapped verbatim substring, or None when the quote is absent
    or exceeds the sentence cap. `str.isalnum` understands stacked Vietnamese
    diacritics, so no folding is needed. Snapping never invents text: the
    result stays a substring of `source`, keeping every downstream `in` check
    valid.
    """
    text = quote.strip()
    if not text:
        return None
    start = source.find(text)
    if start < 0:
        return None
    end = start + len(text)
    while start > 0 and source[start - 1].isalnum():
        start -= 1
    while end < len(source) and source[end].isalnum():
        end += 1
    snapped = source[start:end]
    if _sentence_count(snapped) > max_sentences:
        return None
    return snapped


def _review_batches(
    candidates: list[tuple[TourSnapshot, str]],
    *,
    max_candidates: int = 5,
    max_source_chars: int = 18_000,
) -> list[list[tuple[TourSnapshot, str]]]:
    """Bound each model payload without truncating any source field."""
    batches: list[list[tuple[TourSnapshot, str]]] = []
    current: list[tuple[TourSnapshot, str]] = []
    current_chars = 0
    for candidate in candidates:
        tour, _offer_id = candidate
        size = sum(len(value) for value in _metric_source_fields(tour).values())
        if current and (len(current) >= max_candidates or current_chars + size > max_source_chars):
            batches.append(current)
            current = []
            current_chars = 0
        current.append(candidate)
        current_chars += size
    if current:
        batches.append(current)
    return batches


def _metric_source_fields(tour: TourSnapshot) -> dict[str, str]:
    """Keep sources separate so long fields never crowd out later fields."""
    return {
        "itinerary": tour.itinerary,
        "route": " → ".join(tour.route) if tour.route_observed else "",
        "inclusions": tour.inclusions,
        "exclusions": tour.exclusions,
        "surcharges": tour.surcharges,
        "cancellation_policy": tour.cancellation_policy,
        "child_policy": tour.child_policy,
    }


def _metric_evidence(
    tour: TourSnapshot, source_field: str, quote: str, max_sentences: int
) -> MetricEvidence | None:
    source = _metric_source_fields(tour).get(source_field, "")
    snapped = _snap_quote(source, quote, max_sentences)
    if snapped is None:
        return None
    return MetricEvidence(
        source_field=source_field,
        quote=snapped,
        observed_at=tour.observed_at,
        url=tour.url,
    )


_MONEY_NUMBER = re.compile(
    r"(?<!\d)(\d{1,3}(?:[.,\s]\d{3})+|\d+(?:[.,]\d+)?)\s*(tỷ|ty|triệu|trieu|million|nghìn|nghin|ngàn|ngan|k)?",
    re.IGNORECASE,
)


def _money_amounts(quote: str) -> list[int]:
    amounts: list[int] = []
    for number, suffix in _MONEY_NUMBER.findall(quote):
        compact = re.sub(r"\s", "", number)
        if suffix:
            decimal = compact.replace(",", ".")
            try:
                base = float(decimal)
            except ValueError:
                continue
            multiplier = (
                1_000_000_000 if suffix.casefold() in {"tỷ", "ty"}
                else 1_000_000 if suffix.casefold() in {"triệu", "trieu", "million"}
                else 1_000 if suffix.casefold() in {"nghìn", "nghin", "ngàn", "ngan", "k"}
                else 1
            )
            amounts.append(round(base * multiplier))
            continue
        digits = re.sub(r"\D", "", compact)
        if digits:
            amounts.append(int(digits))
    return amounts


def _has_money_context(quote: str) -> bool:
    folded = quote.casefold()
    return bool(
        re.search(r"\b(vnd|vnđ|đồng|dong|đ)\b|[$€£¥]", folded)
        or re.search(r"\b(tỷ|ty|triệu|trieu|million|nghìn|nghin|ngàn|ngan|k)\b", folded)
        or any(word in folded for word in ("phí", "phu thu", "giá", "tien", "chi phí"))
    )


def _money_supported(amount: int | None, quote: str) -> bool:
    return amount is not None and _has_money_context(quote) and amount in _money_amounts(quote)


def _supported_currency(currency: str, quote: str) -> str:
    folded = quote.casefold()
    markers = {
        "VND": ("vnd", "vnđ", "đồng", "dong", "đ"),
        "USD": ("usd", "$"),
        "EUR": ("eur", "€"),
        "GBP": ("gbp", "£"),
        "JPY": ("jpy", "¥"),
        "CNY": ("cny", "rmb", "¥"),
        "THB": ("thb", "baht", "฿"),
    }
    requested = currency.strip().upper()
    if requested:
        supported = markers.get(requested, (requested.casefold(),))
        return requested if any(marker in folded for marker in supported) else ""
    return next(
        (code for code, tokens in markers.items() if any(token in folded for token in tokens)),
        "",
    )


def _unit_supported(unit: str, quote: str) -> bool:
    folded = _fold_catalog_text(quote)
    markers = {
        "per_person": ("nguoi", "khach", "/nguoi", "/khach"),
        "per_adult": ("nguoi lon", "adult", "/nguoi lon"),
        "per_child": ("tre em", "child", "/tre em"),
        "per_night": ("dem", "night", "/dem"),
        "per_room": ("phong", "room", "/phong"),
        "per_booking": ("tour", "goi", "chuyen", "booking"),
        "per_day": ("ngay", "day", "/ngay"),
        "per_vehicle": ("xe", "vehicle", "/xe"),
    }
    return unit in markers and any(_fold_catalog_text(marker) in folded for marker in markers[unit])


def _number_with_word(number: int | None, quote: str, words: tuple[str, ...]) -> bool:
    if number is None:
        return True
    for token in re.finditer(r"\d+", quote):
        if int(token.group()) != number:
            continue
        tail = quote[token.end():token.end() + 16].casefold()
        if any(word.casefold() in tail for word in words):
            return True
    return False


def _validate_metric_facts(
    tour: TourSnapshot, item: TourMetricFactsInput, max_sentences: int
) -> tuple[ExtractedTourFacts, int]:
    accepted_activities: list[ActivityFact] = []
    accepted_legs: list[RouteLegFact] = []
    accepted_coverage: list[CoverageFact] = []
    accepted_exclusions: list[CostExposure] = []
    accepted_surcharges: list[CostExposure] = []
    accepted_cancellation: list[CancellationRule] = []
    accepted_family: list[FamilyFact] = []
    rejected = 0

    for fact in item.activities:
        evidence = _metric_evidence(tour, "itinerary", fact.quote, max_sentences)
        if evidence is None or not fact.name.strip() or fact.name not in fact.quote:
            rejected += 1
            continue
        day = fact.day if _number_with_word(fact.day, fact.quote, ("ngày", "day")) else None
        accepted_activities.append(ActivityFact(name=fact.name.strip(), day=day, evidence=evidence))

    for fact in item.route_legs:
        field = next((name for name in ("route", "itinerary")
                      if _metric_evidence(tour, name, fact.quote, max_sentences) is not None), "")
        evidence = _metric_evidence(tour, field, fact.quote, max_sentences) if field else None
        if (evidence is None or not fact.origin.strip() or not fact.destination.strip()
                or fact.origin not in fact.quote or fact.destination not in fact.quote):
            rejected += 1
            continue
        accepted_legs.append(RouteLegFact(
            origin=fact.origin.strip(), destination=fact.destination.strip(),
            mode=fact.mode.strip(), evidence=evidence,
        ))

    for fact in item.inclusions:
        source_field = "exclusions" if fact.status == "excluded" else "inclusions"
        evidence = _metric_evidence(tour, source_field, fact.quote, max_sentences)
        if evidence is None:
            rejected += 1
            continue
        accepted_coverage.append(CoverageFact(
            category=fact.category, status=fact.status, evidence=evidence
        ))

    for source_field, facts, destination in (
        ("exclusions", item.exclusions, accepted_exclusions),
        ("surcharges", item.surcharges, accepted_surcharges),
    ):
        for fact in facts:
            evidence = _metric_evidence(tour, source_field, fact.quote, max_sentences)
            if evidence is None or not fact.name.strip():
                rejected += 1
                continue
            amount = fact.amount if _money_supported(fact.amount, fact.quote) else None
            unit = fact.unit if _unit_supported(fact.unit, fact.quote) else "unknown"
            currency = _supported_currency(fact.currency, fact.quote)
            applies_when = fact.applies_when if fact.applies_when and fact.applies_when in fact.quote else ""
            destination.append(CostExposure(
                name=fact.name.strip(), obligation=fact.obligation,
                amount=amount, currency=currency, unit=unit,
                applies_when=applies_when, source_field=source_field,
                quote=evidence.quote,
            ))

    for fact in item.cancellation_rules:
        evidence = _metric_evidence(tour, "cancellation_policy", fact.quote, max_sentences)
        if evidence is None:
            rejected += 1
            continue
        days = fact.days_before_departure
        if not _number_with_word(days, fact.quote, ("ngày", "day")):
            days = None
        refund = fact.refund_percent
        if refund is not None and not re.search(rf"(?<!\d){refund}\s*%", fact.quote):
            refund = None
        fee = fact.fee_amount if _money_supported(fact.fee_amount, fact.quote) else None
        currency = _supported_currency(fact.currency, fact.quote)
        accepted_cancellation.append(CancellationRule(
            days_before_departure=days, refund_percent=refund,
            fee_amount=fee, currency=currency, evidence=evidence,
        ))

    for fact in item.family_facts:
        evidence = _metric_evidence(tour, "child_policy", fact.quote, max_sentences)
        if evidence is None:
            rejected += 1
            continue
        min_age = fact.min_age if _number_with_word(fact.min_age, fact.quote, ("tuổi", "tuoi", "year")) else None
        max_age = fact.max_age if _number_with_word(fact.max_age, fact.quote, ("tuổi", "tuoi", "year")) else None
        amount = fact.amount if _money_supported(fact.amount, fact.quote) else None
        percent = fact.percent if fact.percent is not None and re.search(rf"(?<!\d){fact.percent}\s*%", fact.quote) else None
        condition = fact.condition if fact.condition and fact.condition in fact.quote else ""
        accepted_family.append(FamilyFact(
            kind=fact.kind, min_age=min_age, max_age=max_age,
            amount=amount, percent=percent, condition=condition, evidence=evidence,
        ))

    return ExtractedTourFacts(
        tour_id=tour.id,
        activities=accepted_activities,
        route_legs=accepted_legs,
        inclusions=accepted_coverage,
        exclusions=accepted_exclusions,
        surcharges=accepted_surcharges,
        cancellation_rules=accepted_cancellation,
        family_facts=accepted_family,
        reviewed_fields=[
            field for field in item.reviewed_fields
            if _metric_source_fields(tour).get(field, "").strip()
        ],
        method_version="tour-facts-v3",
    ), rejected


def _fold_catalog_text(value: str) -> str:
    folded = unicodedata.normalize("NFD", value.strip().casefold().replace("đ", "d"))
    return re.sub(r"\s+", " ", "".join(char for char in folded if not unicodedata.combining(char)))


def _fold_catalog_label(value: str) -> str:
    """Compare casing, accents and punctuation without guessing geographic aliases."""
    return fold_vi(value)


def _unresolved_location_labels(
    conditions: list[Any], destinations: list[str], departure_cities: list[str]
) -> list[dict[str, Any]]:
    available = {
        "destination": {_fold_catalog_label(value) for value in destinations},
        "departure_city": {_fold_catalog_label(value) for value in departure_cities},
    }
    unresolved: list[dict[str, Any]] = []
    for condition in conditions:
        if condition.field not in available:
            continue
        values = condition.value if isinstance(condition.value, list) else [condition.value]
        missing = [
            str(value)
            for value in values
            if not isinstance(value, str)
            or _fold_catalog_label(value) not in available[condition.field]
        ]
        if missing:
            unresolved.append({"field": condition.field, "values": missing})
    return unresolved


def _preflight_offer_key(value: dict[str, Any]) -> tuple[Any, ...]:
    has_price = isinstance(value.get("price"), int) and not isinstance(value.get("price"), bool)
    return (
        0 if has_price else 1,
        str(value.get("currency", "")).upper(),
        value["price"] if has_price else 10**18,
        str(value.get("departure_date", "")),
        str(value.get("tour_name", "")).casefold(),
        str(value.get("tour_id", "")),
    )


def create_server(settings: Settings | None = None) -> FastMCP:
    settings = settings or Settings.load()
    catalog = for_settings(settings)
    workflows = TourWorkflows(settings, catalog)
    tools = AgentTools(settings, catalog, workflows)
    server = FastMCP("tour-catalog")

    server.tool()(_guard_tool("ask_choice", tools.ask_choice))
    server.tool()(_guard_tool("catalog_facets", tools.catalog_facets))
    server.tool()(_guard_tool("discover_destinations", tools.discover_destinations))
    server.tool()(_guard_tool("draft_requirement", tools.draft_requirement))
    server.tool()(_guard_tool("query_tours", tools.query_tours))
    server.tool()(_guard_tool("tour_detail", tools.tour_detail))
    server.tool()(_guard_tool("score_soft", tools.score_soft))
    server.tool()(_guard_tool("clarify_date", tools.clarify_date))
    return server


def _guard_tool(name: str, function: Any) -> Any:
    """Convert tool exceptions to a safe JSON error and log them once."""

    @wraps(function)
    def guarded(*args: Any, **kwargs: Any) -> str:
        try:
            return function(*args, **kwargs)
        except AppError as exc:
            log_app_error(exc, transport="mcp", operation=name)
            return _json(exc.payload())
        except Exception as exc:
            log_unexpected_error(exc, transport="mcp", operation=name)
            return _json(
                {"error": {"code": "INTERNAL_ERROR", "message": "An internal error occurred."}}
            )

    return guarded


def main() -> None:
    create_server().run()


if __name__ == "__main__":
    main()
