"""Local MCP tool server for grounded travel-agent workflows."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from functools import wraps
from threading import RLock
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

from backend.agent.results import limit_comparison
from backend.data.catalog import for_settings
from backend.data.sessions import BaseStore, SessionStore
from backend.decide.engine import compare, soft_review_candidates
from backend.error_logging import log_app_error, log_unexpected_error
from backend.errors import AppError
from backend.input.lunar import resolve_lunar
from backend.models import Comparison, Requirement, State, TourSnapshot, uid
from backend.settings import Settings
from backend.workflows import TourWorkflows

_VERDICT_STATES: dict[str, State] = {"fit": "pass", "unknown": "unknown", "not_fit": "fail"}


class QueryConditionInput(BaseModel):
    """Structured MCP input; semantic constraints are rechecked by the workflow."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Unique condition ID, e.g. c1.")
    field: Literal[
        "destination", "departure_city", "date_from", "date_to", "budget_max",
        "duration_days", "transport", "accommodation", "preference",
    ] = Field(description="Condition field supported by the travel requirement contract.")
    operator: Literal["contains", "any", "eq", "lte"] = Field(
        description="Operator compatible with the selected field."
    )
    value: str | int | list[str] = Field(
        description="Condition value: text, positive integer, or destination choices."
    )
    strength: Literal["hard", "soft"] = Field(description="Whether this is a hard or soft condition.")
    quote: str = Field(description="Exact substring copied from raw_text that supports this condition.")
    weight_percent: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="User-reviewed weight for a soft preference; all soft weights must total 100.",
    )


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


class SoftVerdictInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    offer_id: str = Field(description="Offer ID from the active soft_review batch.")
    condition_id: str = Field(description="Soft condition ID from the active soft_review batch.")
    verdict: Literal["fit", "unknown", "not_fit"] = Field(
        description="Whether the tour evidence supports this soft preference."
    )
    quote: str = Field(default="", description="Exact short quote from the candidate evidence.")
    reason: str = Field(default="", description="At most two concise sentences grounded in the quote.")


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


def _json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


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
        self, question: str, options: list[dict[str, str]], allow_custom: bool = True
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

    def catalog_facets(self) -> str:
        tours = self.workflows.snapshots(self.settings.supabase_scan_limit)
        destinations = sorted({value for tour in tours for value in tour.destinations})
        prices = sorted({
            offer.price for tour in tours for offer in tour.offers
            if offer.price is not None and offer.currency == "VND"
        })
        dates = sorted({
            offer.departure_date for tour in tours for offer in tour.offers
            if _is_iso_date(offer.departure_date)
        })
        return _json({
            "destinations": destinations,
            "prices_vnd": prices,
            "departure_dates": dates,
            "scanned_tours": len(tours),
            "scan_limit": self.settings.supabase_scan_limit,
        })

    def query_tours(
        self,
        raw_text: str,
        conditions: list[QueryConditionInput],
        decision_run_id: str,
        travelers: int = 1,
        ranking: QueryRankingInput | None = None,
        requirement_id: str = "",
    ) -> str:
        if not re.fullmatch(r"dec_[0-9a-f]{32}", decision_run_id):
            raise AppError("DECISION_RUN_INVALID", "Invalid decision run ID.", 422)
        structured_conditions = [
            item.model_dump(mode="json")
            if isinstance(item, QueryConditionInput)
            else QueryConditionInput.model_validate(item).model_dump(mode="json")
            for item in conditions
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
        )
        comparison = self.workflows.comparison(requirement, self.settings.supabase_scan_limit)
        return self._comparison_payload(
            requirement, comparison, decision_run_id=decision_run_id or None
        )

    def draft_requirement(
        self,
        raw_text: str,
        conditions: list[QueryConditionInput],
        travelers: int = 1,
        ranking: QueryRankingInput | None = None,
    ) -> str:
        """Validate a reviewable brief without reading the tour catalog."""
        structured_conditions = [
            item.model_dump(mode="json")
            if isinstance(item, QueryConditionInput)
            else QueryConditionInput.model_validate(item).model_dump(mode="json")
            for item in conditions
        ]
        ranking_value = (
            ranking.model_dump(mode="json")
            if isinstance(ranking, QueryRankingInput)
            else QueryRankingInput.model_validate(ranking).model_dump(mode="json")
            if ranking is not None
            else None
        )
        requirement = self.workflows.requirement(
            raw_text, structured_conditions, travelers, ranking_value
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

    def tour_detail(self, tour_id: str) -> str:
        tours = self.workflows.snapshots(self.settings.supabase_scan_limit)
        tour = next((tour for tour in tours if tour.id == tour_id), None)
        if tour is None:
            return _json({"error": "Tour not found in the active catalog."})
        return _json(tour.model_dump(mode="json"))

    def score_soft(
        self,
        context_id: str,
        verdicts: list[SoftVerdictInput],
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

            batch_tour_by_offer = {offer_id: tour for tour, offer_id in batch}
            max_quote = min(self.settings.tuning.decide.quote_chars, 200)
            for item in parsed:
                key = (item.offer_id, item.condition_id)
                tour = batch_tour_by_offer[item.offer_id]
                source = "\n".join(
                    str(getattr(tour, name, ""))
                    for name in self.settings.tuning.decide.soft_fields
                )
                if item.verdict == "unknown":
                    state: State = "unknown"
                    quote, reason = "", item.reason.strip()[:500]
                else:
                    quote_is_grounded = bool(item.quote) and len(item.quote) <= max_quote and item.quote in source
                    reason_is_bounded = (
                        bool(item.reason.strip())
                        and len(item.reason) <= 500
                        and _sentence_count(item.reason) <= 2
                    )
                    if quote_is_grounded and reason_is_bounded:
                        state = _VERDICT_STATES[item.verdict]
                        quote, reason = item.quote, item.reason.strip()
                    else:
                        state, quote, reason = "unknown", "", "Chưa có trích dẫn hợp lệ để xác nhận."
                context.verdicts[key] = (state, quote, reason)
                for same_tour_offer in tour.offers:
                    context.verdicts[(same_tour_offer.id, item.condition_id)] = (state, quote, reason)

            context.batch_index += 1
            if context.batch_index < len(context.batches):
                response: dict[str, Any] = {
                    "requirement": context.requirement.model_dump(mode="json"),
                    "soft_review": self._soft_review_payload(context),
                }
                if context.decision_run_id:
                    response["decision_run_id"] = context.decision_run_id
                return _json(response)

            comparison = compare(
                context.requirement,
                context.comparison.tour_snapshots,
                cfg=self.settings.tuning.decide,
                soft_verdicts=context.verdicts,
            )
            self._ranking_contexts.pop(context_id, None)
            comparison = limit_comparison(comparison)
            if context.decision_run_id:
                self._save_decision_result(context.decision_run_id, comparison)
                return _json(self._decision_receipt(context.decision_run_id, comparison))
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
            snippets = [
                f"{name}: {str(getattr(tour, name, '')).strip()}"
                for name in self.settings.tuning.decide.soft_fields
                if str(getattr(tour, name, "")).strip()
            ]
            evidence = "\n".join(snippets)[:2400]
            candidates.append({
                "offer_id": offer_id,
                "tour_name": tour.name,
                "departure_date": offer.departure_date,
                "price": offer.price,
                "currency": offer.currency,
                "price_basis": offer.price_basis,
                "evidence": evidence,
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
        ) if requirement.soft() else []
        payload: dict[str, Any] = {
            "requirement": requirement.model_dump(mode="json"),
            "scanned_tours": len(comparison.tour_snapshots),
            "scan_limit": self.settings.supabase_scan_limit,
        }
        if review_candidates:
            context_id = uid("rank")
            batches = [review_candidates[i:i + 5] for i in range(0, len(review_candidates), 5)]
            context = _RankingContext(
                id=context_id,
                requirement=requirement,
                comparison=comparison,
                candidates=review_candidates,
                batches=batches,
                decision_run_id=decision_run_id,
            )
            with self._ranking_context_lock:
                self._ranking_contexts[context_id] = context
            payload["soft_review"] = self._soft_review_payload(context)
        else:
            comparison = limit_comparison(comparison)
            if decision_run_id:
                self._save_decision_result(decision_run_id, comparison)
                return _json(self._decision_receipt(decision_run_id, comparison))
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

    @staticmethod
    def _decision_receipt(run_id: str, comparison: Comparison) -> dict[str, Any]:
        return {
            "decision_run_id": run_id,
            "requirement_id": comparison.requirement.id,
            "comparison_id": comparison.id,
            "scanned_tours": comparison.candidates_considered,
            "ranking_complete": True,
        }

    def clarify_date(self, calendar: str, year: int, month: int, day: int, leap: bool = False) -> str:
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


def _fold_catalog_text(value: str) -> str:
    folded = unicodedata.normalize("NFD", value.strip().casefold().replace("đ", "d"))
    return re.sub(r"\s+", " ", "".join(char for char in folded if not unicodedata.combining(char)))


def create_server(settings: Settings | None = None) -> FastMCP:
    settings = settings or Settings.load()
    catalog = for_settings(settings)
    workflows = TourWorkflows(settings, catalog)
    tools = AgentTools(settings, catalog, workflows)
    server = FastMCP("tour-catalog")

    server.tool()(_guard_tool("ask_choice", tools.ask_choice))
    server.tool()(_guard_tool("catalog_facets", tools.catalog_facets))
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
